# 중간 분석 보고서: 서대구제일교회 주보 크롤링 타당성 및 구조 검증

## 1. 개요
서대구제일교회 웹사이트에서 갤러리 앨범 외에 주보(pageCode 24)를 수집하여 신규 카테고리로 분리 제공하기 위한 크롤링 타당성을 검증했습니다.

## 2. 수집 대상 구조 분석
* 교회 앨범 페이지: http://www.seodaegu.net/main/sub.html?pageCode=25 (게시판 아이디: www25)
* 교회 주보 페이지: http://www.seodaegu.net/main/sub.html?pageCode=24 (게시판 아이디: www24)
* 두 게시판 모두 anyboard 솔루션 기반으로 동작하며 구조가 일치합니다.
* 주보 상세 페이지 내부 본문 iframe(/core/anyboard/content.html)에 주보 고화질 이미지(보통 면당 1장씩 총 2장)가 정상 탑재되어 있음을 확인했습니다.

## 3. 검증 결과
* 테스트 스크립트(scripts/01_test_bulletin_crawl.py)를 통해 주보 최신 게시글 15건을 정상 감지했습니다.
* 최신 주보(26년 10월 25일 주보) 상세 진입 후 2장의 주보 원본 이미지를 누락 없이 정상 추출 완료했습니다.

## 4. 향후 작업 계획
1. crawl.py 스크립트를 개선하여 교회 앨범과 주보를 둘 다 수집하도록 확장
2. photos.json 데이터에 category 속성(album 또는 bulletin) 부여
3. index.html 화면에 카테고리 전환 탭(전체, 교회앨범, 주보) 추가 및 디자인 고도화
