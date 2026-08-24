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
        except Exception as e:
            print(f"⚠️ 기존 데이터 로드 실패: {e}")
            existing_data = []
    
    # 중복 체크를 위한 이미지 URL 집합
    existing_urls = {item['img'] for item in existing_data if 'img' in item}

    async with async_playwright() as p:
        print("🚀 [최적화 모드] 서대구제일교회 갤러리 수집을 시작합니다.")
        # GitHub Actions 및 로컬 실행을 위해 headless=True 권장
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        new_photos = []
        target_post_count = 10  # 매 실행 시 최신글 10개 검사

        try:
            for i in range(target_post_count):
                try:
                    print(f"📂 [{i+1}/{target_post_count}] 게시글 탐색 중...")
                    await page.goto(START_URL, wait_until="networkidle", timeout=20000)
                    
                    # 게시판 iframe 찾기
                    board_frame = None
                    for f in page.frames:
                        try:
                            content = await f.content()
                            if "조회" in content or "제목" in content:
                                board_frame = f
                                break
                        except Exception:
                            continue
                    
                    if not board_frame:
                        print("   ⚠️ 게시판 프레임을 찾지 못했습니다. 건너뜁니다.")
                        continue

                    # 게시글 링크 추출 (다운로드/첨부파일 링크 제외)
                    all_a = await board_frame.query_selector_all("a")
                    valid_posts = []
                    for a in all_a:
                        text = (await a.inner_text()).strip()
                        href = await a.get_attribute("href") or ""
                        if "다운로드" in text or "파일" in text or len(text) < 2:
                            continue
                        if "javascript" in href or "idx=" in href or "sub.html" in href:
                            valid_posts.append(a)

                    if i >= len(valid_posts):
                        print(f"   ℹ️ 더 이상 유효한 게시글이 없습니다 (총 {len(valid_posts)}개 발견).")
                        break

                    # 해당 게시글 클릭하여 진입
                    target_post = valid_posts[i]
                    post_title = (await target_post.inner_text()).strip()
                    
                    await target_post.click()
                    try:
                        await page.wait_for_load_state("networkidle", timeout=8000)
                    except Exception:
                        pass
                    await asyncio.sleep(1.5)

                    # 게시물 내 모든 본문 사진 수집
                    found_in_post = 0
                    post_new_photos = []

                    for f in page.frames:
                        try:
                            imgs = await f.query_selector_all("img")
                        except Exception:
                            continue
                        
                        for img in imgs:
                            try:
                                src = await img.get_attribute("src")
                                if not src:
                                    continue
                                
                                # UI 아이콘, 버튼 등 제외
                                lower_src = src.lower()
                                if any(k in lower_src for k in ['icon', 'btn', 'logo', 'design', 'common', 'skin', 'blank', 'arrow']):
                                    continue
                                
                                box = await img.bounding_box()
                                if box and box['width'] > 180 and box['height'] > 100:
                                    full_src = src if src.startswith('http') else BASE_URL + (src if src.startswith('/') else '/' + src)
                                    
                                    if full_src not in existing_urls:
                                        post_new_photos.append({"title": post_title, "img": full_src})
                                        existing_urls.add(full_src)
                                        found_in_post += 1
                            except Exception:
                                continue
                    
                    if found_in_post > 0:
                        print(f"   ✨ [{post_title}] 새 사진 {found_in_post}장 수집 완료")
                        new_photos.extend(post_new_photos)
                    else:
                        print(f"   ✓ [{post_title}] 새 사진 없음 (이미 수집됨)")
                
                except Exception as e:
                    print(f"   ⚠️ 게시글 {i+1}번 처리 중 오류 발생 (건너뜀): {e}")

            # 2. 결과 합치기: [새 사진] + [기존 사진]
            final_data = new_photos + existing_data
            
            # 3. 데이터 상한선 유지 (최신 1,000개 유지)
            final_data = final_data[:1000]

            # 4. 결과 JSON 저장
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=4)
            
            print(f"\n🎉 갤러리 데이터 수집 및 업데이트 완료! (신규: {len(new_photos)}개 / 총합: {len(final_data)}개)")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(get_photos())
