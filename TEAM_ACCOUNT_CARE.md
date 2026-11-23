# 💼 개인 계좌 관리 팀 매뉴얼 (`TEAM_ACCOUNT_CARE`)

## 1. 담당 영역
- **메뉴 `💼 내 계좌 관리` (로그인 회원 전용)**: `renderAccountManagementView()`, `updateAccountCashDirect()`, `addAccountHoldingDirect()` (`index.html`)
- **오늘의 내 계좌 데일리 브리핑**: `renderAccountDailyBriefing()` (`#account-daily-briefing-box`)
- **메뉴 `🚨 계좌 응급실`**: `runEmergencyRoomCalculation()`, `openErWithHolding()` (`index.html`)
- **메뉴 `🏦 KIS 모의투자 & DART 공시`**: `renderKisDartView()`, `executeKisPaperOrder()`, `syncKisToAccountManagement()`
- **우측 하단 `💬 빠른 실행` (3×4 투자자 흐름)**: `executeNaturalLanguageCommand()`, `NL_ACTION_REGISTRY`

## 2. 실행 루틴 및 규칙
1. **데일리 브리핑**: 로그인 회원이 `내 계좌 관리`를 열면 보유 종목의 최대 비중·DART 공시·`-5%` 이하 손실 종목의 예상 물타기 평단가를 자동 계산해 보여준다.
2. **저장 승인/거절 보호**: 예수금 변경, 보유 종목 추가, 모의투자 매수/매도, 관심종목 변경 전 `requestSaveConfirmation()`으로 값 2개를 보여주고 `저장 승인` 시에만 저장한다.
3. **중복 방지**: 동일 후보 재승인 및 3초 이내 연속 중복 클릭을 차단하며, `빠른 실행`에서도 이미 같은 화면·차트·관심종목 상태면 중복 실행하지 않는다.
