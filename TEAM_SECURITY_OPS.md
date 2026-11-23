# 🛡️ 보안·운영 관제 팀 매뉴얼 (`TEAM_SECURITY_OPS`)

## 1. 담당 영역
- **시스템 자가 점검 & 자동 조치 리포트**: `runAdminSelfHealingCheck()` (`index.html` `#admin-self-healing-box`)
- **활동 자동 요약 보고서**: `refreshAccountActivitySummary()`, `previewAndSaveActivitySummary()` (`index.html` `#account-activity-summary-box`)
- **감사 로그 추적**: `UserActivityTracker` (`SEARCH_STOCK`, `TRADE_*`, `CALC_WATER`, `QUICK_CMD`)
- **권한·인증 게이트**: `AuthManager`, `requireAuth()`, Render `/api/audit-logs`, `/api/config`

## 2. 실행 루틴 및 규칙
1. **빈 기록 대기**: `AuthManager.getAuditLogs()`(`cpr_auth_logs_v2`)가 `0건`이면 보고서를 만들지 않고 `⏸️ 대기 중`과 대기 이유를 표시한다.
2. **자료 버전 비교**: `v건수-최신ID`를 직전 보고서와 비교해 같으면 `기존 결과`, 새 기록이 있을 때만 `갱신됨`으로 재생성한다.
3. **자가 점검 & 자동 조치**: `🛡️ 보안통제실` 오픈 시 `/health` 웜업 및 지연 측정, `/api/config` 상태, 차단·중복 로그를 자동 점검하고 조치 내역을 보고한다.
4. **원본 대조 & 승인 저장**: 보고서 건수·버전이 현재 원본 기록과 일치할 때만 `저장 승인` / `저장 거절` 미리보기를 열어 최종 1건을 저장한다.
