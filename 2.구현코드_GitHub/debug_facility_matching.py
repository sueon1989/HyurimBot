#!/usr/bin/env python3
"""
Debug script for facility matching logic
"""
import asyncio
from playwright.async_api import async_playwright

async def debug_webpage_structure():
    """웹페이지의 테이블 구조를 분석하고 시설명 매칭을 테스트"""
    
    url = "https://www.foresttrip.go.kr/pot/rm/fa/selectFcltsArmpListView.do?hmpgId=ID02030014&menuId=002002001#siteNo2"
    target_facility_name = "101호. 연산홍"
    
    print(f"🎯 대상 시설명: '{target_facility_name}'")
    print(f"📍 URL: {url}")
    print("=" * 80)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # WSL에서는 headless 모드 사용
        page = await browser.new_page()
        
        try:
            print("1. 페이지 로딩 중...")
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(3000)
            
            print("2. 테이블 구조 분석...")
            
            # 숙박시설 테이블 찾기
            table_selector = "table tbody tr"
            rows = await page.query_selector_all(table_selector)
            
            print(f"발견된 테이블 행 수: {len(rows)}")
            
            # 각 행의 구조 분석
            for i, row in enumerate(rows[:5]):  # 처음 5개 행만 분석
                cells = await row.query_selector_all("td")
                
                print(f"\n--- 행 {i+1} ---")
                print(f"셀 수: {len(cells)}")
                
                for j, cell in enumerate(cells[:4]):  # 처음 4개 컬럼만
                    try:
                        text = await cell.inner_text()
                        print(f"  컬럼 {j}: '{text.strip()}'")
                    except:
                        print(f"  컬럼 {j}: (읽기 실패)")
            
            print("\n" + "=" * 50)
            print("3. 목표 시설 검색...")
            
            # 실제 매칭 로직 테스트
            found_facility = False
            for i, row in enumerate(rows):
                try:
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 2:
                        facility_type = await cells[0].inner_text()
                        facility_name = await cells[1].inner_text()
                        
                        # 정확한 매칭 확인
                        if facility_name.strip() == target_facility_name:
                            found_facility = True
                            print(f"✅ 정확한 매칭 발견!")
                            print(f"   행 번호: {i+1}")
                            print(f"   시설 유형: '{facility_type.strip()}'")
                            print(f"   시설명: '{facility_name.strip()}'")
                            
                            # 상세보기 버튼 확인
                            detail_link = await row.query_selector("a[href*='#siteNo'], a[onclick*='runParse'], a:has-text('상세보기')")
                            if detail_link:
                                print("   상세보기 링크: 발견됨")
                                
                                # 테스트로 클릭해보기
                                print("4. 상세보기 클릭 테스트...")
                                await detail_link.evaluate('el => el.click()')
                                await page.wait_for_timeout(3000)
                                
                                # 팝업이 열렸는지 확인
                                popup_title = await page.query_selector(".layer_wrap h2")
                                if popup_title:
                                    title_text = await popup_title.inner_text()
                                    print(f"   팝업 제목: '{title_text}'")
                                    
                                    # 가격 테이블 확인
                                    price_tables = await page.query_selector_all(".layer_wrap table")
                                    for table in price_tables:
                                        table_text = await table.inner_text()
                                        if "가격정보" in table_text or "비수기" in table_text:
                                            print("   가격 테이블 발견!")
                                            print(f"   가격 테이블 내용 일부: {table_text[:200]}...")
                                            break
                                else:
                                    print("   팝업이 열리지 않았음")
                            else:
                                print("   상세보기 링크: 찾을 수 없음")
                            break
                        
                        # 부분 매칭 확인 (디버깅용)
                        elif target_facility_name in facility_name or facility_name in target_facility_name:
                            print(f"🔍 부분 매칭 발견: '{facility_name.strip()}'")
                            
                except Exception as e:
                    print(f"   행 {i+1} 처리 중 오류: {e}")
                    continue
            
            if not found_facility:
                print("❌ 목표 시설을 찾을 수 없음")
                
                # 모든 시설명 출력 (디버깅용)
                print("\n모든 시설명 목록:")
                for i, row in enumerate(rows[:10]):
                    try:
                        cells = await row.query_selector_all("td")
                        if len(cells) >= 2:
                            facility_name = await cells[1].inner_text()
                            print(f"  {i+1:2d}. '{facility_name.strip()}'")
                    except:
                        continue
        
        finally:
            # 잠시 대기 후 종료 (수동으로 확인할 시간)
            print("\n5초 후 브라우저 종료...")
            await page.wait_for_timeout(5000)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_webpage_structure())