# SKILL: build-dashboard

## 현재 구조 (중요)
대시보드는 **라이브 페이지**다: `dashboard/index.html` 이 로컬 서버(http://127.0.0.1:8787/status)에서
실시간 데이터를 가져와 표시한다. **파일을 재생성하지 말 것** — 데이터는 항상 최신이다.

## 트리거별 동작
- "/dashboard", "현황 보여줘" → `open dashboard/index.html` 로 열기만 한다
- 디자인 수정 요청 시에만 dashboard/index.html 의 HTML/CSS 수정 (fetch 로직과 카드 id는 유지)

## 앵커 (바탕화면 캐릭터 연동 — 필수 유지)
- 각 habit 카드 id: "dev", "realestate", "piano", "language"
- URL 해시로 열리면 해당 카드로 스크롤 + 2초 글로우 (이미 구현됨)

## 데이터 추가가 필요한 경우
서버(server/server.py)의 /status 응답을 확장하고 대시보드가 그 필드를 읽게 한다.
서버 수정 후 재시작: launchctl kickstart -k gui/$(id -u)/com.habit-agents.server
