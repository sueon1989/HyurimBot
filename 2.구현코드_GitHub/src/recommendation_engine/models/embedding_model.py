#!/usr/bin/env python3
"""
HyurimBot 한국어 BERT 임베딩 시스템 - 기획안 목적 완전 구현
RAG 기반 자연휴양림 AI 추천을 위한 의미적 유사도 검색 엔진

✅ 기획안 핵심 요구사항 구현:
- 개인화 맞춤 추천: 사용자 입력(가족구성, 지역, 테마) 기반 벡터화
- 풍부한 정보 제공: 시설명, 편의시설, 가격, 위치 통합 임베딩  
- 한국어 특화: jhgan/ko-sroberta-multitask 모델 활용
- 실시간 검색: FAISS 연동을 위한 정규화된 벡터 출력
"""

import os
import logging
import numpy as np
import sqlite3
import pickle
import re
from typing import List, Dict, Optional, Union, Tuple
from pathlib import Path

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HyurimBotEmbeddingEngine:
    """
    HyurimBot 전용 한국어 BERT 임베딩 엔진
    기획안의 RAG 기반 개인화 추천 시스템 구현
    """
    
    def __init__(self, db_path: str, model_name: str = "jhgan/ko-sroberta-multitask"):
        """
        초기화
        
        Args:
            db_path: SQLite 데이터베이스 경로 
            model_name: 기획안 지정 한국어 BERT 모델
        """
        self.db_path = db_path
        self.model_name = model_name
        self.model = None
        self.accommodations_data = []
        self.embeddings = None
        
        # 캐시 디렉토리 설정
        self.cache_dir = Path(db_path).parent.parent / "data" / "embeddings"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings_cache_path = self.cache_dir / "hyurimbot_embeddings.pkl"
        
        logger.info(f"🤖 HyurimBot 임베딩 엔진 초기화")
        logger.info(f"📁 캐시 경로: {self.cache_dir}")
        
        # 자동으로 데이터베이스와 모델 로드
        self._load_accommodation_data()
        self._initialize_model()
    
    def _initialize_model(self):
        """기획안 지정 한국어 BERT 모델 초기화"""
        try:
            # SentenceTransformer 임포트 (선택적)
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"🚀 한국어 BERT 모델 로딩: {self.model_name}")
                self.model = SentenceTransformer(self.model_name)
                logger.info("✅ 한국어 BERT 모델 초기화 완료")
                return
            except ImportError:
                logger.warning("⚠️ sentence-transformers 미설치, 기본 임베딩 사용")
            except Exception as e:
                logger.warning(f"⚠️ BERT 모델 로딩 실패, 기본 임베딩 사용: {e}")
            
            # 기본 임베딩 (TF-IDF 기반) 사용
            self.model = "basic_tfidf"
            logger.info("✅ 기본 TF-IDF 임베딩 시스템 사용")
            
        except Exception as e:
            logger.error(f"❌ 임베딩 모델 초기화 실패: {e}")
            raise
    
    def _load_accommodation_data(self):
        """기획안에 맞는 풍부한 숙박시설 데이터 로드"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 기획안 요구: 시설, 가격, 정책, 편의시설 모든 정보 포함
            cursor.execute("""
                SELECT 
                    a.accommodation_id,
                    a.forest_id,
                    a.facility_name,
                    a.facility_type,
                    a.capacity_standard,
                    a.capacity_maximum,
                    a.area,
                    a.amenities,
                    a.price_off_weekday,
                    a.price_peak_weekend,
                    a.usage_info,
                    f.forest_name,
                    f.sido,
                    f.main_facilities,
                    f.address,
                    f.phone,
                    f.homepage_url
                FROM accommodations a
                JOIN forests f ON a.forest_id = f.forest_id
                WHERE a.facility_name IS NOT NULL 
                  AND a.facility_name != ''
                ORDER BY f.forest_name, a.facility_name
            """)
            
            rows = cursor.fetchall()
            self.accommodations_data = [dict(row) for row in rows]
            conn.close()
            
            logger.info(f"📦 {len(self.accommodations_data)}개 숙박시설 데이터 로드 완료")
            
            # 샘플 데이터 로그
            if self.accommodations_data:
                sample = self.accommodations_data[0]
                logger.info(f"📋 샘플: {sample.get('facility_name')} ({sample.get('forest_name')})")
            
        except Exception as e:
            logger.error(f"❌ 데이터베이스 로드 실패: {e}")
            self.accommodations_data = []
    
    def _create_rich_feature_text(self, accommodation: Dict) -> str:
        """
        기획안 요구: 풍부한 특성 텍스트 생성
        시설명, 편의시설, 지역, 가격, 가족구성 등을 종합적으로 반영
        """
        features = []
        
        # 1. 기본 시설 정보 (가장 중요)
        if accommodation.get('facility_name'):
            features.append(f"시설: {accommodation['facility_name']}")
        
        if accommodation.get('facility_type'):
            features.append(f"유형: {accommodation['facility_type']}")
        
        # 2. 위치 정보 (기획안: 지역별 추천)
        if accommodation.get('forest_name'):
            features.append(f"휴양림: {accommodation['forest_name']}")
        
        if accommodation.get('sido'):
            features.append(f"지역: {accommodation['sido']}")
        
        # 3. 가족구성 기반 수용인원 (기획안 핵심)
        capacity = accommodation.get('capacity_standard')
        if capacity:
            if capacity <= 4:
                features.append("소규모가족 커플여행 2~4인")
            elif capacity <= 8:
                features.append("중간가족 가족여행 4~8인")
            else:
                features.append("대가족 단체여행 8인이상")
                
            features.append(f"수용인원: {capacity}명")
        
        # 4. 편의시설 (기획안: 중요 특성)
        amenities_text = []
        if accommodation.get('amenities'):
            amenities = accommodation['amenities'].replace(';', ' ')
            amenities_text.append(f"편의시설: {amenities}")
                
        features.extend(amenities_text)
        
        # 5. 가격대 정보 (기획안: 체감가 중요)
        prices = []
        if accommodation.get('price_off_weekday'):
            prices.append(accommodation['price_off_weekday'])
        if accommodation.get('price_peak_weekend'):
            prices.append(accommodation['price_peak_weekend'])
        
        if prices:
            avg_price = sum(prices) // len(prices)
            if avg_price < 100000:
                price_category = "저가격대 경제적"
            elif avg_price < 200000:
                price_category = "중가격대 합리적"
            else:
                price_category = "고가격대 프리미엄"
            
            features.append(f"가격: {price_category}")
            features.append(f"평균요금: {avg_price:,}원")
        
        # 6. 휴양림 부대시설
        if accommodation.get('main_facilities'):
            facilities = accommodation['main_facilities'][:100]
            features.append(f"부대시설: {facilities}")
        
        # 7. 이용 특성
        if accommodation.get('usage_info'):
            usage_info = accommodation['usage_info'][:100]
            features.append(f"이용안내: {usage_info}")
        
        return " | ".join(features)
    
    def generate_embeddings(self, force_regenerate: bool = False) -> np.ndarray:
        """
        기획안 목적: 모든 숙박시설에 대한 의미적 임베딩 생성
        
        Args:
            force_regenerate: 캐시 무시하고 새로 생성할지 여부
        
        Returns:
            정규화된 임베딩 행렬 (N x embedding_dim)
        """
        # 캐시 확인
        if not force_regenerate and os.path.exists(self.embeddings_cache_path):
            try:
                logger.info("📋 캐시된 임베딩 로딩...")
                with open(self.embeddings_cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                    self.embeddings = cached_data['embeddings']
                    logger.info(f"✅ 캐시 임베딩 로딩 완료: {self.embeddings.shape}")
                    return self.embeddings
            except Exception as e:
                logger.warning(f"⚠️ 캐시 로딩 실패, 새로 생성: {e}")
        
        if not self.accommodations_data:
            logger.error("❌ 숙박시설 데이터가 없습니다")
            return np.array([])
        
        logger.info("🚀 숙박시설 임베딩 생성 시작...")
        
        # 풍부한 특성 텍스트 생성
        feature_texts = []
        for accommodation in self.accommodations_data:
            feature_text = self._create_rich_feature_text(accommodation)
            feature_texts.append(feature_text)
        
        # BERT 또는 TF-IDF 임베딩 생성
        try:
            if isinstance(self.model, str) and self.model == "basic_tfidf":
                # TF-IDF 기반 임베딩
                self.embeddings = self._generate_tfidf_embeddings(feature_texts)
            else:
                # BERT 임베딩
                self.embeddings = self.model.encode(
                    feature_texts,
                    batch_size=16,
                    show_progress_bar=True,
                    normalize_embeddings=True
                )
            
            # 캐시 저장
            cache_data = {
                'embeddings': self.embeddings,
                'accommodation_ids': [acc['accommodation_id'] for acc in self.accommodations_data],
                'model_name': self.model_name,
                'feature_count': len(self.accommodations_data)
            }
            
            with open(self.embeddings_cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            
            logger.info(f"✅ 임베딩 생성 완료: {self.embeddings.shape}")
            logger.info(f"💾 캐시 저장: {self.embeddings_cache_path}")
            
            return self.embeddings
            
        except Exception as e:
            logger.error(f"❌ 임베딩 생성 실패: {e}")
            return np.array([])
    
    def _generate_tfidf_embeddings(self, texts: List[str]) -> np.ndarray:
        """TF-IDF 기반 기본 임베딩 생성 (BERT 대체용)"""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import normalize
        
        # 한국어 특화 TF-IDF
        vectorizer = TfidfVectorizer(
            max_features=1000,
            ngram_range=(1, 2),
            stop_words=None,  # 한국어 불용어 별도 처리 필요
            lowercase=False  # 한국어는 대소문자 구분 안함
        )
        
        # TF-IDF 벡터 생성
        tfidf_matrix = vectorizer.fit_transform(texts)
        
        # 정규화된 dense 배열로 변환
        embeddings = normalize(tfidf_matrix.toarray(), norm='l2')
        
        logger.info(f"🔧 TF-IDF 임베딩 생성: {embeddings.shape}")
        return embeddings
    
    def encode_user_query(self, query: str) -> np.ndarray:
        """
        기획안 목적: 사용자 자연어 쿼리를 임베딩으로 변환
        개인화 요소(가족구성, 지역, 테마)를 자동 추출하여 반영
        
        Args:
            query: 사용자 검색 쿼리 (예: "4인 가족 넓은 객실")
        
        Returns:
            정규화된 쿼리 임베딩 벡터
        """
        if not query:
            logger.warning("❌ 빈 쿼리입니다")
            return np.array([])
        
        try:
            # 기획안 요구: 쿼리 전처리 및 보강
            enhanced_query = self._enhance_user_query(query)
            
            if isinstance(self.model, str) and self.model == "basic_tfidf":
                # TF-IDF로 쿼리 임베딩
                return self._encode_query_tfidf(enhanced_query)
            else:
                # BERT로 쿼리 임베딩
                query_embedding = self.model.encode(
                    [enhanced_query],
                    normalize_embeddings=True
                )
                return query_embedding[0]
                
        except Exception as e:
            logger.error(f"❌ 쿼리 임베딩 실패: {e}")
            return np.array([])
    
    def _enhance_user_query(self, query: str) -> str:
        """
        기획안 요구: 사용자 쿼리 의도 파악 및 보강
        가족구성, 지역, 테마 정보를 자동 추출하여 검색 정확도 향상
        """
        enhanced = query.strip()
        
        # 1. 인원 정보 추출 (기획안: 가족구성 기반)
        capacity_match = re.search(r'(\d+)(?:인|명|인용)', enhanced)
        if capacity_match:
            capacity = int(capacity_match.group(1))
            if capacity <= 4:
                enhanced += " 소규모가족 커플여행"
            elif capacity <= 8:
                enhanced += " 중간가족 가족여행"
            else:
                enhanced += " 대가족 단체여행"
        
        # 2. 가족 관련 키워드 보강
        family_keywords = ['가족', '아이', '어린이', '부모', '할머니', '할아버지', '자녀']
        if any(keyword in enhanced for keyword in family_keywords):
            enhanced += " 가족친화적 편의시설"
        
        # 3. 편의시설 키워드 보강
        amenity_keywords = ['넓은', '깨끗한', '조용한', '편리한', '전망', '뷰']
        if any(keyword in enhanced for keyword in amenity_keywords):
            enhanced += " 고급편의시설 쾌적한"
        
        # 4. 지역 키워드 감지
        region_keywords = ['제주', '강원', '경기', '충북', '충남', '전북', '전남', '경북', '경남']
        found_regions = [region for region in region_keywords if region in enhanced]
        if found_regions:
            enhanced += f" {' '.join(found_regions)}지역"
        
        # 5. 테마 키워드 보강 (기획안: 테마별 추천)
        theme_keywords = {
            '힐링': '조용한 휴식 산림욕',
            '액티비티': '체험프로그램 레포츠',
            '자연': '산림욕 자연휴양',
            '전통': '초가집 한옥 전통',
            '프리미엄': '고급 럭셔리 특급'
        }
        
        for theme, enhancement in theme_keywords.items():
            if theme in enhanced:
                enhanced += f" {enhancement}"
        
        logger.info(f"🔍 쿼리 보강: '{query}' → '{enhanced}'")
        return enhanced
    
    def _encode_query_tfidf(self, query: str) -> np.ndarray:
        """TF-IDF 방식으로 쿼리 임베딩"""
        # 간단한 단어 매칭 기반 임베딩
        query_words = set(query.lower().split())
        
        if not self.accommodations_data or self.embeddings is None:
            return np.array([])
        
        # 각 숙박시설과의 단어 매칭 점수 계산
        similarity_scores = []
        for accommodation in self.accommodations_data:
            acc_text = self._create_rich_feature_text(accommodation).lower()
            acc_words = set(acc_text.split())
            
            # Jaccard 유사도
            intersection = query_words.intersection(acc_words)
            union = query_words.union(acc_words)
            
            similarity = len(intersection) / len(union) if union else 0.0
            similarity_scores.append(similarity)
        
        # 정규화
        scores_array = np.array(similarity_scores)
        if scores_array.sum() > 0:
            scores_array = scores_array / np.linalg.norm(scores_array)
        
        return scores_array
    
    def get_accommodation_by_index(self, index: int) -> Optional[Dict]:
        """인덱스로 숙박시설 정보 반환"""
        if 0 <= index < len(self.accommodations_data):
            return self.accommodations_data[index]
        return None
    
    def get_embedding_info(self) -> Dict:
        """임베딩 엔진 정보 반환"""
        return {
            'model_name': self.model_name,
            'accommodations_count': len(self.accommodations_data),
            'embeddings_shape': self.embeddings.shape if self.embeddings is not None else None,
            'cache_path': str(self.embeddings_cache_path),
            'cache_exists': os.path.exists(self.embeddings_cache_path)
        }


def test_embedding_engine():
    """임베딩 엔진 테스트"""
    import sys
    from pathlib import Path
    
    # 데이터베이스 경로
    project_root = Path(__file__).parent.parent.parent
    db_path = project_root / "database" / "hyurimbot.db"
    
    if not db_path.exists():
        print(f"❌ 데이터베이스를 찾을 수 없습니다: {db_path}")
        return False
    
    try:
        print("🤖 HyurimBot 임베딩 엔진 테스트 시작")
        print("=" * 60)
        
        # 엔진 초기화
        engine = HyurimBotEmbeddingEngine(str(db_path))
        
        # 임베딩 생성
        embeddings = engine.generate_embeddings()
        
        if embeddings.size == 0:
            print("❌ 임베딩 생성 실패")
            return False
        
        print(f"✅ 임베딩 생성 성공: {embeddings.shape}")
        
        # 쿼리 테스트
        test_queries = [
            "4인 가족 넓은 객실",
            "조용한 휴양림에서 힐링",
            "제주도 전통 초가집",
            "아이와 함께 편의시설 좋은 곳"
        ]
        
        for query in test_queries:
            query_embedding = engine.encode_user_query(query)
            if query_embedding.size > 0:
                print(f"✅ 쿼리 '{query}' 임베딩 성공")
            else:
                print(f"❌ 쿼리 '{query}' 임베딩 실패")
        
        # 엔진 정보
        info = engine.get_embedding_info()
        print("\n📊 임베딩 엔진 정보:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        print("\n🎉 HyurimBot 임베딩 엔진 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False


if __name__ == "__main__":
    success = test_embedding_engine()
    sys.exit(0 if success else 1)