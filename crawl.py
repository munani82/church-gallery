import asyncio
from playwright.async_api import async_playwright
import json
import os

START_URL = "http://www.seodaegu.net/main/sub.html?pageCode=25"
BASE_URL = "http://www.seodaegu.net"
DATA_FILE = "photos.json"

async def get_photos():
    # 1. 기존 데이터 불러오기
    existing_data = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except:
            existing_data = []
    
    # 중복 체크를 위한 이미지 URL 집합 (비교 속도를 위해 set 사용)
    existing_urls = {item['img'] for item in existing_data}

    async with async_playwright() as p:
        print("🚀 [업데이트 모드] 수집을 시작합니다.")
        # GitHub Actions에서 실행될 때는 headless=True여야 합니다.
        browser = await p.chromium.launch(headless=True) 
        page = await browser.new_page()

        new_photos = []
        target_post_count = 10 # 매일 최신글 10개만 검사해도 충분합니다.

        try:
            for i in range(target_post_count):
                print(f"📂 [{i+1}/{target_post_count}] 게시글 확인 중...")
                await page.goto(START_URL, wait_until="networkidle")
                
                # 게시판 프레임 찾기
                board_frame = None
                for f in page.frames:
                    if "조회" in await f.content():
                        board_frame = f
                        break
                if not board_frame: continue

                # 링크 추출 및 다운로드 제외 필터링
                all_a = await board_frame.query_selector_all("a")
                valid_posts = []
                for a in all_a:
                    text = await a.inner_text()
                    href = await a.get_attribute("href") or ""
                    if "다운로드" in text or "파일" in text or len(text.strip()) < 2:
                        continue
                    if "javascript" in href or "idx=" in href:
                        valid_posts.append(a)

                if i >= len(valid_posts): break

                # 게시글 진입
                target_post = valid_posts[i]
                post_title = (await target_post.inner_text()).strip()
                
                await target_post.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2) 

                # 게시물 내 모든 고화질 사진 수집
                found_in_post = 0
                for f in page.frames:
                    imgs = await f.query_selector_all("img")
                    for img in imgs:
                        src = await img.get_attribute("src")
                        if not src: continue
                        
                        # 아이콘 제외 필터
                        if any(k in src.lower() for k in ['icon', 'btn', 'logo', 'design', 'common', 'skin', 'blank']):
                            continue
                        
                        box = await img.bounding_box()
                        if box and box['width'] > 200:
                            full_src = src if src.startswith('http') else BASE_URL + (src if src.startswith('/') else '/' + src)
                            
                            # [핵심] 중복 체크: 이미 있는 사진이면 패스!
                            if full_src not in existing_urls:
                                new_photos.append({"title": post_title, "img": full_src})
                                existing_urls.add(full_src)
                                found_in_post += 1
                
                if found_in_post > 0:
                    print(f"   ✨ 새 사진 {found_in_post}장 추가됨: {post_title}")
                else:
                    # 첫 번째 사진이 이미 중복이라면, 그 이후 글들도 중복일 확률이 높으므로 
                    # 여기서 멈춰도 되지만 안전하게 끝까지 확인합니다.
                    pass

            # 2. 합치기: [새 사진] + [기존 사진] 순서로 합쳐 최신순 유지
            final_data = new_photos + existing_data
            
            # 3. 데이터 무제한 증가 방지 (최신 1,000개만 유지)
            final_data = final_data[:1000]

            # 4. 결과 저장
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=4)
            
            print(f"\n✅ 업데이트 완료! (새로 추가: {len(new_photos)}개 / 총합: {len(final_data)}개)")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(get_photos())
