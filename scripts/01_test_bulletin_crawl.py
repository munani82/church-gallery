import asyncio
from playwright.async_api import async_playwright
import json
import os

BULLETIN_URL = "http://www.seodaegu.net/main/sub.html?pageCode=24"
ALBUM_URL = "http://www.seodaegu.net/main/sub.html?pageCode=25"
BASE_URL = "http://www.seodaegu.net"

async def test_crawl():
    async with async_playwright() as p:
        print("서대구제일교회 크롤링 테스트 시작")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 1. 주보 크롤링 테스트 (최신 3개)
        print(f"주보 페이지 접속: {BULLETIN_URL}")
        await page.goto(BULLETIN_URL, wait_until="networkidle", timeout=30000)

        # 게시판 프레임 탐색
        target_frame = None
        for f in page.frames:
            try:
                cnt = await f.content()
                if "조회" in cnt or "제목" in cnt:
                    target_frame = f
                    break
            except Exception:
                continue

        if not target_frame:
            target_frame = page.main_frame

        all_links = await target_frame.query_selector_all("a")
        bulletin_posts = []
        for a in all_links:
            text = (await a.inner_text()).strip()
            href = await a.get_attribute("href") or ""
            onclick = await a.get_attribute("onClick") or await a.get_attribute("onclick") or ""
            if "다운로드" in text or "파일" in text or len(text) < 2:
                continue
            if "javascript" in href or "idx=" in href or "sub.html" in href or "permitCheck" in onclick:
                if any(kw in text for kw in ["주보", "년", "월", "일"]):
                    bulletin_posts.append((text, a))

        print(f"발견된 주보 후보 게시글: {len(bulletin_posts)}개")
        for idx, (title, elem) in enumerate(bulletin_posts[:3]):
            print(f"[{idx + 1}] 제목: {title}")

        # 첫 번째 주보 상세 진입 테스트
        if bulletin_posts:
            target_title, target_elem = bulletin_posts[0]
            print(f"첫번째 주보 클릭: {target_title}")
            await target_elem.click()
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await asyncio.sleep(2)

            # 본문 내 이미지 수집 테스트
            found_imgs = []
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
                        if any(k in lower_src for k in ["icon", "btn", "logo", "design", "common", "skin", "blank", "arrow"]):
                            continue
                        box = await img.bounding_box()
                        if box and box["width"] > 150 and box["height"] > 100:
                            full_src = src if src.startswith("http") else BASE_URL + (src if src.startswith("/") else "/" + src)
                            found_imgs.append(full_src)
                    except Exception:
                        continue

            print(f"주보 본문에서 발견된 본문 이미지: {len(found_imgs)}개")
            for img_url in found_imgs:
                print(f" * 이미지 URL: {img_url}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_crawl())
