# 📊 사용자 추천·리서치 팀 매뉴얼 (`TEAM_USER_RESEARCH`)

## 1. 담당 영역
- **홈 `🏆 오늘의 AI 자동 선정 Top 6 리서치 리포트`**: `renderDailyTop2Report()` (`index.html`)
- **메뉴 `🏛️ 안정 대장주` (시총 Top 50 우량주 6종목)**: `renderLeadStocks6()` (`index.html`)
- **메뉴 `⚠️ 추천 위험주` (하락·변동성 주의 6종목)**: `getRiskStocksMap()` / `renderRiskStocks6()` (`index.html`)
- **메뉴 `📘 주식 입문 가이드`**: `#view-guide` (계좌 개설 · 필수 용어 · 모의투자 연습 연결)
- **종목 상세 리포트 & Gemini AI 분석**: `selectStock()`, `runServerGeminiAnalysis()`, `stock_service.py`

## 2. 실행 루틴 및 규칙
1. **전 종목 스캔**: `getScoredMarketPool()`로 `data/stocks.json`(4,332개 종목)의 거래대금·등락률·시총 순위를 실시간 점수화한다.
2. **UI 상태 유지**: 10초마다 실시간 시세가 갱신되어도 사용자가 펼쳐 둔 `Top 6` 상세 3단 분석(`openTop6Codes`)은 닫히지 않도록 유지한다.
3. **폴백 규칙**: Google Gemini API(`gemini-3.8-flash`)가 `503` 혼잡이거나 10초를 넘기면 즉시 `실시간 Smart 분석 엔진` 리포트를 반환한다.
