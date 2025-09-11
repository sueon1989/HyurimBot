#!/usr/bin/env python3
"""
HyurimBot 기본 추천 시스템 테스트
의존성 패키지 없이 기본 Python 라이브러리만 사용한 간단한 추천 데모
"""

import sqlite3
import json
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

class BasicRecommendationEngine:
    """기본 추천 엔진 (numpy/pandas 없이)"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.accommodations_cache = []
        self.load_accommodations()
    
    def load_accommodations(self):
        """숙박시설 데이터 로드"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    a.accommodation_id,
                    a.facility_name,
                    a.facility_type,
                    a.capacity_standard,
                    a.capacity_maximum,
                    a.area,
                    a.amenities,
                    a.price_off_weekday,
                    a.price_peak_weekend,
                    f.forest_name,
                    f.sido,
                    f.address
                FROM accommodations a
                JOIN forests f ON a.forest_id = f.forest_id
                WHERE a.facility_name IS NOT NULL
            """)
            
            self.accommodations_cache = [dict(row) for row in cursor.fetchall()]
            conn.close()
            print(f"📦 {len(self.accommodations_cache)}개 숙박시설 데이터 로드 완료")
            
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {e}")
            self.accommodations_cache = []
    
    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """간단한 텍스트 유사도 계산 (단어 기반)"""
        if not text1 or not text2:
            return 0.0
        
        # 단어 집합 생성
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        # Jaccard 유사도
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def calculate_price_similarity(self, target_price: int, accommodation_price: int) -> float:
        """가격 유사도 계산"""
        if not target_price or not accommodation_price:
            return 0.5
        
        # 가격 차이를 0-1 범위로 정규화
        price_diff = abs(target_price - accommodation_price)
        max_price = max(target_price, accommodation_price)
        
        if max_price == 0:
            return 1.0
        
        similarity = max(0, 1 - (price_diff / max_price))
        return similarity
    
    def calculate_capacity_similarity(self, target_capacity: int, accommodation_capacity: int) -> float:
        """수용인원 유사도 계산"""
        if not target_capacity or not accommodation_capacity:
            return 0.5
        
        capacity_diff = abs(target_capacity - accommodation_capacity)
        similarity = max(0, 1 - (capacity_diff / max(target_capacity, accommodation_capacity)))
        return similarity
    
    def search_accommodations(self, 
                            query: str = "",
                            target_capacity: int = None,
                            target_price: int = None,
                            location_filter: str = None,
                            top_k: int = 5) -> List[Dict]:
        """숙박시설 추천 검색"""
        
        if not self.accommodations_cache:
            return []
        
        recommendations = []
        
        for accommodation in self.accommodations_cache:
            score = 0.0
            score_components = {}
            
            # 1. 텍스트 유사도 (시설명, 편의시설)
            text_features = []
            if accommodation.get('facility_name'):
                text_features.append(accommodation['facility_name'])
            if accommodation.get('amenities'):
                text_features.append(accommodation['amenities'])
            if accommodation.get('facility_type'):
                text_features.append(accommodation['facility_type'])
            
            accommodation_text = ' '.join(text_features)
            text_similarity = self.calculate_text_similarity(query, accommodation_text)
            score += text_similarity * 0.4
            score_components['text_similarity'] = text_similarity
            
            # 2. 수용인원 유사도
            if target_capacity and accommodation.get('capacity_standard'):
                capacity_similarity = self.calculate_capacity_similarity(
                    target_capacity, accommodation['capacity_standard']
                )
                score += capacity_similarity * 0.3
                score_components['capacity_similarity'] = capacity_similarity
            
            # 3. 가격 유사도
            if target_price and accommodation.get('price_off_weekday'):
                price_similarity = self.calculate_price_similarity(
                    target_price, accommodation['price_off_weekday']
                )
                score += price_similarity * 0.2
                score_components['price_similarity'] = price_similarity
            
            # 4. 지역 필터링
            location_match = True
            if location_filter:
                location_match = (location_filter.lower() in 
                                (accommodation.get('sido', '').lower() or 
                                 accommodation.get('forest_name', '').lower()))
                if location_match:
                    score += 0.1
                score_components['location_match'] = location_match
            
            # 추천 결과에 추가
            if score > 0.1:  # 최소 점수 임계값
                recommendation = {
                    'accommodation_id': accommodation['accommodation_id'],
                    'facility_name': accommodation['facility_name'],
                    'forest_name': accommodation['forest_name'],
                    'facility_type': accommodation['facility_type'],
                    'capacity_standard': accommodation['capacity_standard'],
                    'price_off_weekday': accommodation['price_off_weekday'],
                    'amenities': accommodation['amenities'],
                    'sido': accommodation['sido'],
                    'address': accommodation['address'],
                    'similarity_score': round(score, 3),
                    'score_components': score_components
                }
                recommendations.append(recommendation)
        
        # 점수순 정렬 및 상위 K개 반환
        recommendations.sort(key=lambda x: x['similarity_score'], reverse=True)
        return recommendations[:top_k]
    
    def get_trending_accommodations(self, top_k: int = 5) -> List[Dict]:
        """인기 숙박시설 추천 (간단한 점수 기반)"""
        trending = []
        
        for accommodation in self.accommodations_cache:
            # 간단한 인기도 점수 계산
            popularity_score = 0.0
            
            # 시설 타입별 가중치
            facility_type = accommodation.get('facility_type', '').lower()
            if '펜션' in facility_type or '콘도' in facility_type:
                popularity_score += 0.3
            elif '초가' in facility_type or '통나무' in facility_type:
                popularity_score += 0.4
            elif '휴양관' in facility_type:
                popularity_score += 0.2
            
            # 편의시설 가중치
            amenities = accommodation.get('amenities', '')
            if amenities:
                amenity_count = len(amenities.split(';'))
                popularity_score += min(amenity_count * 0.05, 0.3)
            
            # 수용인원 가중치 (가족 단위 선호)
            capacity = accommodation.get('capacity_standard', 0)
            if 4 <= capacity <= 8:
                popularity_score += 0.2
            
            if popularity_score > 0.1:
                trending.append({
                    'accommodation_id': accommodation['accommodation_id'],
                    'facility_name': accommodation['facility_name'],
                    'forest_name': accommodation['forest_name'],
                    'facility_type': accommodation['facility_type'],
                    'capacity_standard': accommodation['capacity_standard'],
                    'price_off_weekday': accommodation['price_off_weekday'],
                    'address': accommodation['address'],
                    'sido': accommodation['sido'],
                    'popularity_score': round(popularity_score, 3)
                })
        
        trending.sort(key=lambda x: x['popularity_score'], reverse=True)
        return trending[:top_k]
    
    def get_recommendations(self, query: str, preferences: Dict = None) -> List[Dict]:
        """AI 추천 API용 메서드"""
        if not preferences:
            preferences = {}
        
        # 쿼리에서 인원수 추출 시도
        target_capacity = preferences.get('capacity')
        if not target_capacity and query:
            # "4인 가족", "6명", "8인용" 등에서 숫자 추출
            import re
            capacity_match = re.search(r'(\d+)(?:인|명|인용)', query)
            if capacity_match:
                target_capacity = int(capacity_match.group(1))
        
        # 가격 정보 추출
        target_price = preferences.get('price')
        
        # 지역 정보 추출
        location_filter = preferences.get('location')
        
        # 추천 실행
        results = self.search_accommodations(
            query=query,
            target_capacity=target_capacity,
            target_price=target_price,
            location_filter=location_filter,
            top_k=preferences.get('top_k', 5)
        )
        
        # 결과가 없을 경우 인기 추천으로 대체
        if not results:
            results = self.get_trending_accommodations(top_k=5)
            for result in results:
                result['similarity_score'] = result.get('popularity_score', 0)
        
        return results


def test_basic_recommendation_system():
    """기본 추천 시스템 테스트"""
    print("🤖 HyurimBot 기본 추천 시스템 테스트 시작")
    print("=" * 60)
    
    # 데이터베이스 경로 설정
    project_root = Path(__file__).parent
    db_path = project_root / "database" / "hyurimbot.db"
    
    if not db_path.exists():
        print(f"❌ 데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        return False
    
    # 추천 엔진 초기화
    engine = BasicRecommendationEngine(str(db_path))
    
    if not engine.accommodations_cache:
        print("❌ 숙박시설 데이터가 없습니다.")
        return False
    
    print(f"✅ 추천 엔진 초기화 완료 ({len(engine.accommodations_cache)}개 시설)")
    print()
    
    # 테스트 케이스 1: 자연어 검색
    print("📋 테스트 1: 자연어 검색 - '가족 여행 펜션 편의시설'")
    results1 = engine.search_accommodations(
        query="가족 여행 펜션 편의시설",
        target_capacity=6,
        target_price=100000,
        top_k=3
    )
    
    if results1:
        for i, result in enumerate(results1, 1):
            print(f"  {i}위. {result['facility_name']} ({result['forest_name']})")
            print(f"      유형: {result['facility_type']}, 인원: {result['capacity_standard']}명")
            print(f"      가격: {result['price_off_weekday']:,}원, 점수: {result['similarity_score']}")
            print(f"      편의시설: {result['amenities'][:50]}...")
            print()
    else:
        print("  ❌ 검색 결과가 없습니다.")
    
    # 테스트 케이스 2: 제주 지역 필터
    print("📋 테스트 2: 지역 필터링 - '제주' 지역")
    results2 = engine.search_accommodations(
        query="초가 전통",
        location_filter="제주",
        top_k=3
    )
    
    if results2:
        for i, result in enumerate(results2, 1):
            print(f"  {i}위. {result['facility_name']} ({result['forest_name']})")
            print(f"      지역: {result['sido']}, 점수: {result['similarity_score']}")
            print()
    else:
        print("  ❌ 검색 결과가 없습니다.")
    
    # 테스트 케이스 3: 인기 추천
    print("📋 테스트 3: 인기 숙박시설 추천")
    trending = engine.get_trending_accommodations(top_k=5)
    
    if trending:
        for i, result in enumerate(trending, 1):
            print(f"  {i}위. {result['facility_name']} ({result['forest_name']})")
            print(f"      유형: {result['facility_type']}, 인기도: {result['popularity_score']}")
            print()
    else:
        print("  ❌ 인기 추천 결과가 없습니다.")
    
    # 통계 정보
    print("📊 추천 시스템 통계")
    print(f"  • 총 숙박시설: {len(engine.accommodations_cache)}개")
    
    # 시설 유형별 분포
    facility_types = {}
    for acc in engine.accommodations_cache:
        facility_type = acc.get('facility_type', '기타')
        facility_types[facility_type] = facility_types.get(facility_type, 0) + 1
    
    print("  • 시설 유형별 분포:")
    for facility_type, count in sorted(facility_types.items(), key=lambda x: x[1], reverse=True):
        print(f"    - {facility_type}: {count}개")
    
    print("\n🎉 기본 추천 시스템 테스트 완료!")
    return True


if __name__ == "__main__":
    success = test_basic_recommendation_system()
    exit(0 if success else 1)