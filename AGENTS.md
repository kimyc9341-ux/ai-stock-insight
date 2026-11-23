# AGENTS.md — `ai-stock-insight` (내 계좌 심폐소생술)

이 문서는 이 저장소에서 작업하는 AI 에이전트가 프로젝트 구조, 팀 역할, 핵심 규칙을 즉시 파악하고 일관되게 작업하기 위한 안내서입니다.

---

## 1. 프로젝트 개요 및 주요 파일
- **프론트엔드 (SPA)**: `index.html` — 홈 대시보드(4대 지수 · 검색 · AI Top 6), 메뉴 탭, `💬 빠른 실행`, `🛡️ 보안통제실`
- **백엔드 API (Render FastAPI)**: `api_server.py`, `stock_service.py` — 실시간 시세·재무·뉴스, DART 공시(`/api/external/dart`), Gemini 분석(`/api/external/gemini-analyze`), Supabase 인증·감사 로그(`/api/audit-logs`)
- **데이터 수집**: `build_data.py`, `auto_monitor.py`, `data/stocks.json` (4,332개 상장 종목)
- **연관 매뉴얼**:
  - `ROUTINE_MANUAL.md` — 3대 자동화 루틴 절차서 (SOP)
  - `CALL_FLOW_SUMMARY.md` — 주요 요청 → 기존 함수 → 화면 출력 DOM 매핑

---

## 2. 3개 에이전트(기능) 팀 구성
1. **📊 사용자 추천·리서치 팀 (루틴 1)**
   - 전체 4,332개 종목 스캔 → `🏆 오늘의 AI 자동 선정 Top 6 리서치 리포트` (`renderDailyTop2Report`)
   - `🏛️ 안정 대장주` (시총 상위 50대 우량주 6종목), `⚠️ 추천 위험주` (하락/변동성 경계 6종목)
   - `📘 주식 입문 가이드` (`#view-guide`), 종목 상세 리포트 (`selectStock`)
2. **🛡️ 보안·운영 관제 팀 (루틴 2)**
   - `🛡️ 보안통제실` (`#admin-modal`)의 `🩺 시스템 자가 점검 & 자동 조치 리포트` (`runAdminSelfHealingCheck`)
   - `📊 활동 자동 요약 보고서` (`refreshAccountActivitySummary` — 빈 기록 대기, `기존 결과`/`갱신됨`, 원본 대조 후 승인 저장)
   - `UserActivityTracker` 감사 로그 (`SEARCH_STOCK`, `TRADE_*`, `CALC_WATER`, `QUICK_CMD`)
3. **💼 개인 계좌 관리 팀 (루틴 3)**
   - `💼 내 계좌 관리` (`renderAccountManagementView`) & `📌 오늘의 내 계좌 데일리 브리핑` (`renderAccountDailyBriefing`)
   - `🚨 계좌 응급실` (`runEmergencyRoomCalculation`), `🏦 KIS 모의투자` (`executeKisPaperOrder`)
   - `💬 빠른 실행` (`executeNaturalLanguageCommand` — 3×4 투자자 흐름 버튼, 중복 실행 방지)

---

## 3. 작업 및 배포 필수 규칙
- **API 키 보안**: `GEMINI_API_KEY`, `DART_API_KEY`, `SUPABASE_KEY` 등 비밀 키는 절대 `index.html`이나 Git 커밋에 넣지 않고 Render `Environment Variables` 또는 로컬 `.env`에만 둔다.
- **상태 변경 보호**: 계좌 예수금·보유 종목 추가, 모의투자 주문, 관심종목 변경, 요약 보고서 저장 등 상태를 바꾸는 동작은 반드시 `requestSaveConfirmation()` (`저장 승인` / `저장 거절` & 중복 승인 방지)을 거친다.
- **UI 상태 유지**: 10초 주기 실시간 시세 갱신 시 사용자가 열어 둔 `Top 6` 상세 분석(`openTop6Codes`) 등 인터랙션 상태를 초기화하지 않는다.
- **배포 구분**:
  - `index.html` / `.md`만 수정 시 → GitHub `main` 푸시만으로 GitHub Pages 자동 반영 (Render 재배포 불필요)
  - `api_server.py` / `stock_service.py` 수정 시 → GitHub 푸시 후 Render 배포(`Live`) 확인
