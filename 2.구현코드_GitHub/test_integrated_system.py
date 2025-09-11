#!/usr/bin/env python3
"""
HyurimBot 통합 시스템 테스트
Flask 앱 없이 직접 추천 엔진을 테스트합니다.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_basic_recommendation import BasicRecommendationEngine
from pathlib import Path
import json

def test_integrated_recommendation_system():
    """통합 추천 시스템 테스트"""
    print("🤖 HyurimBot 통합 시스템 테스트 시작")
    print("=" * 60)
    
    # 데이터베이스 경로 설정
    project_root = Path(__file__).parent
    db_path = project_root / "database" / "hyurimbot.db"
    
    if not db_path.exists():
        print(f"❌ 데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        return False
    
    # 추천 엔진 초기화
    engine = BasicRecommendationEngine(str(db_path))
    
    # 테스트 케이스들
    test_cases = [
        {
            "query": "4인 가족 넓은 객실",
            "preferences": {"capacity": 4, "price": 100000},
            "description": "4인 가족을 위한 넓은 객실 추천"
        },
        {
            "query": "편의시설 좋은 펜션",
            "preferences": {"capacity": 6},
            "description": "편의시설이 완비된 펜션"
        },
        {
            "query": "조용한 휴양",
            "preferences": {"price": 80000},
            "description": "조용한 휴양을 위한 숙박시설"
        }
    ]
    
    print(f"✅ 추천 엔진 초기화 완료 ({len(engine.accommodations_cache)}개 시설)")
    print()
    
    # 각 테스트 케이스 실행
    for i, test_case in enumerate(test_cases, 1):
        print(f"📋 테스트 {i}: {test_case['description']}")
        print(f"   쿼리: '{test_case['query']}'")
        print(f"   선호도: {test_case['preferences']}")
        
        # 추천 실행
        results = engine.get_recommendations(
            query=test_case['query'],
            preferences=test_case['preferences']
        )
        
        if results:
            print(f"   🎯 {len(results)}개 추천 결과:")
            for j, result in enumerate(results[:3], 1):  # 상위 3개만 표시
                print(f"     {j}위. {result['facility_name']} ({result['forest_name']})")
                print(f"         유형: {result.get('facility_type', 'N/A')}, "
                      f"인원: {result.get('capacity_standard', 'N/A')}명, "
                      f"가격: {result.get('price_off_weekday', 'N/A'):,}원")
                print(f"         점수: {result.get('similarity_score', 0):.3f}")
        else:
            print("   ❌ 추천 결과가 없습니다.")
        print()
    
    # 시스템 상태 정보
    print("📊 시스템 상태")
    print(f"   • 총 숙박시설: {len(engine.accommodations_cache)}개")
    print(f"   • 평균 가격: {sum(acc.get('price_off_weekday', 0) for acc in engine.accommodations_cache if acc.get('price_off_weekday')) / len([acc for acc in engine.accommodations_cache if acc.get('price_off_weekday')]):,.0f}원")
    
    # 시설 유형별 분포
    facility_types = {}
    for acc in engine.accommodations_cache:
        facility_type = acc.get('facility_type', '기타')
        facility_types[facility_type] = facility_types.get(facility_type, 0) + 1
    
    print("   • 시설 유형별 분포 (상위 5개):")
    for facility_type, count in sorted(facility_types.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"     - {facility_type}: {count}개")
    
    print("\n🎉 통합 시스템 테스트 완료!")
    return True

def test_api_simulation():
    """API 호출 시뮬레이션 테스트"""
    print("\n🔄 API 시뮬레이션 테스트")
    print("=" * 40)
    
    # 추천 엔진 초기화
    project_root = Path(__file__).parent
    db_path = project_root / "database" / "hyurimbot.db"
    engine = BasicRecommendationEngine(str(db_path))
    
    # API 호출과 같은 형태로 테스트
    api_request = {
        "query": "4인 가족 넓은 객실",
        "preferences": {
            "capacity": 4,
            "price": 100000,
            "top_k": 5
        }
    }
    
    print(f"📤 API 요청: {json.dumps(api_request, ensure_ascii=False, indent=2)}")
    
    # 추천 실행
    recommendations = engine.get_recommendations(
        query=api_request["query"],
        preferences=api_request["preferences"]
    )
    
    # API 응답 형태로 포맷
    api_response = {
        "success": True,
        "query": api_request["query"],
        "total_results": len(recommendations),
        "recommendations": []
    }
    
    for rec in recommendations:
        api_response["recommendations"].append({
            "accommodation_id": rec.get("accommodation_id"),
            "facility_name": rec.get("facility_name"),
            "forest_name": rec.get("forest_name"),
            "facility_type": rec.get("facility_type"),
            "capacity_standard": rec.get("capacity_standard"),
            "price_off_weekday": rec.get("price_off_weekday"),
            "similarity_score": rec.get("similarity_score"),
            "amenities": rec.get("amenities", "")[:100] + "..." if rec.get("amenities", "") else ""
        })
    
    print(f"📥 API 응답: {json.dumps(api_response, ensure_ascii=False, indent=2)}")
    print(f"✅ API 시뮬레이션 성공!")

if __name__ == "__main__":
    # 메인 테스트 실행
    success = test_integrated_recommendation_system()
    if success:
        test_api_simulation()
    
    exit(0 if success else 1)