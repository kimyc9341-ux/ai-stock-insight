# 호출 흐름 핵심 요약 (빠른 실행 · 내 계좌 관리 · 저장 승인)

## 1. 실제 요청 → 기존 기능 → 화면 결과 매핑

### ① 빠른 실행 명령 (`"내 계좌 관리 보여줘"` / `"삼성전자 주봉 차트로 바꿔줘"` / `"조회해줘"`)
- **진입 함수**: `executeNaturalLanguageCommand(rawText)` (`index.html` 5913행)
- **입력값**: `#nl-cmd-input.value` 또는 프리셋 버튼 `data-cmd` 문자열 (예: `"내 계좌 관리 보여줘"`)
- **내부 호출 흐름**:
  1. `NL_ACTION_REGISTRY` 매핑 표에서 키워드 매칭 (`index.html` 5624행~)
  2. 화면 전환 시 `runTabAction(tab, label)` → `switchTab(tab)` (`index.html` 3671행)
  3. 종목 조회/차트 변경 시 `openStockForCommand(stockQuery)` → `#search-input.value` 세팅 후 `#search-btn.click()` → `selectStock(name)` (`index.html` 4168행)
- **화면에 실제 결과가 나오는 위치**:
  - 명령 실행/중복 방지 안내: `#nl-cmd-feedback` (`index.html` 7054행)
  - 종목 리포트 결과: `#report-card` (`index.html` 2509행) 및 `#report-branch-box`
  - 계좌 관리 결과: `#view-account` (`index.html` 2618행)

### ② 상태 변경 저장 (`+ 내 계좌에 추가`, `예수금 적용`, `모의 매수/매도`, `관심종목 추가`)
- **진입 함수**: `addAccountHoldingDirect()` / `updateAccountCashDirect()` / `executeKisPaperOrder()` / `toggleCurrentReportFavorite()`
- **확인 화면 함수**: `requestSaveConfirmation(opts)` (`index.html` 5984행)
  - **입력값**: `{ candidateId, candidateKey, title, label1, value1, label2, value2, onApprove }`
- **화면에 실제 결과가 나오는 위치**:
  - 확인 화면 모달: `#save-confirm-modal` (`index.html` 7062행) — 값 2개 + `저장 승인` / `저장 거절`
  - 승인 시 저장 위치: `saveKisPaperAccount(acc)` (`localStorage` 키 `kis_paper_account_v2_${currentUser}` 및 서버 `/api/user/portfolio`) / `saveUserFavorites()`

---

## 2. 처음 멈출 수 있는 자리 (게이트웨이 1곳)
- **위치**: `requireAuth(featureName)` (`index.html` 3660행)
- **조건**: `AuthManager.isLoggedIn()`이 `false`(비로그인/게스트 상태)일 때
- **동작**: `switchTab('account' | 'er' | 'kis-dart' | 'fav' | 'radar')` 또는 관심종목/모의투자 실행 직전에 `[로그인 필요]` 알림을 띄우고 `openAuthModal()`을 연 뒤 `false`를 반환해 실행을 멈춥니다.
