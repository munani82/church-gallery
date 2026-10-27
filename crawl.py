import asyncio
from playwright.async_api import async_playwright
import json
import os

BASE_URL = "http://www.seodaegu.net"
DATA_FILE = "photos.json"

TARGET_SECTIONS = [
    {
        "name": "교회앨범",
        "category": "album",
        "url": "http://www.seodaegu.net/main/sub.html?pageCode=25"
    },
    {
        "name": "주보",
        "category": "bulletin",
        "url": "http://www.seodaegu.net/main/sub.html?pageCode=24"
    }
]

async def get_photos():
    # 1. 기존 데이터 불러오기 및 카테고리 보정
    existing_data = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf_8') as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"기존 데이터 로드 실패: {e}")
            existing_data = []

    # 기존 데이터 카테고리 필드 보정 (구버전 호환)
    for item in existing_data:
        if "category" not in item:
            img_url = item.get("img", "")
            item["category"] = "bulletin" if "www24" in img_url else "album"

    existing_urls = {item['img'] for item in existing_data if 'img' in item}

    async with async_playwright() as p:
        print("서대구제일교회 갤러리 및 주보 통합 수집을 시작합니다.")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        new_photos = []
        target_post_count = 10  # 각 섹션별 최신 게시글 10개 검사

        try:
            for section in TARGET_SECTIONS:
                sec_name = section["name"]
                sec_category = section["category"]
                sec_url = section["url"]
                print(f"\n========================================")
                print(f"[{sec_name}] 수집 시작: {sec_url}")
                print(f"========================================")

                for i in range(target_post_count):
                    try:
                        print(f"[{sec_name}] [{i + 1}/{target_post_count}] 게시글 탐색 중...")
                        await page.goto(sec_url, wait_until="networkidle", timeout=25000)

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
                            board_frame = page.main_frame

                        all_a = await board_frame.query_selector_all("a")
                        valid_posts = []
                        for a in all_a:
                            text = (await a.inner_text()).strip()
                            href = await a.get_attribute("href") or ""
                            onclick = await a.get_attribute("onClick") or await a.get_attribute("onclick") or ""
                            if "다운로드" in text or "파일" in text or len(text) < 2:
                                continue
                            if sec_category == "bulletin":
                                if "permitCheck" in onclick or "javascript" in href or "idx=" in href or "sub.html" in href:
                                    if any(kw in text for kw in ["주보", "년", "월", "일"]):
                                        valid_posts.append(a)
                            else:
                                if "javascript" in href or "idx=" in href or "sub.html" in href:
                                    valid_posts.append(a)

                        if i >= len(valid_posts):
                            print(f"더 이상 유효한 게시글이 없습니다. (총 {len(valid_posts)}개 발견)")
                            break

                        target_post = valid_posts[i]
                        post_title = (await target_post.inner_text()).strip()

                        await target_post.click()
                        try:
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        except Exception:
                            pass
                        await asyncio.sleep(1.5)

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

                                    lower_src = src.lower()
                                    if any(k in lower_src for k in ['icon', 'btn', 'logo', 'design', 'common', 'skin', 'blank', 'arrow']):
                                        continue

                                    box = await img.bounding_box()
                                    if box and box['width'] > 150 and box['height'] > 100:
                                        full_src = src if src.startswith('http') else BASE_URL + (src if src.startswith('/') else '/' + src)

                                        if full_src not in existing_urls:
                                            post_new_photos.append({
                                                "title": post_title,
                                                "img": full_src,
                                                "category": sec_category
                                            })
                                            existing_urls.add(full_src)
                                            found_in_post += 1
                                except Exception:
                                    continue

                        if found_in_post > 0:
                            print(f"새 사진 {found_in_post}장 수집 완료: {post_title}")
                            new_photos.extend(post_new_photos)
                        else:
                            print(f"새 사진 없음 (이미 수집됨): {post_title}")

                    except Exception as e:
                        print(f"게시글 {i + 1}번 처리 중 오류 발생: {e}")

            # 2. 결과 합치기
            final_data = new_photos + existing_data

            # 3. 데이터 상한선 유지 (최신 1500개 유지)
            final_data = final_data[:1500]

            # 4. 결과 JSON 저장
            with open(DATA_FILE, 'w', encoding='utf_8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=4)

            print(f"\n데이터 수집 및 업데이트 완료 (신규: {len(new_photos)}개 / 총합: {len(final_data)}개)")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(get_photos())
