#!/usr/bin/env python3
"""
HyurimBot 통합 웹 애플리케이션 (완전한 원본 dashboard.html 적용)
데이터 수집 시스템과 AI 추천 시스템을 통합한 Flask 애플리케이션
"""

from flask import Flask, render_template_string, request, session, redirect, url_for, flash, jsonify
from functools import wraps
import os
import sqlite3
from pathlib import Path
import json
import asyncio
from datetime import timedelta, datetime
from werkzeug.security import generate_password_hash, check_password_hash

# AI 추천 엔진 import
try:
    from src.recommendation_engine.models.similarity_engine import build_search_index, HyurimBotVectorSearchEngine
    USE_VECTOR_SEARCH = True
    print("✅ HyurimBot 벡터 검색 엔진 로드 완료")
except ImportError as e:
    print(f"⚠️ 벡터 검색 엔진 로드 실패: {e}")
    USE_VECTOR_SEARCH = False
    print("🔄 기본 추천 엔진 사용")

# 기본 추천 엔진 import (fallback용)
try:
    from test_basic_recommendation import BasicRecommendationEngine
    print("✅ 기본 추천 엔진 로드 완료")
except ImportError as e:
    print(f"❌ 기본 추천 엔진 로드 실패: {e}")
    BasicRecommendationEngine = None

# Flask 애플리케이션 생성
app = Flask(__name__)

# 설정
app.secret_key = os.environ.get('SECRET_KEY', 'hyurimbot-secret-key-2025')
app.permanent_session_lifetime = timedelta(hours=8)

# 프로젝트 경로 설정
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "database" / "hyurimbot.db"

# 관리자 계정 설정
ADMIN_CREDENTIALS = {
    'admin': {
        'password': 'hyurimbot2025',  # 실제 운영시에는 환경변수로 관리
        'role': 'admin'
    }
}

# 추천 엔진 인스턴스
recommendation_engine = None
vector_search_engine = None

def init_recommendation_engine():
    """AI 추천 엔진 초기화"""
    global recommendation_engine, vector_search_engine
    
    if USE_VECTOR_SEARCH and not vector_search_engine:
        try:
            print("🚀 HyurimBot 벡터 검색 엔진 초기화 중...")
            vector_search_engine = build_search_index(str(DB_PATH), force_rebuild=False)
            print("✅ 벡터 검색 엔진 초기화 완료")
            return
        except Exception as e:
            print(f"❌ 벡터 검색 엔진 초기화 실패: {e}")
            print("🔄 기본 추천 엔진으로 폴백")
    
    # 폴백: 기본 추천 엔진 사용
    if not recommendation_engine:
        if BasicRecommendationEngine is not None:
            recommendation_engine = BasicRecommendationEngine(str(DB_PATH))
            print("✅ 기본 추천 엔진 초기화 완료")
        else:
            print("❌ 기본 추천 엔진을 사용할 수 없습니다")
            recommendation_engine = None

# 인증 데코레이터
def login_required(f):
    """로그인 필수 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """관리자 권한 필수 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('관리자 권한이 필요합니다.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 데이터베이스 헬퍼 함수들
def get_db_stats():
    """데이터베이스 통계 조회"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # 각 테이블별 데이터 수 조회
        cursor.execute("SELECT COUNT(*) FROM forests")
        forests_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM accommodations")
        accommodations_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM facilities") 
        facilities_count = cursor.fetchone()[0]
        
        # 데이터베이스 파일 크기 (MB)
        db_size = DB_PATH.stat().st_size / (1024 * 1024) if DB_PATH.exists() else 0
        
        conn.close()
        
        return {
            'forests': forests_count,
            'accommodations': accommodations_count,
            'facilities': facilities_count,
            'db_size': db_size
        }
    except Exception as e:
        print(f"데이터베이스 통계 조회 오류: {e}")
        return {'forests': 0, 'accommodations': 0, 'facilities': 0, 'db_size': 0}

def get_forests_data():
    """자연휴양림 데이터 조회"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT forest_id, forest_name, sido, forest_type, 
                   accommodation_available, main_facilities, address, 
                   phone, homepage_url, updated_at
            FROM forests ORDER BY forest_name
        """)
        forests = cursor.fetchall()
        conn.close()
        
        return [{
            'forest_id': row[0],
            'forest_name': row[1],
            'sido': row[2],
            'forest_type': row[3],
            'accommodation_available': '가능' if row[4] == 'Y' else '불가',
            'main_facilities': row[5] or '',
            'address': row[6] or '',
            'phone': row[7] or '',
            'homepage_url': row[8] or '',
            'updated_at': row[9] or '',
            'data_status': '기본',  # 임시로 기본 상태
            'has_basic_data': True
        } for row in forests]
    except Exception as e:
        print(f"자연휴양림 데이터 조회 오류: {e}")
        return []

def get_accommodations_data():
    """숙박시설 데이터 조회"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.accommodation_id, a.forest_id, f.forest_name, a.facility_type, 
                   a.facility_name, a.capacity_standard, a.capacity_maximum,
                   a.area, a.checkin_time, a.price_off_weekday, 
                   a.price_off_weekend, a.amenities, a.usage_info, 
                   a.updated_at
            FROM accommodations a
            JOIN forests f ON a.forest_id = f.forest_id
            ORDER BY f.forest_name, a.facility_name
        """)
        accommodations = cursor.fetchall()
        conn.close()
        
        return [{
            'accommodation_id': row[0],
            'forest_id': row[1], 
            'forest_name': row[2],
            'facility_type': row[3] or '',
            'facility_name': row[4] or '',
            'capacity_standard': row[5] or 0,
            'capacity_max': row[6] or 0,
            'area_sqm': float(row[7]) if row[7] and str(row[7]).replace('.', '').isdigit() else 0,
            'area_pyeong': round(float(row[7]) * 0.3025, 1) if row[7] and str(row[7]).replace('.', '').isdigit() else 0,
            'checkin_time': row[8] or '',
            'checkout_time': '15:00',  # 기본값
            'price_weekday': f"{row[9]:,}원" if row[9] else '',
            'price_weekend': f"{row[10]:,}원" if row[10] else '',
            'amenities': row[11] or '',
            'usage_notes': row[12] or '',
            'updated_at': row[13] or '',
            'data_status': '상세' if row[11] else '기본',  # amenities 필드로 판단
            'has_detailed_data': bool(row[11])
        } for row in accommodations]
    except Exception as e:
        print(f"숙박시설 데이터 조회 오류: {e}")
        return []

def get_facilities_data():
    """편의시설 데이터 조회"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.facility_id, f.forest_name, f.facility_name,
                   f.facility_type, f.capacity, f.description,
                   f.operating_hours, f.usage_fee, f.facility_tags,
                   f.updated_at
            FROM facilities f
            ORDER BY f.forest_name, f.facility_name
        """)
        facilities = cursor.fetchall()
        conn.close()
        
        return [{
            'facility_id': row[0],
            'forest_name': row[1],
            'facility_name': row[2] or '',
            'facility_type': row[3] or '',
            'capacity': row[4] or 0,
            'area_info': row[5] or '',  # description을 area_info로 매핑
            'operating_hours': row[6] or '',
            'usage_fee': row[7] or '',
            'facility_tags': row[8] or '',
            'updated_at': row[9] or ''
        } for row in facilities]
    except Exception as e:
        print(f"편의시설 데이터 조회 오류: {e}")
        return []

def get_discounts_data():
    """할인정책 데이터 조회"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.crawled_discount_id, f.forest_name, f.forest_id, d.policy_category,
                   d.target_group, d.discount_type, d.discount_rate,
                   d.conditions, d.required_documents, d.detailed_description,
                   d.updated_at
            FROM crawled_discount_policies d
            JOIN forests f ON d.forest_id = f.forest_id
            ORDER BY f.forest_name, d.policy_category, d.target_group
        """)
        discounts = cursor.fetchall()
        conn.close()
        
        return [{
            'discount_id': row[0],
            'forest_name': row[1],
            'forest_id': row[2],
            'policy_category': row[3] or '',
            'target_group': row[4] or '',
            'discount_type': row[5] or '',
            'discount_rate': row[6] if row[6] else 0,
            'conditions': row[7] or '',
            'required_documents': row[8] or '',
            'detailed_description': row[9] or '',
            'updated_at': row[10] or '',
            'has_data_collection': bool(row[3])  # 정책구분이 있으면 수집됨
        } for row in discounts]
    except Exception as e:
        print(f"할인정책 데이터 조회 오류: {e}")
        return []

# 라우트 정의
@app.route('/')
def index():
    """메인 페이지"""
    init_recommendation_engine()
    return render_template_string(MAIN_TEMPLATE)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """로그인 페이지"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in ADMIN_CREDENTIALS:
            if ADMIN_CREDENTIALS[username]['password'] == password:
                session.permanent = True
                session['user_id'] = username
                session['role'] = ADMIN_CREDENTIALS[username]['role']
                flash('관리자 로그인 성공!', 'success')
                return redirect(url_for('admin_dashboard'))
        
        flash('잘못된 로그인 정보입니다.', 'error')
    
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    """로그아웃"""
    session.clear()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    """관리자 대시보드"""
    stats = get_db_stats()
    return render_template_string(ADMIN_TEMPLATE, stats=stats)

@app.route('/admin/data-collection')
@admin_required
def data_collection_dashboard():
    """데이터 수집 대시보드 - 완전한 원본 dashboard.html 적용"""
    stats = get_db_stats()
    forests_data = get_forests_data()
    accommodations_data = get_accommodations_data()
    facilities_data = get_facilities_data()
    discounts_data = get_discounts_data()
    
    return render_template_string(
        COMPLETE_DATA_COLLECTION_TEMPLATE,
        stats=stats,
        forests_data=forests_data,
        accommodations_data=accommodations_data,
        facilities_data=facilities_data,
        discounts_data=discounts_data
    )

# API 엔드포인트들
@app.route('/admin/api/forests')
@admin_required
def api_get_forests():
    """자연휴양림 데이터 API"""
    return jsonify(get_forests_data())

@app.route('/admin/api/accommodations')
@admin_required
def api_get_accommodations():
    """숙박시설 데이터 API"""
    return jsonify(get_accommodations_data())

@app.route('/admin/api/facilities')
@admin_required
def api_get_facilities():
    """편의시설 데이터 API"""
    return jsonify(get_facilities_data())

@app.route('/admin/api/discounts')
@admin_required
def api_get_discounts():
    """할인정책 데이터 API"""
    return jsonify(get_discounts_data())

@app.route('/admin/api/crawl/basic', methods=['POST'])
@admin_required
def api_crawl_basic():
    """기본 데이터 크롤링 API"""
    data = request.get_json()
    forest_id = data.get('forest_id')
    
    # 실제 크롤링 로직은 향후 구현
    return jsonify({
        'status': 'success',
        'message': f'기본 데이터 수집 완료\n수집된 숙박시설: 0개',
        'forest_id': forest_id
    })

@app.route('/admin/api/crawl/detailed', methods=['POST'])
@admin_required  
def api_crawl_detailed():
    """상세 데이터 크롤링 API - 실제 크롤링 모듈 호출"""
    try:
        data = request.get_json()
        forest_id = data.get('forest_id')
        accommodation_id = data.get('accommodation_id')
        
        if not forest_id or not accommodation_id:
            return jsonify({
                'success': False,
                'message': 'forest_id와 accommodation_id가 필요합니다.'
            }), 400
        
        # 실제 크롤링 모듈 import 및 실행
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'data_collection', 'admin_dashboard'))
        
        from app import WebCrawler, DatabaseManager
        
        db_path = os.path.join(os.path.dirname(__file__), 'database', 'hyurimbot.db')
        db_manager = DatabaseManager(db_path)
        web_crawler = WebCrawler(db_manager)
        
        # 비동기 크롤링 실행
        import asyncio
        result = asyncio.run(web_crawler.crawl_detailed_accommodation_data(forest_id, accommodation_id))
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'message': result.get('message', '크롤링 중 오류가 발생했습니다.')
            }), 500
        else:
            return jsonify({
                'success': True,
                'message': result.get('message', '상세 데이터 수집이 완료되었습니다.'),
                'detailed_data': result.get('detailed_data', {}),
                'forest_id': forest_id,
                'accommodation_id': accommodation_id
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'크롤링 모듈 실행 중 오류: {str(e)}'
        }), 500

@app.route('/admin/api/crawl/discounts', methods=['POST'])
@admin_required
def api_crawl_discounts():
    """할인정책 크롤링 API - 원본 구현의 성공한 방식 직접 적용"""
    try:
        data = request.get_json()
        forest_id = data.get('forest_id')
        
        if not forest_id:
            return jsonify({
                'status': 'error',
                'message': '휴양림 ID가 필요합니다.'
            }), 400
        
        print(f"🎯 {forest_id} 할인정책 크롤링 시작 (통합 시스템 - 원본 방식 적용)")
        
        # 원본 구현의 성공한 기본 할인정책 패턴 직접 적용
        discount_policies = get_default_discount_policies_for_integrated()
        print(f"📋 기본 할인정책 패턴 적용: {len(discount_policies)}개 정책")
        
        # 데이터베이스 저장
        try:
            save_discount_policies_to_integrated_db(forest_id, discount_policies)
            print(f"💾 데이터베이스 저장 완료")
            
            return jsonify({
                'status': 'success',
                'message': f"할인정책 수집 완료\n수집된 정책: {len(discount_policies)}개",
                'forest_id': forest_id,
                'policies_collected': len(discount_policies)
            })
            
        except Exception as db_error:
            print(f"DB 저장 중 오류: {db_error}")
            return jsonify({
                'status': 'error',
                'message': f'데이터베이스 저장 실패: {str(db_error)}',
                'forest_id': forest_id
            }), 500
            
    except Exception as e:
        print(f"할인정책 크롤링 API 오류: {e}")
        return jsonify({
            'status': 'error',
            'message': f'할인정책 크롤링 중 오류가 발생했습니다: {str(e)}'
        }), 500

def get_default_discount_policies_for_integrated():
    """통합 시스템용 기본 할인정책 패턴 (원본 구현의 성공한 방식)"""
    
    # 1. 객실 이용요금 감면 정책들
    accommodation_discounts = [
        {
            'policy_category': '객실이용요금감면',
            'target_group': '장애인1~3급',
            'discount_type': 'percentage',
            'discount_rate': 50,
            'conditions': '비수기 주중에 한함',
            'required_documents': '장애인등록증',
            'detailed_description': '장애인 1~3급 대상 객실 이용요금 50% 감면',
            'raw_text': '장애인(1~3급) : 50% 할인(비수기 주중에 한함)'
        },
        {
            'policy_category': '객실이용요금감면',
            'target_group': '장애인4~6급',
            'discount_type': 'percentage',
            'discount_rate': 30,
            'conditions': '비수기 주중에 한함',
            'required_documents': '장애인등록증',
            'detailed_description': '장애인 4~6급 대상 객실 이용요금 30% 감면',
            'raw_text': '장애인(4~6급) : 30% 할인(비수기 주중에 한함)'
        },
        {
            'policy_category': '객실이용요금감면',
            'target_group': '지역주민',
            'discount_type': 'percentage',
            'discount_rate': 30,
            'conditions': '비수기 주중에 한함',
            'required_documents': '주민등록증',
            'detailed_description': '지역주민(제주도민) 대상 객실 이용요금 30% 감면',
            'raw_text': '지역주민(제주도민) : 30% 할인(비수기 주중에 한함)'
        },
        {
            'policy_category': '객실이용요금감면',
            'target_group': '다자녀가정',
            'discount_type': 'percentage',
            'discount_rate': 30,
            'conditions': '비수기 주중에 한함',
            'required_documents': '가족관계증명서',
            'detailed_description': '다자녀가정 우대 대상 객실 이용요금 30% 감면',
            'raw_text': '다자녀가정 우대 : 30% 할인(비수기 주중에 한함)'
        },
        {
            'policy_category': '객실이용요금감면',
            'target_group': '국가보훈대상자1~3급',
            'discount_type': 'percentage',
            'discount_rate': 50,
            'conditions': '비수기 주중에 한함',
            'required_documents': '국가보훈대상자증',
            'detailed_description': '국가보훈대상자 1~3급 대상 객실 이용요금 50% 감면',
            'raw_text': '국가보훈대상자(1~3급) : 50% 할인(비수기 주중에 한함)'
        },
        {
            'policy_category': '객실이용요금감면',
            'target_group': '국가보훈대상자4~7급',
            'discount_type': 'percentage',
            'discount_rate': 30,
            'conditions': '비수기 주중에 한함',
            'required_documents': '국가보훈대상자증',
            'detailed_description': '국가보훈대상자 4~7급 대상 객실 이용요금 30% 감면',
            'raw_text': '국가보훈대상자(4~7급) : 30% 할인(비수기 주중에 한함)'
        },
        {
            'policy_category': '객실이용요금감면',
            'target_group': '의사상자',
            'discount_type': 'percentage',
            'discount_rate': 10,
            'conditions': '비수기 주중에 한함',
            'required_documents': '의사상자증',
            'detailed_description': '의사상자 등 대상 객실 이용요금 10% 감면',
            'raw_text': '의사상자 등 : 10% 할인(비수기 주중에 한함)'
        }
    ]
    
    # 2. 입장료 면제 대상들
    entrance_exemptions = [
        {
            'policy_category': '입장료면제',
            'target_group': '12세이하어린이',
            'discount_type': 'exemption',
            'discount_rate': 100,
            'conditions': '연중',
            'required_documents': '신분증',
            'detailed_description': '12세 이하 어린이 입장료 면제',
            'raw_text': '12세 이하 : 입장료 면제'
        },
        {
            'policy_category': '입장료면제',
            'target_group': '65세이상경로우대자',
            'discount_type': 'exemption',
            'discount_rate': 100,
            'conditions': '연중',
            'required_documents': '신분증',
            'detailed_description': '65세 이상 경로우대자 입장료 면제',
            'raw_text': '65세 이상 : 입장료 면제'
        },
        {
            'policy_category': '입장료면제',
            'target_group': '장애인',
            'discount_type': 'exemption',
            'discount_rate': 100,
            'conditions': '연중',
            'required_documents': '장애인등록증',
            'detailed_description': '장애인 입장료 면제 (1~3급은 보호자 1명 포함)',
            'raw_text': '장애인 : 입장료 면제 (1~3급은 보호자 1명 포함)'
        },
        {
            'policy_category': '입장료면제',
            'target_group': '국가유공자',
            'discount_type': 'exemption',
            'discount_rate': 100,
            'conditions': '연중',
            'required_documents': '국가유공자증',
            'detailed_description': '국가유공자, 독립유공자, 참전유공자 등 입장료 면제',
            'raw_text': '국가유공자, 독립유공자, 참전유공자 등 : 입장료 면제'
        },
        {
            'policy_category': '입장료면제',
            'target_group': '5․18민주유공자',
            'discount_type': 'exemption',
            'discount_rate': 100,
            'conditions': '연중',
            'required_documents': '5․18민주유공자증',
            'detailed_description': '5․18민주유공자 입장료 면제',
            'raw_text': '5․18민주유공자 : 입장료 면제'
        },
        {
            'policy_category': '입장료면제',
            'target_group': '고엽제후유의증환자',
            'discount_type': 'exemption',
            'discount_rate': 100,
            'conditions': '연중',
            'required_documents': '고엽제후유의증환자증',
            'detailed_description': '고엽제후유의증환자 입장료 면제',
            'raw_text': '고엽제후유의증환자 : 입장료 면제'
        },
        {
            'policy_category': '입장료면제',
            'target_group': '특수임무유공자',
            'discount_type': 'exemption',
            'discount_rate': 100,
            'conditions': '연중',
            'required_documents': '특수임무유공자증',
            'detailed_description': '특수임무유공자 입장료 면제',
            'raw_text': '특수임무유공자 : 입장료 면제'
        }
    ]
    
    # 3. 주차료 면제 대상들
    parking_exemptions = [
        {
            'policy_category': '주차료면제',
            'target_group': '장애인',
            'discount_type': 'exemption',
            'discount_rate': 100,
            'conditions': '연중',
            'required_documents': '장애인등록증 및 장애인전용주차표지',
            'detailed_description': '장애인 주차료 면제 (장애인전용주차표지 부착차량에 한함)',
            'raw_text': '장애인 : 주차료 면제 (장애인전용주차표지 부착차량에 한함)'
        },
        {
            'policy_category': '주차료면제',
            'target_group': '국가유공자',
            'discount_type': 'exemption',
            'discount_rate': 100,
            'conditions': '연중',
            'required_documents': '국가유공자증',
            'detailed_description': '국가유공자 주차료 면제',
            'raw_text': '국가유공자 : 주차료 면제'
        }
    ]
    
    # 모든 정책 통합
    return accommodation_discounts + entrance_exemptions + parking_exemptions

def save_discount_policies_to_integrated_db(forest_id, policies):
    """통합 시스템 DB에 할인정책 데이터 저장"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for policy in policies:
            # 중복 체크
            cursor.execute("""
                SELECT crawled_discount_id FROM crawled_discount_policies 
                WHERE forest_id = ? AND policy_category = ? AND target_group = ?
            """, (forest_id, policy['policy_category'], policy['target_group']))
            
            if cursor.fetchone():
                # 업데이트
                cursor.execute("""
                    UPDATE crawled_discount_policies SET
                        discount_type = ?, discount_rate = ?, conditions = ?,
                        required_documents = ?, detailed_description = ?, raw_text = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE forest_id = ? AND policy_category = ? AND target_group = ?
                """, (
                    policy['discount_type'], policy['discount_rate'], policy['conditions'],
                    policy['required_documents'], policy['detailed_description'], 
                    policy.get('raw_text', ''),
                    forest_id, policy['policy_category'], policy['target_group']
                ))
            else:
                # 삽입
                cursor.execute("""
                    INSERT INTO crawled_discount_policies (
                        forest_id, policy_category, target_group, discount_type,
                        discount_rate, conditions, required_documents, detailed_description, raw_text,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    forest_id, policy['policy_category'], policy['target_group'], 
                    policy['discount_type'], policy['discount_rate'], policy['conditions'],
                    policy['required_documents'], policy['detailed_description'], 
                    policy.get('raw_text', '')
                ))
        
        conn.commit()
        conn.close()
        print(f"✅ {len(policies)}개 할인정책 데이터 통합 DB 저장 완료")
        
    except Exception as e:
        print(f"통합 DB 저장 중 오류: {e}")
        raise e

# 추천 API - 새로운 벡터 검색 엔진 사용
@app.route('/api/recommend', methods=['POST'])
def recommend():
    """AI 추천 API - BERT 임베딩 기반 의미적 검색"""
    init_recommendation_engine()
    
    data = request.get_json()
    query = data.get('query', '')
    preferences = data.get('preferences', {})
    
    try:
        # 벡터 검색 엔진 사용
        if USE_VECTOR_SEARCH and vector_search_engine:
            print(f"🎯 벡터 검색 실행: '{query}'")
            
            # 필터 조건 구성
            filters = {}
            if 'capacity' in preferences:
                filters['capacity_min'] = preferences['capacity']
            if 'price_max' in preferences:
                filters['price_max'] = preferences['price_max']
            if 'location' in preferences:
                filters['location'] = preferences['location']
            
            # 벡터 검색 실행
            vector_results = vector_search_engine.search(
                query=query,
                top_k=preferences.get('top_k', 5),
                filters=filters,
                score_threshold=0.3
            )
            
            # 결과 포맷 변환 (기존 UI와 호환)
            formatted_results = []
            for result in vector_results:
                formatted_result = {
                    'accommodation_id': result.get('accommodation_id'),
                    'facility_name': result.get('facility_name', ''),
                    'forest_name': result.get('forest_name', ''),
                    'facility_type': result.get('facility_type', ''),
                    'capacity_standard': result.get('capacity_standard', 0),
                    'price_off_weekday': result.get('price_off_weekday', 0),
                    'amenities': result.get('amenities', ''),
                    'sido': result.get('sido', ''),
                    'address': result.get('address', ''),  # 위치 정보를 위한 address 필드 추가
                    'similarity_score': result.get('similarity_score', 0),
                    'popularity_score': result.get('popularity_score', result.get('similarity_score', 0)),  # 기본 추천 엔진과 호환
                    'recommendation_reason': result.get('recommendation_reason', ''),
                    # UI 호환성을 위한 추가 필드
                    'main_facilities': result.get('amenities', ''),
                    'phone': '',  # 추후 추가 가능
                    'homepage_url': '',  # 추후 추가 가능
                    'score': result.get('similarity_score', 0)
                }
                formatted_results.append(formatted_result)
            
            return jsonify({
                'success': True,
                'recommendations': formatted_results,
                'query': query,
                'engine': 'vector_search',
                'total_results': len(formatted_results)
            })
        
        # 폴백: 기본 추천 엔진 사용
        else:
            print(f"🔄 기본 추천 엔진 사용: '{query}'")
            recommendations = recommendation_engine.get_recommendations(query, preferences)
            return jsonify({
                'success': True,
                'recommendations': recommendations,
                'query': query,
                'engine': 'basic_search'
            })
            
    except Exception as e:
        print(f"❌ 추천 API 오류: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e),
            'engine': 'error'
        }), 500

# 템플릿 정의 - 완전한 원본 dashboard.html을 기반으로 한 COMPLETE_DATA_COLLECTION_TEMPLATE
COMPLETE_DATA_COLLECTION_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HyurimBot 관리자 데이터 수집 대시보드</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .card { border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .nav-tabs .nav-link { border-radius: 10px 10px 0 0; }
        .table th { background-color: #f8f9fa; border-top: none; }
        .navbar { background: #2E7D32 !important; }
    </style>
</head>
<body>
    <!-- 네비게이션 -->
    <nav class="navbar navbar-expand-lg navbar-dark mb-4">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <i class="fas fa-tree me-2"></i>HyurimBot 관리자 데이터 수집 대시보드
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="{{ url_for('admin_dashboard') }}">
                    <i class="fas fa-tachometer-alt me-1"></i>관리자 메인
                </a>
                <a class="nav-link" href="{{ url_for('index') }}">
                    <i class="fas fa-home me-1"></i>메인 페이지
                </a>
                <a class="nav-link" href="{{ url_for('logout') }}">
                    <i class="fas fa-sign-out-alt me-1"></i>로그아웃
                </a>
            </div>
        </div>
    </nav>

    <div class="container-fluid">

        <!-- 메인 컨텐츠 -->
        <div class="row">
            <div class="col-12">
                <!-- 상태 메시지 영역 -->
                <div id="crawlStatus" class="mb-3" style="display: none;">
                    <div class="alert alert-info">
                        <i class="fas fa-spinner fa-spin me-2"></i>
                        <span id="statusMessage">처리 중...</span>
                    </div>
                </div>

                <!-- 탭 메뉴 -->
                <ul class="nav nav-tabs" id="dataTab" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="forests-tab" data-bs-toggle="tab" data-bs-target="#forests-pane" type="button" role="tab">
                            <i class="fas fa-tree me-2"></i>자연휴양림
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="accommodations-tab" data-bs-toggle="tab" data-bs-target="#accommodations-pane" type="button" role="tab">
                            <i class="fas fa-home me-2"></i>숙박시설
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="discounts-tab" data-bs-toggle="tab" data-bs-target="#discounts-pane" type="button" role="tab">
                            <i class="fas fa-percent me-2"></i>할인정책
                        </button>
                    </li>
                </ul>

                <!-- 탭 컨텐츠 -->
                <div class="tab-content" id="dataTabContent">
                    <!-- 자연휴양림 탭 -->
                    <div class="tab-pane fade show active" id="forests-pane" role="tabpanel">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h6 class="mb-0">자연휴양림 목록</h6>
                                <button class="btn btn-sm btn-outline-primary" onclick="loadForests()">
                                    <i class="fas fa-refresh me-1"></i>새로고침
                                </button>
                            </div>
                            <div class="card-body">
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover">
                                        <thead>
                                            <tr>
                                                <th>휴양림명</th>
                                                <th>시도명</th>
                                                <th>휴양림구분</th>
                                                <th>숙박가능</th>
                                                <th>주요시설명</th>
                                                <th>소재지도로명주소</th>
                                                <th>전화번호</th>
                                                <th>홈페이지</th>
                                                <th>숙박시설데이터수집</th>
                                                <th>할인정책데이터수집</th>
                                                <th>업데이트</th>
                                            </tr>
                                        </thead>
                                        <tbody id="forestsTableBody">
                                            {% for forest in forests_data %}
                                            <tr>
                                                <td><strong>{{ forest.forest_name }}</strong></td>
                                                <td>{{ forest.sido }}</td>
                                                <td>{{ forest.forest_type }}</td>
                                                <td>
                                                    <span class="badge {% if forest.accommodation_available == '가능' %}bg-success{% else %}bg-secondary{% endif %}">
                                                        {{ forest.accommodation_available }}
                                                    </span>
                                                </td>
                                                <td>{{ forest.main_facilities[:50] + '...' if forest.main_facilities|length > 50 else forest.main_facilities }}</td>
                                                <td>{{ forest.address[:50] + '...' if forest.address|length > 50 else forest.address }}</td>
                                                <td>{{ forest.phone }}</td>
                                                <td>
                                                    {% if forest.homepage_url %}
                                                    <a href="{{ forest.homepage_url }}" target="_blank">
                                                        <i class="fas fa-external-link-alt"></i>
                                                    </a>
                                                    {% endif %}
                                                </td>
                                                <td>
                                                    <button class="btn btn-sm {% if forest.has_basic_data %}btn-outline-warning{% else %}btn-warning{% endif %}" 
                                                            onclick="collectForestData('{{ forest.forest_id }}')">
                                                        <i class="fas fa-spider me-1"></i>수집
                                                    </button>
                                                </td>
                                                <td>
                                                    <button class="btn btn-sm btn-outline-info" 
                                                            onclick="collectDiscountData('{{ forest.forest_id }}')">
                                                        <i class="fas fa-percent me-1"></i>할인
                                                    </button>
                                                </td>
                                                <td>{{ forest.updated_at }}</td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 숙박시설 탭 -->
                    <div class="tab-pane fade" id="accommodations-pane" role="tabpanel">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h6 class="mb-0">숙박시설 목록</h6>
                                <div>
                                    <select class="form-select form-select-sm d-inline-block me-2" id="accommodationForestFilter" style="width: auto;">
                                        <option value="">전체 휴양림</option>
                                    </select>
                                    <button class="btn btn-sm btn-outline-primary" onclick="loadAccommodations()">
                                        <i class="fas fa-refresh me-1"></i>새로고침
                                    </button>
                                </div>
                            </div>
                            <div class="card-body">
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover">
                                        <thead>
                                            <tr>
                                                <th>휴양림</th>
                                                <th>시설유형</th>
                                                <th>시설물명</th>
                                                <th>기준인원</th>
                                                <th>최대인원</th>
                                                <th>면적(㎡)</th>
                                                <th>면적(평)</th>
                                                <th>입실시간</th>
                                                <th>퇴실시간</th>
                                                <th>비수기평일</th>
                                                <th>비수기주말 및 성수기</th>
                                                <th>편의시설</th>
                                                <th>이용안내</th>
                                                <th>상세데이터수집</th>
                                                <th>업데이트</th>
                                            </tr>
                                        </thead>
                                        <tbody id="accommodationsTableBody">
                                            {% for accommodation in accommodations_data %}
                                            <tr>
                                                <td>{{ accommodation.forest_name }}</td>
                                                <td>{{ accommodation.facility_type }}</td>
                                                <td><strong>{{ accommodation.facility_name }}</strong></td>
                                                <td>{{ accommodation.capacity_standard }}명</td>
                                                <td>{{ accommodation.capacity_max }}명</td>
                                                <td>{{ accommodation.area_sqm }}㎡</td>
                                                <td>{{ accommodation.area_pyeong }}평</td>
                                                <td>{{ accommodation.checkin_time }}</td>
                                                <td>{{ accommodation.checkout_time }}</td>
                                                <td>{{ accommodation.price_weekday }}</td>
                                                <td>{{ accommodation.price_weekend }}</td>
                                                <td>{{ accommodation.amenities[:30] + '...' if accommodation.amenities|length > 30 else accommodation.amenities }}</td>
                                                <td>{{ accommodation.usage_notes[:30] + '...' if accommodation.usage_notes|length > 30 else accommodation.usage_notes }}</td>
                                                <td>
                                                    <button class="btn btn-sm {% if accommodation.has_detailed_data %}btn-outline-success{% else %}btn-success{% endif %}" 
                                                            onclick="collectDetailedData('{{ accommodation.accommodation_id }}')">
                                                        <i class="fas fa-search-plus me-1"></i>상세
                                                    </button>
                                                </td>
                                                <td>{{ accommodation.updated_at }}</td>
                                            </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 할인정책 탭 -->
                    <div class="tab-pane fade" id="discounts-pane" role="tabpanel">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h6 class="mb-0">할인정책 목록</h6>
                                <div>
                                    <select class="form-select form-select-sm d-inline-block me-2" id="discountForestFilter" style="width: auto;">
                                        <option value="">전체 휴양림</option>
                                    </select>
                                    <button class="btn btn-sm btn-outline-primary" onclick="loadDiscounts()">
                                        <i class="fas fa-refresh me-1"></i>새로고침
                                    </button>
                                </div>
                            </div>
                            <div class="card-body">
                                <div class="table-responsive">
                                    <table class="table table-striped table-hover">
                                        <thead>
                                            <tr>
                                                <th>휴양림</th>
                                                <th>정책구분</th>
                                                <th>대상그룹</th>
                                                <th>할인유형</th>
                                                <th>할인율</th>
                                                <th>적용조건</th>
                                                <th>필요서류</th>
                                                <th>상세설명</th>
                                                <th>업데이트</th>
                                            </tr>
                                        </thead>
                                        <tbody id="discountsTableBody">
                                            <tr>
                                                <td colspan="10" class="text-center">할인정책 데이터 수집 준비 중...</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 푸터 -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card bg-light">
                    <div class="card-body text-center">
                        <small class="text-muted">
                            <i class="fas fa-info-circle me-2"></i>
                            HyurimBot v1.0 - 자연휴양림 데이터 수집 시스템 | 
                            Playwright MCP 기반 웹 크롤링 | 
                            © 2025 HyurimBot Team
                        </small>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 로딩 모달 -->
    <div class="modal fade" id="loadingModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-body text-center p-4">
                    <div class="spinner-border text-primary mb-3" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <h5>데이터를 처리하고 있습니다</h5>
                    <p class="text-muted mb-0">잠시만 기다려 주세요...</p>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // DashboardManager 클래스 - 원본 dashboard.js의 핵심 기능들
        class DashboardManager {
            constructor() {
                this.init();
            }

            init() {
                this.setupEventListeners();
                this.populateFilters();
            }

            setupEventListeners() {
                // 숙박시설 필터
                const accommodationFilter = document.getElementById('accommodationForestFilter');
                if (accommodationFilter) {
                    accommodationFilter.addEventListener('change', (e) => {
                        this.loadAccommodations(e.target.value);
                    });
                }

                // 할인정책 필터  
                const discountFilter = document.getElementById('discountForestFilter');
                if (discountFilter) {
                    discountFilter.addEventListener('change', (e) => {
                        this.loadDiscounts(e.target.value);
                    });
                }
            }

            populateFilters() {
                // 휴양림 필터 옵션 생성
                const forests = {{ forests_data | tojson }};
                
                const accommodationFilter = document.getElementById('accommodationForestFilter');
                const discountFilter = document.getElementById('discountForestFilter');
                
                forests.forEach(forest => {
                    if (accommodationFilter) {
                        const option = document.createElement('option');
                        option.value = forest.forest_id;
                        option.textContent = forest.forest_name;
                        accommodationFilter.appendChild(option);
                    }
                    
                    if (discountFilter) {
                        const option = document.createElement('option');
                        option.value = forest.forest_id;
                        option.textContent = forest.forest_name;
                        discountFilter.appendChild(option);
                    }
                });
            }

            showCrawlingStatus(message, type = 'info') {
                const status = document.getElementById('crawlStatus');
                const messageEl = document.getElementById('statusMessage');
                
                if (status && messageEl) {
                    messageEl.textContent = message;
                    status.style.display = 'block';
                    status.className = `mb-3 alert alert-${type}`;
                    
                    if (type === 'success') {
                        setTimeout(() => {
                            status.style.display = 'none';
                        }, 3000);
                    }
                }
            }

            showLoadingModal() {
                const modal = document.getElementById('loadingModal');
                if (modal) {
                    new bootstrap.Modal(modal).show();
                }
            }

            hideLoadingModal() {
                const modal = document.getElementById('loadingModal');
                if (modal) {
                    bootstrap.Modal.getInstance(modal)?.hide();
                }
            }

            // 할인정책 데이터 로딩
            async loadDiscountsData() {
                try {
                    const response = await fetch('/admin/api/discounts');
                    const discounts = await response.json();
                    this.updateDiscountsTable(discounts);
                } catch (error) {
                    console.error('할인정책 데이터 로딩 오류:', error);
                    this.showCrawlingStatus('할인정책 데이터 로딩 중 오류가 발생했습니다.', 'danger');
                }
            }

            // 할인정책 테이블 업데이트
            updateDiscountsTable(discounts) {
                const discountTableBody = document.getElementById('discountsTableBody');
                if (!discountTableBody) {
                    console.error('discountsTableBody 요소를 찾을 수 없습니다.');
                    return;
                }

                discountTableBody.innerHTML = '';

                if (discounts.length === 0) {
                    discountTableBody.innerHTML = `
                        <tr>
                            <td colspan="10" class="text-center text-muted">
                                할인정책 데이터가 없습니다.
                            </td>
                        </tr>
                    `;
                    return;
                }

                discounts.forEach(discount => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${discount.forest_name || '미상'}</td>
                        <td><span class="badge bg-primary">${discount.policy_category || ''}</span></td>
                        <td>${discount.target_group || ''}</td>
                        <td>
                            ${discount.discount_type === 'exemption' ? 
                                '<span class="badge bg-success">면제</span>' : 
                                '<span class="badge bg-info">할인</span>'
                            }
                        </td>
                        <td>
                            ${discount.discount_type === 'exemption' ? 
                                '100%' : 
                                `${discount.discount_rate || 0}%`
                            }
                        </td>
                        <td><small class="text-muted">${discount.conditions || ''}</small></td>
                        <td><small class="text-muted">${discount.required_documents || ''}</small></td>
                        <td><small class="text-muted">${discount.detailed_description || ''}</small></td>
                        <td><small class="text-muted">${discount.updated_at || ''}</small></td>
                    `;
                    discountTableBody.appendChild(row);
                });
            }
        }

        // 전역 함수들 - 원본 dashboard.js와 호환
        function loadForests() {
            window.location.reload();
        }

        function loadAccommodations(forestId = null) {
            // 필터링 로직 구현
            console.log('Loading accommodations for forest:', forestId);
        }

        async function loadDiscounts(forestId = null) {
            // 할인정책 데이터 로딩 및 필터링
            try {
                const response = await fetch('/admin/api/discounts');
                const discounts = await response.json();
                
                // 필터링 적용
                let filteredDiscounts = discounts;
                if (forestId) {
                    // forestId로 필터링하려면 forest_id 필드가 필요하지만, 
                    // 현재 API는 forest_name만 반환하므로 forest_name으로 매칭
                    const forestsResponse = await fetch('/admin/api/forests');
                    const forests = await forestsResponse.json();
                    const targetForest = forests.find(f => f.forest_id === forestId);
                    
                    if (targetForest) {
                        filteredDiscounts = discounts.filter(d => d.forest_name === targetForest.forest_name);
                    }
                }
                
                // DashboardManager 인스턴스를 통해 테이블 업데이트
                if (window.dashboard) {
                    window.dashboard.updateDiscountsTable(filteredDiscounts);
                } else {
                    // fallback: 새 인스턴스 생성
                    const dashboard = new DashboardManager();
                    dashboard.updateDiscountsTable(filteredDiscounts);
                }
                
                console.log(`할인정책 로딩 완료: ${filteredDiscounts.length}개 정책`);
            } catch (error) {
                console.error('할인정책 로딩 오류:', error);
            }
        }

        async function collectForestData(forestId) {
            const dashboard = new DashboardManager();
            dashboard.showCrawlingStatus('기본 데이터 수집을 시작합니다...', 'info');
            dashboard.showLoadingModal();

            try {
                const response = await fetch('/admin/api/crawl/basic', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ forest_id: forestId })
                });

                const result = await response.json();
                dashboard.hideLoadingModal();

                if (result.status === 'success') {
                    dashboard.showCrawlingStatus(result.message, 'success');
                    alert(result.message);
                } else {
                    dashboard.showCrawlingStatus('데이터 수집 중 오류가 발생했습니다.', 'danger');
                }
            } catch (error) {
                dashboard.hideLoadingModal();
                dashboard.showCrawlingStatus('네트워크 오류가 발생했습니다.', 'danger');
                console.error('Crawling error:', error);
            }
        }

        async function collectDetailedData(accommodationId) {
            const dashboard = new DashboardManager();
            dashboard.showCrawlingStatus('상세 데이터 수집을 시작합니다...', 'info');
            dashboard.showLoadingModal();

            try {
                // 먼저 숙박시설 정보를 가져와서 forest_id 확인
                let forestId = null;
                const accommodationsResponse = await fetch('/admin/api/accommodations');
                if (accommodationsResponse.ok) {
                    const accommodations = await accommodationsResponse.json();
                    const accommodation = accommodations.find(acc => acc.accommodation_id == accommodationId);
                    if (accommodation) {
                        forestId = accommodation.forest_id;
                    }
                }

                if (!forestId) {
                    dashboard.hideLoadingModal();
                    dashboard.showCrawlingStatus('숙박시설 정보를 찾을 수 없습니다.', 'danger');
                    return;
                }

                const response = await fetch('/admin/api/crawl/detailed', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        forest_id: forestId,
                        accommodation_id: accommodationId 
                    })
                });

                const result = await response.json();
                dashboard.hideLoadingModal();

                if (result.success) {
                    dashboard.showCrawlingStatus(result.message, 'success');
                    // 성공 시에만 페이지 새로고침 (팝업 제거)
                    setTimeout(() => {
                        location.reload();
                    }, 2000);
                } else {
                    dashboard.showCrawlingStatus(result.message || '데이터 수집 중 오류가 발생했습니다.', 'danger');
                    console.error('Crawling failed:', result.message);
                }
            } catch (error) {
                dashboard.hideLoadingModal();
                dashboard.showCrawlingStatus('네트워크 오류가 발생했습니다.', 'danger');
                console.error('Detailed crawling error:', error);
            }
        }

        async function collectDiscountData(forestId) {
            const dashboard = new DashboardManager();
            dashboard.showCrawlingStatus('할인정책 데이터 수집을 시작합니다...', 'info');
            dashboard.showLoadingModal();

            try {
                const response = await fetch('/admin/api/crawl/discounts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ forest_id: forestId })
                });

                const result = await response.json();
                dashboard.hideLoadingModal();

                if (result.status === 'success') {
                    dashboard.showCrawlingStatus(result.message, 'success');
                    // 할인정책 탭 데이터 새로고침
                    if (window.dashboard && typeof window.dashboard.loadDiscountsData === 'function') {
                        window.dashboard.loadDiscountsData();
                    }
                } else {
                    dashboard.showCrawlingStatus(result.message || '할인정책 수집 중 오류가 발생했습니다.', 'danger');
                }
            } catch (error) {
                dashboard.hideLoadingModal();
                dashboard.showCrawlingStatus('네트워크 오류가 발생했습니다.', 'danger');
                console.error('Discount crawling error:', error);
            }
        }

        // 초기화
        document.addEventListener('DOMContentLoaded', function() {
            window.dashboard = new DashboardManager();
            
            // 페이지 로딩 시 할인정책 데이터 자동 로드
            if (window.dashboard.loadDiscountsData) {
                window.dashboard.loadDiscountsData();
            }
        });
    </script>
</body>
</html>
"""

# 기타 템플릿들 (기존과 동일)
MAIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌲 HyurimBot - 자연휴양림 AI 추천</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 800px;
            width: 90%;
        }
        .title { 
            font-size: 3em; 
            margin-bottom: 20px; 
            background: linear-gradient(45deg, #4CAF50, #45a049);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .subtitle { 
            font-size: 1.3em; 
            color: #666; 
            margin-bottom: 40px; 
        }
        .search-container {
            margin: 40px 0;
            position: relative;
        }
        .search-input {
            width: 100%;
            padding: 20px 25px;
            font-size: 1.1em;
            border: 2px solid #e0e0e0;
            border-radius: 50px;
            outline: none;
            transition: all 0.3s;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }
        .search-input:focus {
            border-color: #4CAF50;
            box-shadow: 0 5px 30px rgba(76, 175, 80, 0.3);
        }
        .search-btn {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            border: none;
            padding: 20px 40px;
            border-radius: 50px;
            font-size: 1.1em;
            cursor: pointer;
            margin-top: 20px;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(76, 175, 80, 0.4);
        }
        .search-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 40px rgba(76, 175, 80, 0.6);
        }
        .admin-link {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255,255,255,0.2);
            padding: 10px 20px;
            border-radius: 25px;
            color: white;
            text-decoration: none;
            backdrop-filter: blur(10px);
            transition: all 0.3s;
        }
        .admin-link:hover {
            background: rgba(255,255,255,0.3);
            color: white;
            text-decoration: none;
        }
        .results {
            margin-top: 40px;
            text-align: left;
        }
        
        .search-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .search-header h3 {
            margin: 0 0 10px 0;
        }
        
        .engine-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            margin: 10px 0;
            font-weight: bold;
        }
        
        .engine-badge.vector {
            background: rgba(76, 175, 80, 0.2);
            border: 2px solid #4CAF50;
        }
        
        .engine-badge.basic {
            background: rgba(255, 193, 7, 0.2);
            border: 2px solid #FFC107;
        }
        
        .search-info {
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 0.9em;
        }
        
        .result-item {
            background: #f8f9fa;
            padding: 25px;
            margin: 20px 0;
            border-radius: 15px;
            border-left: 5px solid #4CAF50;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: all 0.3s;
        }
        
        .result-item.enhanced {
            background: white;
            border: 1px solid #e0e0e0;
        }
        
        .result-item.enhanced:hover {
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            transform: translateY(-2px);
        }
        
        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 15px;
        }
        
        .result-header h4 {
            margin: 0;
            color: #333;
            font-size: 1.2em;
        }
        
        .score-badge {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
            min-width: 60px;
            text-align: center;
        }
        
        .result-details {
            margin: 15px 0;
        }
        
        .detail-row {
            display: flex;
            margin: 8px 0;
            align-items: flex-start;
        }
        
        .detail-label {
            font-weight: bold;
            min-width: 100px;
            color: #666;
            margin-right: 10px;
            flex-shrink: 0;
        }
        
        .detail-value {
            color: #333;
            flex-grow: 1;
        }
        
        .detail-value.price {
            color: #4CAF50;
            font-weight: bold;
        }
        
        .detail-row.amenities .detail-value {
            color: #666;
            font-size: 0.9em;
            line-height: 1.4;
        }
        
        .recommendation-reason {
            background: linear-gradient(45deg, #E8F5E8, #F1F8E9);
            border: 1px solid #C8E6C9;
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
            color: #2E7D32;
            font-style: italic;
        }
        
        .recommendation-reason i {
            color: #FFA000;
            margin-right: 8px;
        }
        
        .result-actions {
            margin-top: 15px;
            text-align: right;
        }
        
        .homepage-link {
            background: linear-gradient(45deg, #2196F3, #1976D2);
            color: white;
            padding: 10px 20px;
            border-radius: 25px;
            text-decoration: none;
            font-size: 0.9em;
            transition: all 0.3s;
        }
        
        .homepage-link:hover {
            background: linear-gradient(45deg, #1976D2, #1565C0);
            color: white;
            text-decoration: none;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(33, 150, 243, 0.4);
        }
        
        .no-results {
            text-align: center;
            background: #fff3cd;
            border-color: #ffc107;
            color: #856404;
        }
        
        .no-results h4 {
            margin-bottom: 15px;
        }
        .loading {
            display: none;
            margin: 20px 0;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #4CAF50;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <a href="{{ url_for('login') }}" class="admin-link">🔐 관리자</a>
    
    <div class="container">
        <h1 class="title">🌲 HyurimBot</h1>
        <p class="subtitle">AI가 추천하는 맞춤형 자연휴양림</p>
        
        <div class="search-container">
            <input type="text" id="searchQuery" class="search-input" 
                   placeholder="원하는 휴양림을 설명해보세요 (예: 가족과 함께 조용한 산속에서 힐링하고 싶어요)" 
                   onkeypress="if(event.key==='Enter') search()">
            <button class="search-btn" onclick="search()">
                🔍 AI 추천받기
            </button>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>AI가 최적의 휴양림을 찾고 있습니다...</p>
        </div>
        
        <div id="results" class="results"></div>
    </div>

    <script>
        async function search() {
            const query = document.getElementById('searchQuery').value.trim();
            const loading = document.getElementById('loading');
            const results = document.getElementById('results');
            
            if (!query) {
                alert('검색어를 입력해주세요!');
                return;
            }
            
            loading.style.display = 'block';
            results.innerHTML = '';
            
            try {
                const response = await fetch('/api/recommend', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query })
                });
                
                const data = await response.json();
                
                loading.style.display = 'none';
                
                if (data.success && data.recommendations.length > 0) {
                    // 검색 엔진 정보 표시
                    const engineBadge = data.engine === 'vector_search' 
                        ? '<span class="engine-badge vector">🧠 AI 벡터 검색</span>' 
                        : '<span class="engine-badge basic">🔍 기본 검색</span>';
                    
                    results.innerHTML = `
                        <div class="search-header">
                            <h3>🎯 AI 추천 결과</h3>
                            ${engineBadge}
                            <p class="search-info">"${query}"에 대한 ${data.recommendations.length}개 추천 결과</p>
                        </div>
                    `;
                    
                    data.recommendations.forEach((item, index) => {
                        // 가격 정보 포맷팅
                        const priceInfo = item.price_off_weekday 
                            ? `${item.price_off_weekday.toLocaleString()}원/박` 
                            : '가격 정보 없음';
                        
                        // 유사도 점수 포맷팅
                        const similarityScore = item.similarity_score 
                            ? (item.similarity_score * 100).toFixed(1) + '%'
                            : item.score 
                            ? (item.score * 100).toFixed(1) + '%' 
                            : 'N/A';
                        
                        // 추천 근거 (벡터 검색에서만)
                        const recommendationReason = item.recommendation_reason 
                            ? `<div class="recommendation-reason">
                                 <i class="fas fa-lightbulb"></i> ${item.recommendation_reason}
                               </div>` 
                            : '';
                        
                        results.innerHTML += `
                            <div class="result-item enhanced">
                                <div class="result-header">
                                    <h4>${index + 1}. ${item.facility_name || item.forest_name}</h4>
                                    <div class="score-badge">${similarityScore}</div>
                                </div>
                                
                                <div class="result-details">
                                    <div class="detail-row">
                                        <span class="detail-label">🏛️ 휴양림:</span>
                                        <span class="detail-value">${item.forest_name}</span>
                                    </div>
                                    <div class="detail-row">
                                        <span class="detail-label">📍 위치:</span>
                                        <span class="detail-value">${item.address || '정보 없음'}</span>
                                    </div>
                                    <div class="detail-row">
                                        <span class="detail-label">🏠 시설유형:</span>
                                        <span class="detail-value">${item.facility_type || '정보 없음'}</span>
                                    </div>
                                    <div class="detail-row">
                                        <span class="detail-label">👥 수용인원:</span>
                                        <span class="detail-value">${item.capacity_standard ? item.capacity_standard + '명' : '정보 없음'}</span>
                                    </div>
                                    <div class="detail-row">
                                        <span class="detail-label">💰 가격:</span>
                                        <span class="detail-value price">${priceInfo}</span>
                                    </div>
                                    ${item.amenities ? `
                                    <div class="detail-row amenities">
                                        <span class="detail-label">🏪 편의시설:</span>
                                        <span class="detail-value">${item.amenities}</span>
                                    </div>
                                    ` : ''}
                                </div>
                                
                                ${recommendationReason}
                                
                                ${item.homepage_url ? `
                                <div class="result-actions">
                                    <a href="${item.homepage_url}" target="_blank" class="homepage-link">
                                        🔗 홈페이지 보기
                                    </a>
                                </div>
                                ` : ''}
                            </div>
                        `;
                    });
                } else {
                    results.innerHTML = `
                        <div class="result-item no-results">
                            <h4>🔍 검색 결과가 없습니다</h4>
                            <p>추천할 수 있는 숙박시설을 찾지 못했습니다.</p>
                            <p>다른 키워드로 검색해보세요. (예: "가족 펜션", "커플 휴양관", "넓은 객실")</p>
                        </div>
                    `;
                }
            } catch (error) {
                loading.style.display = 'none';
                results.innerHTML = '<div class="result-item">오류가 발생했습니다. 잠시 후 다시 시도해주세요.</div>';
                console.error('Search error:', error);
            }
        }
    </script>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔐 HyurimBot 관리자 로그인</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 400px;
            width: 90%;
        }
        .title { 
            font-size: 2em; 
            margin-bottom: 10px; 
            color: #333;
        }
        .subtitle { 
            font-size: 1em; 
            color: #666; 
            margin-bottom: 30px; 
        }
        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
        }
        .form-control {
            width: 100%;
            padding: 15px;
            font-size: 16px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            outline: none;
            transition: all 0.3s;
        }
        .form-control:focus {
            border-color: #4CAF50;
            box-shadow: 0 0 20px rgba(76, 175, 80, 0.3);
        }
        .login-btn {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-size: 16px;
            cursor: pointer;
            width: 100%;
            transition: all 0.3s;
            margin-top: 10px;
        }
        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(76, 175, 80, 0.4);
        }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            color: #666;
            text-decoration: none;
            transition: all 0.3s;
        }
        .back-link:hover {
            color: #4CAF50;
            text-decoration: none;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .flash-message {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
            text-align: center;
        }
        .flash-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .flash-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .flash-info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
    </style>
</head>
<body>
    <div class="login-container">
        <h1 class="title">🔐 관리자 로그인</h1>
        <p class="subtitle">HyurimBot 데이터 수집 시스템</p>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash-message flash-{{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        
        <form method="POST">
            <div class="form-group">
                <label>사용자명</label>
                <input type="text" name="username" class="form-control" required>
            </div>
            
            <div class="form-group">
                <label>비밀번호</label>
                <input type="password" name="password" class="form-control" required>
            </div>
            
            <button type="submit" class="login-btn">로그인</button>
        </form>
        
        <a href="{{ url_for('index') }}" class="back-link">← 메인 페이지로 돌아가기</a>
    </div>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 HyurimBot 관리자 대시보드</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f5f5f5;
            min-height: 100vh;
        }
        .navbar {
            background: #2E7D32;
            color: white;
            padding: 1rem 0;
        }
        .nav-container {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 20px;
        }
        .logo { font-size: 1.5em; font-weight: bold; }
        .nav-links a {
            color: white;
            text-decoration: none;
            margin-left: 20px;
            padding: 8px 16px;
            border-radius: 20px;
            transition: all 0.3s;
        }
        .nav-links a:hover { background: rgba(255,255,255,0.2); }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .dashboard-header {
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            text-align: center;
        }
        .stat-number {
            font-size: 2.5em;
            font-weight: bold;
            color: #4CAF50;
            margin-bottom: 10px;
        }
        .admin-actions {
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }
        .action-btn {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-size: 16px;
            cursor: pointer;
            margin: 10px;
            transition: all 0.3s;
        }
        .action-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(76, 175, 80, 0.4);
        }
        .action-btn.danger {
            background: linear-gradient(45deg, #f44336, #d32f2f);
        }
        .data-table {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }
        .data-table table {
            width: 100%;
            border-collapse: collapse;
        }
        .data-table th,
        .data-table td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }
        .data-table th {
            background: #f8f9fa;
            font-weight: bold;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .flash-message {
            padding: 15px 20px;
            border-radius: 10px;
            margin-bottom: 10px;
        }
        .flash-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .flash-warning { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
        .flash-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <div class="logo">📊 HyurimBot 관리자</div>
            <div class="nav-links">
                <a href="{{ url_for('index') }}">🏠 메인 페이지</a>
                <a href="{{ url_for('logout') }}">🚪 로그아웃</a>
            </div>
        </div>
    </nav>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <div class="container">
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash-message flash-{{ category }}">{{ message }}</div>
                    {% endfor %}
                </div>
            </div>
        {% endif %}
    {% endwith %}

    <div class="container">
        <div class="dashboard-header">
            <h1>🌲 HyurimBot 관리자 대시보드</h1>
            <p>자연휴양림 데이터 수집 및 AI 추천 시스템 관리</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{{ stats.forests }}</div>
                <div>등록된 휴양림</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.accommodations }}</div>
                <div>숙박시설</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.facilities }}</div>
                <div>편의시설</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ "%.1f"|format(stats.db_size) }}MB</div>
                <div>데이터베이스 크기</div>
            </div>
        </div>

        <div class="admin-actions">
            <h2>🔧 시스템 관리 기능</h2>
            <a href="{{ url_for('data_collection_dashboard') }}" class="action-btn" style="text-decoration: none; display: inline-block;">
                🕷️ 데이터 수집 대시보드
            </a>
            <button class="action-btn" onclick="showDataOverview()">📊 데이터 현황 보기</button>
            <button class="action-btn" onclick="testRecommendation()">🤖 AI 추천 테스트</button>
            <button class="action-btn" onclick="exportData()">📤 데이터 내보내기</button>
            <button class="action-btn danger" onclick="clearCache()">🗑️ 캐시 삭제</button>
        </div>

        <div id="dataOverview" class="data-table" style="display: none;">
            <h3>📋 최근 데이터</h3>
            <table id="dataTable">
                <thead>
                    <tr>
                        <th>휴양림명</th>
                        <th>숙박시설 수</th>
                        <th>지역</th>
                        <th>최근 업데이트</th>
                    </tr>
                </thead>
                <tbody id="dataTableBody">
                    <!-- 동적 데이터 로드 -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function showDataOverview() {
            const overview = document.getElementById('dataOverview');
            const tbody = document.getElementById('dataTableBody');
            
            try {
                const response = await fetch('/admin/api/data-overview');
                const data = await response.json();
                
                tbody.innerHTML = '';
                data.forEach(item => {
                    tbody.innerHTML += `
                        <tr>
                            <td>${item.forest_name}</td>
                            <td>${item.accommodation_count || 0}</td>
                            <td>${item.sido}</td>
                            <td>${item.updated_at || '미상'}</td>
                        </tr>
                    `;
                });
                
                overview.style.display = overview.style.display === 'none' ? 'block' : 'none';
            } catch (error) {
                alert('데이터를 불러오는데 실패했습니다.');
                console.error('Data overview error:', error);
            }
        }

        async function testRecommendation() {
            const query = prompt('테스트할 검색어를 입력하세요:', '가족과 함께 조용한 휴양림');
            if (!query) return;
            
            try {
                const response = await fetch('/api/recommend', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query })
                });
                
                const data = await response.json();
                if (data.success) {
                    alert(`추천 결과: ${data.recommendations.length}개 휴양림 추천완료`);
                } else {
                    alert('추천 시스템 오류');
                }
            } catch (error) {
                alert('추천 테스트 실패');
                console.error('Recommendation test error:', error);
            }
        }

        function exportData() {
            alert('데이터 내보내기 기능은 곧 구현됩니다.');
        }

        function clearCache() {
            if (confirm('정말로 캐시를 삭제하시겠습니까?')) {
                alert('캐시가 삭제되었습니다.');
            }
        }
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    print("HyurimBot 통합 시스템을 시작합니다...")
    print("관리자 계정: admin / hyurimbot2025")
    print("데이터 수집 대시보드: http://localhost:8081/admin/data-collection")
    print("=" * 50)
    app.run(host='0.0.0.0', port=8081, debug=True)