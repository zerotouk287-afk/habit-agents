# 🐶 habit-agents — 반려동물이 내 습관을 관리하는 바탕화면

마우스를 화면 아래로 내리면 캐릭터들이 출근합니다. 오늘 안 한 습관의 캐릭터는 흑백으로 기다리고,
클릭해서 기록하면 컬러로 부활하면서 노션에 자동 저장됩니다.

📖 **전체 제작 가이드 (캐릭터 만드는 법 포함):** [노션 가이드 링크 넣기]

## 빠른 시작

```bash
# 1. 받기
git clone <이 레포> ~/habit-agents
cd ~/habit-agents

# 2. 내 습관 설정
cp data/goals.json.example data/goals.json
#    → goals.json을 열어 습관/목표/노션 DB ID를 내 것으로 수정

# 3. 노션 연결
#    notion.so/profile/integrations 에서 통합 생성 → 시크릿 복사
#    노션에서 습관 DB들의 부모 페이지 ⋯ → 연결 → 통합 추가 (필수!)
echo 'ntn_내시크릿' > .notion_token

# 4. 서버 자동 실행 등록
sed -i '' "s|__HOME__|$HOME|g" server/com.habit-agents.server.plist
cp server/com.habit-agents.server.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.habit-agents.server.plist
curl http://127.0.0.1:8787/status   # JSON 나오면 성공

# 5. 캐릭터: 데모용 말티즈 4마리(뽀삐 🐶)가 desktop/에 포함되어 있어 바로 작동합니다.
#    내 반려동물로 바꾸려면 가이드 Step 4를 따라 webp를 만들어 교체하세요.
#    파일명은 goals.json의 습관 ID와 동일하게: dev.webp, piano.webp ...

# 6. Plash(App Store) 설치 → Add Website → desktop/index.html 파일 선택 → Browsing Mode ON
```

## 필수 설정 체크리스트

- [ ] `data/goals.json` — 내 습관 ID/목표/노션 DB ID (기본 예시는 데모 캐릭터 4마리와 1:1 매칭)
- [ ] `desktop/index.html` 상단 `CHARS` 배열 — 습관 구성을 바꿨다면 ID/파일명 함께 수정
- [ ] `.notion_token` — 노션 통합 시크릿
- [ ] 노션 DB 속성: 이름(제목)/날짜(날짜)/분(숫자)/태그(선택)/주차(텍스트)
- [ ] (선택) `server/server.py` 상단 `REPORT_PARENT_PAGE` — 주간 리포트를 받을 노션 페이지 ID
- [ ] (선택) `REMINDER_TIME` — 리마인더 시각 (기본 21:00)

## 구조

```
server/server.py      로컬 서버: 기록 저장, 노션 동기화, 통계, 리마인더, 주간 리포트
desktop/index.html    바탕화면 캐릭터 (Plash로 표시) + 데모 캐릭터 webp 4개 포함
dashboard/index.html  라이브 대시보드 → http://127.0.0.1:8787/dashboard
data/goals.json       습관/목표 설정 (gitignore 됨 — 개인 설정)
data/logs/*.jsonl     기록 원본 (gitignore 됨 — 개인 데이터)
CLAUDE.md, skills/    Claude Code로도 기록/조회하고 싶을 때의 에이전트 지침 (선택)
```

기록은 로컬 jsonl이 원본이고 노션은 동기화 사본입니다. 모든 통계(레벨·스트릭·잔디)는 로그에서 매번 재계산됩니다.

## 라이선스 / 크레딧

자유롭게 쓰고 고치세요. dyno.kr님의 바탕화면 AI 직원 영상에서 영감을 받았습니다.
