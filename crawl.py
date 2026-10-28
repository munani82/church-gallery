import asyncio
from playwright.async_api import async_playwright
import json
import os
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
import requests
import pymupdf

BASE_URL = "http://www.seodaegu.net"
DATA_FILE = "photos.json"

GBS_USER_ID = os.environ.get("GBS_USER_ID", "munani82")
GBS_USER_PW = os.environ.get("GBS_USER_PW", "mm3243")
GBS_OUTPUT_DIR = "gbs"

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


def get_target_sundays(weeks_back=3):
    """돌아오는 주일(또는 오늘이 주일이면 오늘)부터 과거 N주간의 주일 날짜(YYYY-MM-DD) 리스트 반환 (오래된 순 -> 최신 순)"""
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    # Python weekday(): 월=0 ... 토=5, 일=6
    days_until_sunday = (6 - now.weekday()) % 7
    next_sunday = now + timedelta(days=days_until_sunday)
    sundays = []
    for w in range(weeks_back, -1, -1):
        d = next_sunday - timedelta(weeks=w)
        sundays.append(d.strftime("%Y-%m-%d"))
    return sundays


def crawl_gbs_guides(existing_urls):
    """365qt.com에서 GBS 인도자 지침서 PDF를 다운로드하고 고해상도 이미지로 변환하여 반환"""
    print("\n========================================")
    print("[GBS 지침서] 365qt.com 수집 시작")
    print("========================================")

    os.makedirs(GBS_OUTPUT_DIR, exist_ok=True)
    sundays = get_target_sundays(weeks_back=3)
    new_gbs_items = []

    session = requests.Session()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    session.headers.update({"User-Agent": ua})

    logged_in = False

    # 최신 주일이 리스트 맨 앞에 오도록 역순(최신순)으로 처리
    for target_date in reversed(sundays):
        first_page_rel = f"{GBS_OUTPUT_DIR}/{target_date}_page_1.png"
        if first_page_rel in existing_urls and os.path.exists(first_page_rel):
            print(f"[GBS 지침서] 이미 수집됨: {target_date}")
            continue

        try:
            if not logged_in:
                login_url = f"https://www.365qt.com/User/Login?returnurl=%2FQT%2FGbs%2F{target_date}"
                r1 = session.get(login_url, timeout=15)
                token_match = re.search(
                    r'name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"',
                    r1.text
                )
                if not token_match:
                    print("[GBS 지침서] 로그인 토큰 추출 실패")
                    break
                token = token_match.group(1)

                session.post(
                    "https://www.365qt.com/User/Login",
                    data={
                        "USER_ID": GBS_USER_ID,
                        "Password": GBS_USER_PW,
                        "__RequestVerificationToken": token,
                        "RememberMe": "false"
                    },
                    headers={"Referer": login_url},
                    allow_redirects=False,
                    timeout=15
                )
                logged_in = True

            page_url = f"https://www.365qt.com/QT/Gbs/{target_date}"
            r_page = session.get(page_url, timeout=15)
            fn_match = (
                re.search(r'id=["\']oldFILE_NM["\'][^>]+value=["\']([^"\']+)["\']', r_page.text, re.I)
                or re.search(r'name=["\']oldFILE_NM["\'][^>]+value=["\']([^"\']+)["\']', r_page.text, re.I)
            )
            if not fn_match:
                print(f"[GBS 지침서] {target_date} 자료가 아직 등록되지 않았습니다.")
                continue

            real_fn = fn_match.group(1)
            dl_url = f"https://www.365qt.com/QT/File/FileDownloadProc/?fn={urllib.parse.quote(real_fn)}"
            pdf_res = session.get(dl_url, headers={"Referer": page_url}, timeout=25)

            if pdf_res.status_code != 200 or len(pdf_res.content) < 1000:
                print(f"[GBS 지침서] {target_date} PDF 다운로드 실패")
                continue

            pdf_rel_path = f"{GBS_OUTPUT_DIR}/{target_date}_인도자지침서.pdf"
            with open(pdf_rel_path, "wb") as pf:
                pf.write(pdf_res.content)

            doc = pymupdf.open(stream=pdf_res.content, filetype="pdf")
            first_text_lines = [line.strip() for line in doc[0].get_text().splitlines() if line.strip()]
            lesson_subtitle = ""
            if first_text_lines:
                # 예: '1과: 회복의 최우선은 예배!(58분)' -> '(58분)' 제거 후 깔끔하게 표시
                raw_sub = re.sub(r"\(\d+분\)", "", first_text_lines[0]).strip()
                lesson_subtitle = f" - {raw_sub}"

            dt_obj = datetime.strptime(target_date, "%Y-%m-%d")
            post_title = f"{dt_obj.strftime('%y년 %m월 %d일')} GBS 인도자 지침서{lesson_subtitle} ({dt_obj.strftime('%y.%m.%d')})"

            for page_idx in range(len(doc)):
                page_obj = doc[page_idx]
                pix = page_obj.get_pixmap(dpi=200)
                img_rel_path = f"{GBS_OUTPUT_DIR}/{target_date}_page_{page_idx + 1}.png"
                pix.save(img_rel_path)

                if img_rel_path not in existing_urls:
                    new_gbs_items.append({
                        "title": post_title,
                        "img": img_rel_path,
                        "category": "gbs",
                        "pdf": pdf_rel_path
                    })
                    existing_urls.add(img_rel_path)

            doc.close()
            print(f"[GBS 지침서] 수집 및 이미지 변환 완료: {post_title}")

        except Exception as e:
            print(f"[GBS 지침서] {target_date} 처리 중 오류: {e}")

    return new_gbs_items

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

    # 1.5 GBS 인도자 지침서 수집 (365qt.com)
    new_gbs = crawl_gbs_guides(existing_urls)

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

            # 2. 결과 합치기 (신규 GBS + 신규 앨범/주보 + 기존 데이터)
            final_data = new_gbs + new_photos + existing_data

            # 3. 데이터 상한선 유지 (최신 1500개 유지)
            final_data = final_data[:1500]

            # 4. 결과 JSON 저장
            with open(DATA_FILE, 'w', encoding='utf_8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=4)

            print(f"\n데이터 수집 및 업데이트 완료 (신규 GBS: {len(new_gbs)}장, 신규 사진/주보: {len(new_photos)}장 / 총합: {len(final_data)}장)")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(get_photos())
