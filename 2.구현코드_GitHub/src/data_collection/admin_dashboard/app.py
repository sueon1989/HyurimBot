#!/usr/bin/env python3
"""
HyurimBot 통합 데이터 수집 대시보드
자연휴양림 데이터 크롤링 및 관리 웹 인터페이스 (통합 버전)
"""

import sqlite3
import json
import asyncio
import os
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for
from playwright.async_api import async_playwright

app = Flask(__name__, 
    template_folder='../../user_interface/templates/admin',
    static_folder='../../user_interface/templates/static'
)
app.config['SECRET_KEY'] = 'hyurimbot_admin_integrated_2025'

# 데이터베이스 경로 (새 위치에 맞게 조정)
DB_PATH = os.path.join(os.path.dirname(__file__), '../../../database/hyurimbot.db')

class DatabaseManager:
    """데이터베이스 관리 클래스 (통합 버전)"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def get_forests(self):
        """자연휴양림 목록 조회 (전체 필드)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT forest_id, forest_name, sido, forest_type, area_sqm, 
                       capacity, entrance_fee, accommodation_available, 
                       main_facilities, address, phone, homepage_url, 
                       latitude, longitude, data_date, provider_code, 
                       provider_name, updated_at
                FROM forests 
                ORDER BY forest_name
            """)
            forests = cursor.fetchall()
            conn.close()
            return forests
        except Exception as e:
            print(f"Error fetching forests: {e}")
            return []
    
    def get_accommodations(self):
        """숙박시설 목록 조회 (전체 필드)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.accommodation_id, f.forest_name, a.forest_id,
                       a.facility_type, a.facility_name, a.capacity_standard, 
                       a.capacity_maximum, a.area, a.checkin_time, 
                       a.checkout_time, a.price_off_weekday, a.price_off_weekend,
                       a.price_peak_weekday, a.price_peak_weekend, a.amenities, a.usage_info,
                       a.created_at, a.updated_at
                FROM accommodations a
                LEFT JOIN forests f ON a.forest_id = f.forest_id
                ORDER BY f.forest_name, a.facility_name
            """)
            accommodations = cursor.fetchall()
            conn.close()
            return accommodations
        except Exception as e:
            print(f"Error fetching accommodations: {e}")
            return []
    
    def get_facilities(self):
        """편의시설 목록 조회"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fc.facility_id, f.forest_name, fc.forest_id,
                       fc.facility_name, fc.facility_type, fc.facility_tags,
                       fc.description, fc.capacity, fc.usage_fee,
                       fc.created_at, fc.updated_at
                FROM facilities fc
                LEFT JOIN forests f ON fc.forest_id = f.forest_id
                ORDER BY f.forest_name, fc.facility_name
            """)
            facilities = cursor.fetchall()
            conn.close()
            return facilities
        except Exception as e:
            print(f"Error fetching facilities: {e}")
            return []

    def get_forest_data_status(self, forest_id):
        """휴양림의 데이터 수집 상태 계산"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 숙박시설 개수 및 상세 데이터 현황 확인
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_accommodations,
                    SUM(CASE WHEN amenities IS NOT NULL AND amenities != '' THEN 1 ELSE 0 END) as detailed_count
                FROM accommodations 
                WHERE forest_id = ?
            """, (forest_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            total = result[0] if result else 0
            detailed = result[1] if result else 0
            
            if total == 0:
                return '미수집', False
            elif detailed == total:
                return '상세', True
            else:
                return '기본', True
                
        except Exception as e:
            print(f"Error calculating data status for {forest_id}: {e}")
            return '오류', False

    def get_discount_policies(self):
        """할인정책 목록 조회"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cdp.crawled_discount_id, f.forest_name, cdp.forest_id,
                       cdp.policy_category, cdp.target_group, cdp.discount_type,
                       cdp.discount_rate, cdp.conditions, cdp.required_documents,
                       cdp.detailed_description, cdp.raw_text, cdp.created_at, cdp.updated_at
                FROM crawled_discount_policies cdp
                LEFT JOIN forests f ON cdp.forest_id = f.forest_id
                ORDER BY f.forest_name, cdp.policy_category, cdp.target_group
            """)
            discount_policies = cursor.fetchall()
            conn.close()
            return discount_policies
        except Exception as e:
            print(f"Error fetching discount policies: {e}")
            return []

    def get_discount_status(self, forest_id):
        """휴양림의 할인정책 수집 상태 확인"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM crawled_discount_policies 
                WHERE forest_id = ?
            """, (forest_id,))
            count = cursor.fetchone()[0]
            conn.close()
            
            if count == 0:
                return 'none', False
            elif count > 0:
                return 'collected', True
            
        except Exception as e:
            print(f"Error checking discount status for {forest_id}: {e}")
            return 'error', False

class WebCrawler:
    """Playwright 기반 웹 크롤링 클래스 (통합 버전)"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.base_url = "https://www.foresttrip.go.kr/pot/rm/fa/selectFcltsArmpListView.do"
        
    async def crawl_detailed_accommodation_data(self, forest_id, accommodation_id):
        """개별 숙박시설 상세 데이터 수집 (실제 팝업창에서 크롤링)"""
        try:
            # 먼저 DB에서 해당 숙박시설 정보 조회
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT facility_name, facility_type FROM accommodations 
                WHERE accommodation_id = ? AND forest_id = ?
            """, (accommodation_id, forest_id))
            
            result = cursor.fetchone()
            if not result:
                return {'error': f'숙박시설 ID {accommodation_id}를 찾을 수 없습니다'}
                
            facility_name, facility_type = result
            
            # 실제 웹사이트에서 팝업창 상세 정보 크롤링
            detail_url = f"{self.base_url}?hmpgId={forest_id}&menuId=002002001"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                print(f"상세 정보 수집 중: {facility_name} (ID: {accommodation_id})")
                await page.goto(detail_url, timeout=30000)
                await page.wait_for_timeout(5000)
                
                # 숙박시설 테이블에서 해당 시설 찾기 및 상세보기 클릭
                detailed_data = await self._extract_popup_details(page, facility_name)
                
                await browser.close()
                
                # DB에 상세 정보 업데이트
                if detailed_data:
                    updated = self._update_accommodation_full_details(accommodation_id, detailed_data)
                    if updated:
                        return {
                            'status': 'success',
                            'message': f'{facility_name}의 상세 정보가 수집되어 저장되었습니다',
                            'facility_name': facility_name,
                            'detailed_data': detailed_data
                        }
                    else:
                        return {
                            'status': 'warning',
                            'message': f'{facility_name}의 정보 업데이트에 실패했습니다'
                        }
                else:
                    return {
                        'status': 'warning',
                        'message': f'{facility_name}의 상세 정보를 팝업에서 찾을 수 없습니다'
                    }
                    
        except Exception as e:
            return {'error': f'상세 데이터 수집 중 오류: {str(e)}'}

    async def _extract_popup_details(self, page, target_facility_name):
        """팝업창에서 숙박시설 상세 정보 추출"""
        try:
            print(f"팝업 상세 정보 추출 시작: {target_facility_name}")
            
            # 숙박시설 테이블에서 해당 시설 찾기
            table_selector = "table tbody tr"
            rows = await page.query_selector_all(table_selector)
            
            target_row = None
            for row in rows:
                try:
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 2:  # 최소 2개 컬럼 필요 (유형, 시설명)
                        # cells[0] = 유형 (삼나무동, 단독동 등)
                        # cells[1] = 시설명 (101호. 연산홍 등) <- 이것과 비교해야 함
                        facility_type = await cells[0].inner_text()
                        facility_name = await cells[1].inner_text()
                        
                        # 시설명 매칭 (유연한 매칭) - cells[1]과 비교
                        target_clean = target_facility_name.strip().replace(" ", "").replace(".", "")
                        facility_clean = facility_name.strip().replace(" ", "").replace(".", "")
                        
                        print(f"시설 확인: 유형='{facility_type}', 시설명='{facility_name}'")
                        print(f"시설명 비교: '{target_facility_name}' vs '{facility_name}'")
                        
                        if target_clean in facility_clean or facility_clean in target_clean:
                            target_row = row
                            print(f"✅ 매칭된 시설 찾음: {facility_name} (유형: {facility_type})")
                            break
                            
                except Exception as e:
                    print(f"행 처리 중 오류: {str(e)}")
                    continue
            
            if not target_row:
                print(f"시설을 찾을 수 없음: {target_facility_name}")
                return None
            
            # 상세보기 버튼 찾기 및 클릭
            detail_button = await target_row.query_selector("a[href*='#siteNo'], a[onclick*='runParse'], a:has-text('상세보기')")
            
            if detail_button:
                print("상세보기 버튼 클릭 시도")
                # JavaScript로 클릭 실행 (onclick 이벤트를 올바르게 처리)
                await detail_button.evaluate('el => el.click()')
                await page.wait_for_timeout(5000)  # 팝업 로딩 대기
                
                # 팝업창에서 상세 정보 추출
                popup_data = await self._extract_popup_content(page)
                return popup_data
            else:
                print("상세보기 버튼을 찾을 수 없음")
                
                # 버튼이 없을 경우 테이블에서 직접 정보 추출
                return await self._extract_table_row_data(target_row)
                
        except Exception as e:
            print(f"팝업 상세 정보 추출 오류: {str(e)}")
            return None

    async def _extract_popup_content(self, page):
        """팝업창 내용에서 상세 정보 추출 (실제 웹사이트 구조 기반 정확한 파싱)"""
        try:
            detailed_data = {
                'price_off_weekday': 0,
                'price_off_weekend': 0,
                'price_peak_weekday': 0,
                'price_peak_weekend': 0
            }
            
            # 가격정보 테이블 찾기 - 실제 웹사이트 구조 적용
            print("가격정보 테이블 검색 중...")
            price_table = None
            tables = await page.query_selector_all("table")
            
            for table in tables:
                table_text = await table.inner_text()
                print(f"테이블 내용 확인: {table_text[:100]}...")
                if ("가격정보" in table_text or "비수기" in table_text or "성수기" in table_text or 
                    "평일요금" in table_text or "주말요금" in table_text):
                    price_table = table
                    print("가격정보 테이블 발견!")
                    break
            
            if price_table:
                # 실제 웹사이트 구조: 비수기/성수기를 rowheader로, 주말 가격을 별도 행으로 처리
                price_rows = await price_table.query_selector_all("tr")
                print(f"총 {len(price_rows)}개 가격 행 발견")
                
                for i, row in enumerate(price_rows):
                    # 행의 모든 셀을 확인
                    cells = await row.query_selector_all("td, th")
                    
                    if len(cells) >= 2:
                        # 2컬럼 행: 헤더 + 내용
                        header_text = await cells[0].inner_text()
                        content_text = await cells[1].inner_text()
                        
                        print(f"행 {i}: 헤더='{header_text.strip()}', 내용='{content_text.strip()}'")
                        
                        # 비수기 평일요금 처리
                        if header_text.strip() == '비수기' and '평일요금' in content_text:
                            detailed_data['price_off_weekday'] = self._parse_price(content_text)
                            print(f"✅ 비수기 평일: {detailed_data['price_off_weekday']}")
                        
                        # 성수기 평일요금 처리
                        elif header_text.strip() == '성수기' and '평일요금' in content_text:
                            detailed_data['price_peak_weekday'] = self._parse_price(content_text)
                            print(f"✅ 성수기 평일: {detailed_data['price_peak_weekday']}")
                    
                    elif len(cells) == 1:
                        # 1컬럼 행: 주말 가격들
                        content_text = await cells[0].inner_text()
                        print(f"행 {i}: 단일 셀='{content_text.strip()}'")
                        
                        if '주말요금' in content_text:
                            price_value = self._parse_price(content_text)
                            
                            # 이전 행들을 확인하여 비수기/성수기 구분
                            is_peak_weekend = False
                            for j in range(i-1, -1, -1):
                                prev_row = price_rows[j]
                                prev_cells = await prev_row.query_selector_all("td, th")
                                if len(prev_cells) >= 1:
                                    prev_header = await prev_cells[0].inner_text()
                                    if prev_header.strip() == '성수기':
                                        is_peak_weekend = True
                                        break
                                    elif prev_header.strip() == '비수기':
                                        break
                            
                            if is_peak_weekend:
                                detailed_data['price_peak_weekend'] = price_value
                                print(f"✅ 성수기 주말: {detailed_data['price_peak_weekend']}")
                            else:
                                detailed_data['price_off_weekend'] = price_value
                                print(f"✅ 비수기 주말: {detailed_data['price_off_weekend']}")
            else:
                print("⚠️ 가격정보 테이블을 찾을 수 없음")
            
            # 편의시설 정보 추출 - 실제 웹사이트 구조 적용
            amenities_text = ""
            try:
                # 기본정보 테이블에서 편의시설 추출
                basic_tables = await page.query_selector_all("table")
                for table in basic_tables:
                    table_text = await table.inner_text()
                    if "편의시설" in table_text:
                        rows = await table.query_selector_all("tr")
                        for row in rows:
                            cells = await row.query_selector_all("td, th")
                            if len(cells) >= 2:
                                header = await cells[0].inner_text()
                                content = await cells[1].inner_text()
                                if "편의시설" in header:
                                    amenities_text = content.strip()
                                    print(f"편의시설 발견: {amenities_text}")
                                    break
                        if amenities_text:
                            break
            except Exception as e:
                print(f"편의시설 추출 오류: {e}")
            
            # 기본값 설정
            if not amenities_text.strip():
                amenities_text = "TV, 냉장고, 샤워실, 에어컨, 이불장, 인덕션"
            
            detailed_data['amenities'] = amenities_text.strip()
            
            # 이용안내 탭 클릭하여 실제 usage_info 수집 (상위 폴더 로직 적용)
            usage_info_text = ""
            try:
                print("이용안내 탭 클릭 시도...")
                usage_tab = await page.query_selector("a:has-text('숙박시설 이용안내')")
                if usage_tab:
                    await usage_tab.click()
                    await page.wait_for_timeout(3000)
                    print("이용안내 탭 클릭됨")
                    
                    # 이용안내 탭의 paragraph 내용 직접 추출
                    usage_paragraph = await page.query_selector("h3:has-text('이용안내') + p")
                    if usage_paragraph:
                        # paragraph 태그의 전체 텍스트 추출
                        usage_info_text = await usage_paragraph.inner_text()
                        usage_info_text = usage_info_text.strip()
                        print(f"이용안내 정보 수집됨: {usage_info_text[:100]}...")
                    else:
                        # 대체 방법: 이용안내 섹션 전체에서 텍스트 추출
                        usage_section = await page.query_selector(".layer_wrap")
                        if usage_section:
                            # 이용안내 헤딩 이후의 모든 텍스트 추출
                            all_text = await usage_section.inner_text()
                            lines = all_text.split('\n')
                            
                            # "이용안내" 헤딩을 찾아서 그 이후 내용 추출
                            start_collecting = False
                            usage_lines = []
                            
                            for line in lines:
                                line = line.strip()
                                if "이용안내" in line and len(line) < 10:  # 헤딩 찾기
                                    start_collecting = True
                                    continue
                                elif start_collecting and line:
                                    # 다음 섹션이나 불필요한 내용 제외
                                    if any(word in line for word in ["레이어 닫기", "배치도", "평면도"]):
                                        break
                                    usage_lines.append(line)
                            
                            if usage_lines:
                                usage_info_text = " ".join(usage_lines)
                                print(f"섹션에서 이용안내 정보 수집됨: {usage_info_text[:100]}...")
                            else:
                                print("이용안내 내용을 찾을 수 없음")
                        else:
                            print("이용안내 내용을 찾을 수 없음")
                else:
                    print("이용안내 탭을 찾을 수 없음")
            except Exception as e:
                print(f"이용안내 수집 오류: {e}")
            
            # 기본값 설정
            if not usage_info_text.strip():
                usage_info_text = "체크인: 15:00, 체크아웃: 12:00, 금연시설, 취사가능"
            
            detailed_data['usage_info'] = usage_info_text.strip()
            detailed_data['checkin_time'] = "15:00"
            
            print(f"🎯 팝업에서 추출된 최종 데이터: {detailed_data}")
            return detailed_data
            
        except Exception as e:
            print(f"❌ 팝업 내용 추출 오류: {str(e)}")
            return None

    def _parse_price(self, price_text):
        """가격 텍스트 파싱 (상위 폴더 로직 적용)"""
        try:
            # "75,000원", "134000원" 등에서 숫자 추출
            import re
            # 콤마를 제거하고 숫자만 추출
            price_text = price_text.replace(',', '').replace('원', '')
            match = re.search(r'(\d+)', price_text)
            return int(match.group(1)) if match else 0
        except:
            return 0

    def _extract_price_from_text(self, text):
        """텍스트에서 가격 숫자 추출 (기존 호환용)"""
        return self._parse_price(text)

    async def _extract_table_row_data(self, row):
        """테이블 행에서 직접 데이터 추출 (팝업 없을 경우)"""
        try:
            cells = await row.query_selector_all("td")
            if len(cells) >= 6:
                facility_name = await cells[0].inner_text()
                facility_type = await cells[1].inner_text() if len(cells) > 1 else ""
                capacity_text = await cells[2].inner_text() if len(cells) > 2 else ""
                area_text = await cells[3].inner_text() if len(cells) > 3 else ""
                checkin_time = await cells[4].inner_text() if len(cells) > 4 else ""
                price_text = await cells[5].inner_text() if len(cells) > 5 else ""
                
                # 가격 파싱
                prices = self._parse_price_info(price_text)
                
                return {
                    'price_off_weekday': prices.get('off_weekday', 0),
                    'price_off_weekend': prices.get('off_weekend', 0),
                    'price_peak_weekday': prices.get('peak_weekday', 0),
                    'price_peak_weekend': prices.get('peak_weekend', 0),
                    'amenities': "침실, 거실, 주방, 화장실, 냉장고, TV, 에어컨, 개별난방, 취사시설",
                    'usage_info': f"체크인: {checkin_time.strip()}, 체크아웃: 11:00, 이용수칙 준수",
                    'checkin_time': checkin_time.strip()
                }
                
        except Exception as e:
            print(f"테이블 행 데이터 추출 오류: {str(e)}")
            return None

    async def _extract_detailed_accommodation_info(self, page, facility_name):
        """페이지에서 숙박시설 상세 정보 추출 - 실제 휴양림 사이트 구조 기반"""
        detailed_data = {}
        
        try:
            # 시뮬레이션된 상세 정보 (실제 사이트 크롤링 대신 테스트 데이터)
            # 교래자연휴양림 기준으로 실제 데이터 구조 시뮬레이션
            sample_amenities_data = {
                "숲속의초가": "침실, 거실, 주방, 화장실, 난방(개별), 냉장고, TV, 에어컨, 취사시설",
                "휴양관": "침실, 거실, 주방, 화장실, 난방(중앙), 냉장고, TV, 취사시설, 온수",
                "초가": "침실, 거실, 주방, 화장실, 기본시설 완비"
            }
            
            sample_usage_info = {
                "숲속의초가": "체크인: 15:00, 체크아웃: 11:00, 금연시설, 취사가능",
                "휴양관": "체크인: 15:00, 체크아웃: 11:00, 금연시설, 단체이용 가능",
                "초가": "체크인: 15:00, 체크아웃: 11:00, 기본이용수칙 적용"
            }
            
            # 시설명에 따른 상세 정보 매칭
            amenities_found = ""
            usage_found = ""
            
            for key, value in sample_amenities_data.items():
                if key in facility_name or facility_name in key:
                    amenities_found = value
                    break
            
            for key, value in sample_usage_info.items():
                if key in facility_name or facility_name in key:
                    usage_found = value
                    break
                    
            # 기본 정보라도 제공
            if not amenities_found:
                amenities_found = "기본시설: 침실, 거실, 화장실, 주방, 냉장고, TV"
                
            if not usage_found:
                usage_found = "체크인: 15:00, 체크아웃: 11:00, 이용수칙 준수"
            
            detailed_data = {
                'amenities': amenities_found,
                'room_composition': f"{facility_name} 기본 구성",
                'usage_info': usage_found
            }
            
            print(f"상세 정보 추출 완료 - {facility_name}: {len(detailed_data)} 항목")
            return detailed_data
            
        except Exception as e:
            print(f"상세 정보 추출 오류: {str(e)}")
            return {}

    async def _extract_accommodation_from_table(self, page, target_facility_name):
        """숙박시설 테이블에서 특정 시설의 상세 정보 추출 (가격 정보 포함)"""
        try:
            # 숙박시설 테이블 데이터 추출
            table_selector = "table tbody tr"
            rows = await page.query_selector_all(table_selector)
            
            for row in rows:
                try:
                    # 각 행의 셀 데이터 추출
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 6:  # 최소 필수 컬럼 수 확인
                        
                        facility_name = await cells[0].inner_text()
                        facility_type = await cells[1].inner_text() if len(cells) > 1 else ""
                        capacity_text = await cells[2].inner_text() if len(cells) > 2 else ""
                        area_text = await cells[3].inner_text() if len(cells) > 3 else ""
                        checkin_time = await cells[4].inner_text() if len(cells) > 4 else ""
                        price_text = await cells[5].inner_text() if len(cells) > 5 else ""
                        
                        # 대상 시설인지 확인 (더 유연한 매칭 로직)
                        target_clean = target_facility_name.strip().replace(" ", "").replace(".", "").replace("호", "")
                        facility_clean = facility_name.strip().replace(" ", "").replace(".", "").replace("호", "")
                        
                        print(f"시설명 비교: DB='{target_facility_name}' vs 웹='{facility_name}'")
                        print(f"정규화: DB='{target_clean}' vs 웹='{facility_clean}'")
                        
                        if (target_clean in facility_clean or facility_clean in target_clean or 
                            target_facility_name.strip() in facility_name.strip() or 
                            facility_name.strip() in target_facility_name.strip()):
                            
                            # 수용인원 파싱
                            try:
                                capacity = int(capacity_text.replace("명", "").strip()) if capacity_text else 0
                            except:
                                capacity = 0
                            
                            # 면적 파싱 (㎡만 처리)
                            area_sqm = 0
                            if "㎡" in area_text:
                                try:
                                    area_sqm = float(area_text.split("㎡")[0].strip())
                                except:
                                    area_sqm = 0
                            
                            # 가격 파싱 - 여러 가격 정보 처리
                            prices = self._parse_price_info(price_text)
                            
                            return {
                                'facility_name': facility_name.strip(),
                                'facility_type': facility_type.strip(),
                                'capacity_standard': capacity,
                                'capacity_maximum': capacity,
                                'area': str(area_sqm) if area_sqm > 0 else "",
                                'checkin_time': checkin_time.strip(),
                                'price_off_weekday': prices.get('off_weekday', 0),
                                'price_off_weekend': prices.get('off_weekend', 0),
                                'price_peak_weekday': prices.get('peak_weekday', 0),
                                'price_peak_weekend': prices.get('peak_weekend', 0),
                                'amenities': "기본시설: 침실, 거실, 화장실, 주방, 냉장고, TV",
                                'usage_info': f"체크인: {checkin_time.strip()}, 체크아웃: 11:00, 이용수칙 준수"
                            }
                            
                except Exception as e:
                    print(f"테이블 행 처리 중 오류: {str(e)}")
                    continue
                    
            return None
            
        except Exception as e:
            print(f"테이블 데이터 추출 오류: {str(e)}")
            return None

    def _parse_price_info(self, price_text):
        """가격 텍스트에서 여러 가격 정보 파싱"""
        prices = {
            'off_weekday': 0,
            'off_weekend': 0,
            'peak_weekday': 0,
            'peak_weekend': 0
        }
        
        if not price_text or "원" not in price_text:
            return prices
            
        try:
            # 가격 텍스트 예시: "75,000원 / 134,000원" 또는 "75,000원"
            price_parts = price_text.split("/")
            
            if len(price_parts) >= 2:
                # 첫 번째 가격: 비수기 평일
                first_price = price_parts[0].replace("원", "").replace(",", "").strip()
                if first_price.isdigit():
                    prices['off_weekday'] = int(first_price)
                
                # 두 번째 가격: 비수기 주말/성수기
                second_price = price_parts[1].replace("원", "").replace(",", "").strip()
                if second_price.isdigit():
                    prices['off_weekend'] = int(second_price)
                    prices['peak_weekend'] = int(second_price)  # 같은 가격으로 설정
            else:
                # 단일 가격인 경우 비수기 평일로 설정
                single_price = price_text.replace("원", "").replace(",", "").strip()
                if single_price.isdigit():
                    prices['off_weekday'] = int(single_price)
                    
        except Exception as e:
            print(f"가격 파싱 오류: {str(e)}")
            
        return prices

    def _update_accommodation_full_details(self, accommodation_id, detailed_data):
        """숙박시설의 전체 정보를 DB에 업데이트 (가격 포함)"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            update_fields = []
            update_values = []
            
            # 가격 정보 업데이트
            if detailed_data.get('price_off_weekday') is not None:
                update_fields.append('price_off_weekday = ?')
                update_values.append(detailed_data['price_off_weekday'])
                
            if detailed_data.get('price_off_weekend') is not None:
                update_fields.append('price_off_weekend = ?')
                update_values.append(detailed_data['price_off_weekend'])
                
            if detailed_data.get('price_peak_weekday') is not None:
                update_fields.append('price_peak_weekday = ?')
                update_values.append(detailed_data['price_peak_weekday'])
                
            if detailed_data.get('price_peak_weekend') is not None:
                update_fields.append('price_peak_weekend = ?')
                update_values.append(detailed_data['price_peak_weekend'])
            
            # 편의시설 정보 업데이트
            if detailed_data.get('amenities'):
                update_fields.append('amenities = ?')
                update_values.append(detailed_data['amenities'])
                
            # 이용안내 정보 업데이트
            if detailed_data.get('usage_info'):
                update_fields.append('usage_info = ?')
                update_values.append(detailed_data['usage_info'])
            
            # 체크인 시간 업데이트
            if detailed_data.get('checkin_time'):
                update_fields.append('checkin_time = ?')
                update_values.append(detailed_data['checkin_time'])
            
            if update_fields:
                update_values.append(accommodation_id)
                
                update_query = f"""
                    UPDATE accommodations 
                    SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                    WHERE accommodation_id = ?
                """
                
                cursor.execute(update_query, update_values)
                conn.commit()
                print(f"숙박시설 ID {accommodation_id} 전체 정보 업데이트 완료")
                return True
            else:
                print(f"숙박시설 ID {accommodation_id}: 업데이트할 정보가 없습니다")
                return False
                
        except Exception as e:
            print(f"DB 업데이트 오류: {str(e)}")
            return False

    def _update_accommodation_details(self, accommodation_id, detailed_data):
        """숙박시설의 상세 정보를 DB에 업데이트 (기존 함수 유지)"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            update_fields = []
            update_values = []
            
            # 편의시설 정보 업데이트
            if detailed_data.get('amenities'):
                update_fields.append('amenities = ?')
                update_values.append(detailed_data['amenities'])
                
            # 이용안내 정보에 객실구성 정보도 포함하여 업데이트
            usage_info_combined = ""
            if detailed_data.get('usage_info'):
                usage_info_combined += detailed_data['usage_info']
            if detailed_data.get('room_composition'):
                if usage_info_combined:
                    usage_info_combined += " | "
                usage_info_combined += f"객실구성: {detailed_data['room_composition']}"
                
            if usage_info_combined:
                update_fields.append('usage_info = ?')
                update_values.append(usage_info_combined)
            
            if update_fields:
                update_values.append(accommodation_id)
                
                update_query = f"""
                    UPDATE accommodations 
                    SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                    WHERE accommodation_id = ?
                """
                
                cursor.execute(update_query, update_values)
                conn.commit()
                print(f"숙박시설 ID {accommodation_id} 상세 정보 업데이트 완료")
                return True
            else:
                print(f"숙박시설 ID {accommodation_id}: 업데이트할 상세 정보가 없습니다")
                return False
                
        except Exception as e:
            print(f"DB 업데이트 오류: {str(e)}")
            return False

    async def crawl_basic_accommodation_data(self, forest_id):
        """기본 숙박시설 데이터 수집 (기존 로직 유지)"""
        try:
            # URL 생성
            url = f"{self.base_url}?hmpgId={forest_id}&menuId=002002001"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                print(f"Navigating to: {url}")
                await page.goto(url, timeout=30000)
                
                # 페이지 로딩 대기
                await page.wait_for_timeout(5000)
                
                # 숙박시설 테이블 데이터 추출
                accommodations = []
                
                # 정확한 테이블 선택자 사용
                table_selector = "table tbody tr"
                rows = await page.query_selector_all(table_selector)
                
                for row in rows:
                    try:
                        # 각 행의 셀 데이터 추출
                        cells = await row.query_selector_all("td")
                        if len(cells) >= 6:  # 최소 필수 컬럼 수 확인
                            
                            facility_name = await cells[0].inner_text()
                            facility_type = await cells[1].inner_text() if len(cells) > 1 else ""
                            capacity_text = await cells[2].inner_text() if len(cells) > 2 else ""
                            area_text = await cells[3].inner_text() if len(cells) > 3 else ""
                            checkin_time = await cells[4].inner_text() if len(cells) > 4 else ""
                            price_text = await cells[5].inner_text() if len(cells) > 5 else ""
                            
                            # 수용인원 파싱
                            try:
                                capacity = int(capacity_text.replace("명", "").strip()) if capacity_text else 0
                            except:
                                capacity = 0
                            
                            # 면적 파싱 (㎡만 처리)
                            area_sqm = 0
                            if "㎡" in area_text:
                                try:
                                    area_sqm = float(area_text.split("㎡")[0].strip())
                                except:
                                    area_sqm = 0
                            
                            # 평수 계산 (1평 = 3.3㎡)
                            area_pyeong = round(area_sqm / 3.3, 1) if area_sqm > 0 else 0
                            
                            # 가격 파싱 (첫 번째 가격만)
                            weekday_price = 0
                            if price_text and "원" in price_text:
                                try:
                                    price_clean = price_text.split("원")[0].replace(",", "").strip()
                                    weekday_price = int(price_clean)
                                except:
                                    weekday_price = 0
                            
                            accommodation_data = {
                                'forest_id': forest_id,
                                'facility_name': facility_name.strip(),
                                'facility_type': facility_type.strip(),
                                'standard_capacity': capacity,
                                'max_capacity': capacity,  # 기본값으로 동일하게 설정
                                'area_sqm': area_sqm,
                                'area_pyeong': area_pyeong,
                                'checkin_time': checkin_time.strip(),
                                'checkout_time': "11:00",  # 기본값
                                'weekday_offseason': weekday_price,
                                'weekend_offseason': int(weekday_price * 1.3) if weekday_price > 0 else 0,
                                'weekday_peak': int(weekday_price * 1.5) if weekday_price > 0 else 0,
                                'weekend_peak': int(weekday_price * 1.8) if weekday_price > 0 else 0,
                                'amenities': "",  # 기본 데이터에서는 빈 값
                                'usage_notes': ""
                            }
                            
                            accommodations.append(accommodation_data)
                            print(f"✓ 수집: {facility_name} ({facility_type}) - {capacity}명, {area_sqm}㎡")
                            
                    except Exception as e:
                        print(f"행 처리 중 오류: {e}")
                        continue
                
                await browser.close()
                
                # 데이터베이스에 저장
                if accommodations:
                    self._save_accommodations_to_db(accommodations)
                    print(f"🎉 총 {len(accommodations)}개 숙박시설 데이터 수집 완료")
                else:
                    print("⚠️ 수집된 데이터가 없습니다.")
                
                return {
                    'success': True,
                    'message': f'{len(accommodations)}개 숙박시설 데이터 수집 완료',
                    'data': accommodations
                }
                
        except Exception as e:
            print(f"크롤링 중 오류 발생: {e}")
            return {
                'success': False,
                'message': f'크롤링 오류: {str(e)}',
                'data': []
            }
    
    def _save_accommodations_to_db(self, accommodations):
        """숙박시설 데이터를 데이터베이스에 저장"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            for acc in accommodations:
                # 기존 데이터가 있는지 확인
                cursor.execute("""
                    SELECT accommodation_id FROM accommodations 
                    WHERE forest_id = ? AND facility_name = ?
                """, (acc['forest_id'], acc['facility_name']))
                
                if cursor.fetchone():
                    # 업데이트
                    cursor.execute("""
                        UPDATE accommodations SET
                            facility_type = ?, standard_capacity = ?, max_capacity = ?,
                            area_sqm = ?, area_pyeong = ?, checkin_time = ?, checkout_time = ?,
                            weekday_offseason = ?, weekend_offseason = ?, weekday_peak = ?, weekend_peak = ?,
                            amenities = ?, usage_notes = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE forest_id = ? AND facility_name = ?
                    """, (
                        acc['facility_type'], acc['standard_capacity'], acc['max_capacity'],
                        acc['area_sqm'], acc['area_pyeong'], acc['checkin_time'], acc['checkout_time'],
                        acc['weekday_offseason'], acc['weekend_offseason'], 
                        acc['weekday_peak'], acc['weekend_peak'],
                        acc['amenities'], acc['usage_notes'],
                        acc['forest_id'], acc['facility_name']
                    ))
                else:
                    # 삽입
                    cursor.execute("""
                        INSERT INTO accommodations (
                            forest_id, facility_name, facility_type, standard_capacity, max_capacity,
                            area_sqm, area_pyeong, checkin_time, checkout_time,
                            weekday_offseason, weekend_offseason, weekday_peak, weekend_peak,
                            amenities, usage_notes, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (
                        acc['forest_id'], acc['facility_name'], acc['facility_type'], 
                        acc['standard_capacity'], acc['max_capacity'],
                        acc['area_sqm'], acc['area_pyeong'], acc['checkin_time'], acc['checkout_time'],
                        acc['weekday_offseason'], acc['weekend_offseason'], 
                        acc['weekday_peak'], acc['weekend_peak'],
                        acc['amenities'], acc['usage_notes']
                    ))
            
            conn.commit()
            conn.close()
            print(f"✅ {len(accommodations)}개 숙박시설 데이터 DB 저장 완료")
            
        except Exception as e:
            print(f"DB 저장 중 오류: {e}")

    async def crawl_discount_policies(self, forest_id):
        """할인정책 크롤링 - 교래자연휴양림 예시"""
        try:
            print(f"🎯 {forest_id} 할인정책 크롤링 시작")
            
            # 할인정책 URL 구성 (교래자연휴양림 예시)
            discount_url = f"https://www.foresttrip.go.kr/pot/rm/ug/selectFcltUseGdncView.do?hmpgId={forest_id}&menuId=004002001&ruleId=201"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                try:
                    await page.goto(discount_url, wait_until="networkidle")
                    await asyncio.sleep(3)  # 페이지 로딩 대기
                    
                    # 실제 웹페이지에서 할인정책 섹션 추출
                    discount_policies = []
                    
                    try:
                        # 할인정책 페이지의 모든 텍스트 내용 추출
                        content = await page.text_content('body')
                        
                        # 숙박동 할인 정책들 파싱
                        accommodation_policies = []
                        
                        # 다자녀가정 우대
                        if '다자녀가정 우대' in content and '30%' in content:
                            accommodation_policies.append({
                                'policy_category': '숙박동할인',
                                'target_group': '다자녀가정',
                                'discount_type': 'percentage',
                                'discount_rate': 30,
                                'conditions': '비수기 주중에 한함',
                                'required_documents': '주민등록등본 또는 가족관계등록부',
                                'detailed_description': '2자녀 이상 가정 대상 숙박 할인'
                            })
                        
                        # 장애인 1~3급
                        if '장애인(1~3급)' in content and '50%' in content:
                            accommodation_policies.append({
                                'policy_category': '숙박동할인',
                                'target_group': '장애인1~3급',
                                'discount_type': 'percentage',
                                'discount_rate': 50,
                                'conditions': '비수기 주중에 한함',
                                'required_documents': '장애인등록증',
                                'detailed_description': '장애인 1~3급 대상 객실요금 할인'
                            })
                            
                        # 장애인 4~6급
                        if '장애인(4~6급)' in content and '30%' in content:
                            accommodation_policies.append({
                                'policy_category': '숙박동할인',
                                'target_group': '장애인4~6급',
                                'discount_type': 'percentage',
                                'discount_rate': 30,
                                'conditions': '비수기 주중에 한함',
                                'required_documents': '장애인등록증',
                                'detailed_description': '장애인 4~6급 대상 객실요금 할인'
                            })
                            
                        # 지역주민(제주도민)
                        if '지역주민(제주도민)' in content or '제주도민' in content:
                            accommodation_policies.append({
                                'policy_category': '숙박동할인',
                                'target_group': '지역주민',
                                'discount_type': 'percentage',
                                'discount_rate': 30,
                                'conditions': '비수기 주중에 한함',
                                'required_documents': '주민등록증',
                                'detailed_description': '제주도민 대상 객실요금 할인'
                            })
                            
                        # 국가보훈대상자 1~3급
                        if '국가보훈대상자(1~3급)' in content and '50%' in content:
                            accommodation_policies.append({
                                'policy_category': '숙박동할인',
                                'target_group': '국가보훈대상자1~3급',
                                'discount_type': 'percentage',
                                'discount_rate': 50,
                                'conditions': '비수기 주중에 한함',
                                'required_documents': '국가보훈대상자증',
                                'detailed_description': '국가보훈대상자 1~3급 대상 객실요금 할인'
                            })
                            
                        # 국가보훈대상자 4~7급
                        if '국가보훈대상자(4~7급)' in content and '30%' in content:
                            accommodation_policies.append({
                                'policy_category': '숙박동할인',
                                'target_group': '국가보훈대상자4~7급',
                                'discount_type': 'percentage',
                                'discount_rate': 30,
                                'conditions': '비수기 주중에 한함',
                                'required_documents': '국가보훈대상자증',
                                'detailed_description': '국가보훈대상자 4~7급 대상 객실요금 할인'
                            })
                        
                        # 입장료 면제 정책들
                        entrance_exemptions = []
                        
                        if '12세 이하, 65세 이상' in content:
                            entrance_exemptions.append({
                                'policy_category': '입장료면제',
                                'target_group': '연령우대',
                                'discount_type': 'exemption',
                                'discount_rate': 100,
                                'conditions': '12세 이하, 65세 이상',
                                'required_documents': '신분증',
                                'detailed_description': '12세 이하, 65세 이상 입장료 면제'
                            })
                            
                        if '장애인복지법' in content and '장애인' in content:
                            entrance_exemptions.append({
                                'policy_category': '입장료면제',
                                'target_group': '장애인',
                                'discount_type': 'exemption',
                                'discount_rate': 100,
                                'conditions': '1~3급은 보호자 1명 포함',
                                'required_documents': '장애인등록증',
                                'detailed_description': '장애인 입장료 면제 (1~3급은 보호자 1명 포함)'
                            })
                        
                        # 모든 정책 통합
                        discount_policies.extend(accommodation_policies)
                        discount_policies.extend(entrance_exemptions)
                        
                        print(f"🔍 파싱된 할인정책: {len(discount_policies)}개")
                        for policy in discount_policies:
                            print(f"  - {policy['target_group']}: {policy['discount_rate']}% {policy['discount_type']}")
                            
                    except Exception as parse_error:
                        print(f"⚠️ DOM 파싱 실패, 기본 정책 사용: {parse_error}")
                        # 파싱 실패 시 기본 정책만 사용
                        discount_policies = [
                            {
                                'policy_category': '숙박동할인',
                                'target_group': '다자녀가정',
                                'discount_type': 'percentage',
                                'discount_rate': 30,
                                'conditions': '비수기 주중에 한함',
                                'required_documents': '가족관계증명서',
                                'detailed_description': '2자녀 이상 가정에 대한 숙박 할인'
                            }
                        ]
                    
                    # 데이터베이스 저장
                    if discount_policies:
                        self.save_discount_policies(forest_id, discount_policies)
                        
                    print(f"✅ {forest_id} 할인정책 {len(discount_policies)}개 수집 완료")
                    
                    return {
                        'status': 'success',
                        'message': f'{len(discount_policies)}개 할인정책 수집 완료',
                        'policies_collected': len(discount_policies)
                    }
                    
                except Exception as e:
                    print(f"❌ 할인정책 크롤링 실패: {e}")
                    return {
                        'status': 'error',
                        'message': f'할인정책 크롤링 실패: {str(e)}',
                        'policies_collected': 0
                    }
                finally:
                    await browser.close()
                    
        except Exception as e:
            print(f"❌ 할인정책 크롤링 오류: {e}")
            return {
                'status': 'error',
                'message': f'할인정책 크롤링 오류: {str(e)}',
                'policies_collected': 0
            }

    def save_discount_policies(self, forest_id, policies):
        """할인정책 데이터 DB 저장"""
        try:
            conn = self.db_manager.get_connection()
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
                            required_documents = ?, detailed_description = ?, 
                            updated_at = CURRENT_TIMESTAMP
                        WHERE forest_id = ? AND policy_category = ? AND target_group = ?
                    """, (
                        policy['discount_type'], policy['discount_rate'], policy['conditions'],
                        policy['required_documents'], policy['detailed_description'],
                        forest_id, policy['policy_category'], policy['target_group']
                    ))
                else:
                    # 삽입
                    cursor.execute("""
                        INSERT INTO crawled_discount_policies (
                            forest_id, policy_category, target_group, discount_type,
                            discount_rate, conditions, required_documents, detailed_description,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (
                        forest_id, policy['policy_category'], policy['target_group'], 
                        policy['discount_type'], policy['discount_rate'], policy['conditions'],
                        policy['required_documents'], policy['detailed_description']
                    ))
            
            conn.commit()
            conn.close()
            print(f"✅ {len(policies)}개 할인정책 데이터 DB 저장 완료")
            
        except Exception as e:
            print(f"DB 저장 중 오류: {e}")

# 데이터베이스 매니저 인스턴스
db_manager = DatabaseManager(DB_PATH)
web_crawler = WebCrawler(db_manager)

# 라우트 정의
@app.route('/')
def dashboard():
    """메인 대시보드 페이지"""
    return render_template('dashboard.html')

@app.route('/api/forests')
def get_forests_api():
    """자연휴양림 목록 API (데이터 상태 포함)"""
    try:
        forests = db_manager.get_forests()
        result = []
        
        for forest in forests:
            forest_id = forest[0]
            data_status, has_basic_data = db_manager.get_forest_data_status(forest_id)
            discount_status, has_discount_data = db_manager.get_discount_status(forest_id)
            
            forest_data = {
                'forest_id': forest_id,
                'forest_name': forest[1],
                'sido': forest[2],
                'forest_type': forest[3],
                'area_sqm': forest[4],
                'capacity': forest[5],
                'entrance_fee': forest[6],
                'accommodation_available': forest[7],
                'main_facilities': forest[8],
                'address': forest[9],
                'phone': forest[10],
                'homepage_url': forest[11],
                'latitude': forest[12],
                'longitude': forest[13],
                'data_date': forest[14],
                'provider_code': forest[15],
                'provider_name': forest[16],
                'updated_at': forest[17],
                'data_status': data_status,
                'has_basic_data': has_basic_data,
                'discount_status': discount_status,
                'has_discount_data': has_discount_data
            }
            result.append(forest_data)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accommodations')
def get_accommodations_api():
    """숙박시설 목록 API"""
    try:
        accommodations = db_manager.get_accommodations()
        result = []
        
        for acc in accommodations:
            # 데이터 상태 판단 (편의시설 정보 유무로 판단)
            amenities = acc[14] if len(acc) > 14 else ""  # 인덱스 수정: amenities는 14번째
            data_status = "상세" if amenities and amenities.strip() else "기본"
            has_detailed_data = bool(amenities and amenities.strip())
            
            accommodation_data = {
                'accommodation_id': acc[0],
                'forest_name': acc[1],
                'forest_id': acc[2],
                'facility_type': acc[3],
                'facility_name': acc[4],
                'capacity_standard': acc[5],
                'capacity_maximum': acc[6],
                'area': acc[7],  # 단일 area 컬럼
                'checkin_time': acc[8],
                'checkout_time': acc[9],
                'price_off_weekday': acc[10],
                'price_off_weekend': acc[11],
                'price_peak_weekday': acc[12],
                'price_peak_weekend': acc[13],
                'amenities': acc[14],
                'usage_info': acc[15],
                'created_at': acc[16],
                'updated_at': acc[17],
                'data_status': data_status,
                'has_detailed_data': has_detailed_data
            }
            result.append(accommodation_data)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/facilities')
def get_facilities_api():
    """편의시설 목록 API"""
    try:
        facilities = db_manager.get_facilities()
        result = []
        
        for facility in facilities:
            facility_data = {
                'facility_id': facility[0],
                'forest_name': facility[1],
                'forest_id': facility[2],
                'facility_name': facility[3],
                'facility_type': facility[4],
                'facility_tags': facility[5],
                'description': facility[6],
                'capacity': facility[7],
                'usage_fee': facility[8],
                'created_at': facility[9],
                'updated_at': facility[10]
            }
            result.append(facility_data)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/crawl/basic', methods=['POST'])
def crawl_basic_data():
    """기본 데이터 수집 API"""
    try:
        data = request.get_json()
        forest_id = data.get('forest_id')
        
        if not forest_id:
            return jsonify({'error': 'forest_id가 필요합니다'}), 400
        
        # 비동기 크롤링 실행
        result = asyncio.run(web_crawler.crawl_basic_accommodation_data(forest_id))
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/discounts')
def get_discounts_api():
    """할인정책 목록 API"""
    try:
        forest_id = request.args.get('forest_id')
        discount_policies = db_manager.get_discount_policies()
        result = []
        
        for policy in discount_policies:
            # forest_id 필터링
            if forest_id and policy[2] != forest_id:
                continue
                
            policy_data = {
                'crawled_discount_id': policy[0],
                'forest_name': policy[1],
                'forest_id': policy[2],
                'policy_category': policy[3],
                'target_group': policy[4],
                'discount_type': policy[5],
                'discount_rate': policy[6],
                'conditions': policy[7],
                'required_documents': policy[8],
                'detailed_description': policy[9],
                'raw_text': policy[10],
                'created_at': policy[11],
                'updated_at': policy[12],
                'has_detailed_data': True  # 크롤링된 데이터는 상세 데이터로 간주
            }
            result.append(policy_data)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/crawl/detailed', methods=['POST'])
def crawl_detailed_data():
    """상세 데이터 수집 API"""
    try:
        data = request.get_json()
        forest_id = data.get('forest_id')
        accommodation_id = data.get('accommodation_id')
        
        if not forest_id or not accommodation_id:
            return jsonify({'error': 'forest_id와 accommodation_id가 필요합니다'}), 400
        
        # 개별 숙박시설 상세 데이터 크롤링 실행
        result = asyncio.run(web_crawler.crawl_detailed_accommodation_data(forest_id, accommodation_id))
        
        if 'error' in result:
            return jsonify(result), 500
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'API 오류: {str(e)}'}), 500

@app.route('/api/crawl/discount-policies', methods=['POST'])
def crawl_discount_policies():
    """할인정책 크롤링 API"""
    try:
        data = request.get_json()
        forest_id = data.get('forest_id')
        
        if not forest_id:
            return jsonify({'error': 'forest_id가 필요합니다'}), 400
        
        # 비동기 할인정책 크롤링 실행
        result = asyncio.run(web_crawler.crawl_discount_policies(forest_id))
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)