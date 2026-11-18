"""
main.py - AI 주식 예측 프로그램 (종합 분석 에이전트)
- 1: 오늘의 상승 예측 8종목 실시간 시세 및 AI 브리핑
- 2: 종목 검색 및 상세 리포트 (실시간 주가 + 재무제표 + 뉴스 + Gemini 분석)
- 3: Gemini API 키 설정 가이드 및 확인
- 4: AI 주식 상담 챗봇 (실시간 데이터 연동 멀티턴 대화)
- 0: 프로그램 종료
"""

import sys
import stock_service

TOP_PREDICTIONS = [
    {"name": "삼성전자", "code": "005930", "tag": "반도체 대장"},
    {"name": "SK하이닉스", "code": "000660", "tag": "AI 메모리/HBM"},
    {"name": "한미반도체", "code": "042700", "tag": "반도체 HBM 장비"},
    {"name": "LS ELECTRIC", "code": "010120", "tag": "데이터센터 전력 인프라"},
    {"name": "삼성SDS", "code": "018260", "tag": "AI 데이터센터/클라우드"},
    {"name": "현대차", "code": "005380", "tag": "모빌리티/밸류업"},
    {"name": "우리기술", "code": "032820", "tag": "원전/전력망"},
    {"name": "NAVER", "code": "035420", "tag": "AI 플랫폼"}
]

def show_top_predictions():
    print("\n" + "=" * 70)
    print(" 📡 [실시간 시세 연동] 오늘의 상승 유망 8종목 라이브 모니터링")
    print("=" * 70)
    print("실시간 시장 데이터를 수집하는 중입니다...")
    
    for idx, item in enumerate(TOP_PREDICTIONS, 1):
        price_data = stock_service.get_realtime_price(item["code"])
        if price_data:
            sign = price_data['sign']
            price = price_data['price']
            rate = price_data['change_rate']
            change_val = price_data['change_val']
            print(f"\n{idx}. {item['name']} ({item['code']}) [{item['tag']}]")
            print(f"   현재가: {price}원  |  등락: {sign} {change_val}원 ({rate}%)")
        else:
            print(f"\n{idx}. {item['name']} ({item['code']}) [{item['tag']}] - 시세 수신 지연")
            
    print("\n" + "=" * 70)
    print("💡 팁: 특정 종목의 재무제표와 AI 상세 분석을 보려면 메뉴 [2]번을 이용하세요.")

def search_and_analyze():
    print("\n" + "-" * 60)
    query = input("🔍 분석할 종목명 또는 종목코드 6자리를 입력하세요 (예: 삼성전자, SK하이닉스, 005930): ").strip()
    if not query:
        print("[!] 입력이 취소되었습니다.")
        return
        
    name, code = stock_service.resolve_stock_code(query)
    if not code:
        print(f"[!] '{query}' 종목을 찾을 수 없습니다. 종목명이나 6자리 코드를 확인해 주세요.")
        return
        
    print(f"\n데이터 수집 중... [{name} ({code})]")
    
    # 1. 실시간 주가
    price_info = stock_service.get_realtime_price(code)
    # 2. 재무제표 요약
    finance_info = stock_service.get_financial_summary(code)
    # 3. 최신 뉴스
    news_list = stock_service.get_recent_news(code, page_size=3)
    # 4. AI 종합 분석
    analysis_res = stock_service.analyze_with_gemini(name, price_info, finance_info, news_list)
    
    # 결과 화면 출력
    print("\n" + "━" * 65)
    print(f" 📑 [{name} ({code})] AI 종합 투자 분석 리포트")
    print("━" * 65)
    
    # 시세 영역
    if price_info:
        print(f"▶ 현재가: {price_info['price']}원 ({price_info['sign']} {price_info['change_val']}원 / {price_info['change_rate']}%)")
        print(f"▶ 시장구분: {price_info['market']}  |  체결시간: {price_info['traded_at']}")
    else:
        print("▶ 실시간 시세를 불러오지 못했습니다.")
        
    # 재무 영역
    print("\n[📊 핵심 재무제표 및 수익성 지표]")
    if finance_info and finance_info.get("metrics"):
        years = finance_info.get("years", [])
        header = f"{'구분':<12} | " + " | ".join([f"{y:>12}" for y in years])
        print(header)
        print("-" * len(header))
        for metric, vals in finance_info["metrics"].items():
            line = f"{metric:<12} | " + " | ".join([f"{v:>12}" for v in vals])
            print(line)
        if finance_info.get("summary"):
            print("\n* 기업 개요 요약:")
            for s in finance_info["summary"]:
                if s:
                    print(f"  • {s}")
    else:
        print("  재무제표 정보를 조회할 수 없습니다.")
        
    # 뉴스 영역
    print("\n[📰 최근 시장 주요 뉴스 헤드라인]")
    if news_list:
        for idx, n in enumerate(news_list, 1):
            print(f"  {idx}. [{n['office']}] {n['title']}")
            if n.get("body"):
                print(f"     ㄴ {n['body'][:65]}...")
    else:
        print("  관련 최신 뉴스가 없습니다.")
        
    # AI 심층 리포트
    print("\n" + "─" * 65)
    print(f"🤖 [AI 분석 리포트 - 엔진: {analysis_res.get('source')}]")
    print("─" * 65)
    print(analysis_res.get("analysis", "분석 결과가 없습니다."))
    print("━" * 65 + "\n")

def guide_api_key():
    print("\n" + "=" * 68)
    print(" 🔑 API 키 연동 안내 (.env 자리 안내)")
    print("=" * 68)
    print("프로젝트 폴더의 '.env' 파일에 아래 자리 형식으로 입력합니다:")
    print("  GEMINI_API_KEY=여기에_발급받은_Gemini_API_키를_입력하세요")
    print("  MODEL_NAME=gemini-3.8-flash")
    print("  KIS_APP_KEY=여기에_한국투자증권_AppKey를_입력하세요")
    print("  KIS_APP_SECRET=여기에_한국투자증권_AppSecret을_입력하세요")
    print("  KIS_ACCOUNT_NO=여기에_모의투자_계좌번호(예:50123456-01)를_입력하세요")
    print("  DART_API_KEY=여기에_금융감독원_DART_오픈API_키를_입력하세요")
    print("=" * 68)


def run_dart_monitor():
    print("\n" + "=" * 68)
    print(" 📢 DART 전자공시 AI 감지 및 관심종목 요약")
    print("=" * 68)
    q = input("조회할 종목명(비워두면 기본 관심종목 전체 요약): ").strip()
    if q:
        items = stock_service.get_dart_disclosures(q, page_count=5)
        if not items:
            print(f"[!] '{q}' 관련 공시를 찾을 수 없습니다.")
            return
        print(f"\n[{q}] 최근 주요 공시 및 이슈 감지 결과:")
        for idx, d in enumerate(items, 1):
            print(f"  {idx}. [{d['category']} | {d['impact']}] {d['title']} ({d['date']})")
    else:
        watchlist = [item["name"] for item in TOP_PREDICTIONS[:6]]
        print("\n[오늘 관심종목 중요 공시 AI 감지 요약]")
        print(stock_service.summarize_watchlist_disclosures(watchlist))
    print("=" * 68)


def run_kis_paper_trading():
    print("\n" + "=" * 68)
    print(" 🏦 한국투자증권(KIS) 모의투자 API 잔고 조회 및 주문 테스트")
    print("=" * 68)
    bal = stock_service.get_kis_paper_balance()
    print(f"▶ 연동 모드: {bal.get('source')}")
    print(f"▶ 주문가능 예수금: {bal.get('cash', 0):,}원  |  총 평가금액: {bal.get('total_eval', 0):,}원")
    print("\n[보유 종목 잔고]")
    for h in bal.get("holdings", []):
        print(
            f"  • {h['name']} ({h['code']}): {h['qty']}주 | 평균단가 {h['avg_price']:,}원 | "
            f"현재가 {h['cur_price']:,}원 ({h['profit_rate']}%)"
        )
    sub = input("\n모의 주문을 테스트하시겠습니까? (종목명 입력 / 엔터 시 메뉴 복귀): ").strip()
    if sub:
        side = input("매수(BUY) 또는 매도(SELL) 입력 [기본: BUY]: ").strip() or "BUY"
        qty_str = input("주문 수량(주) 입력 [기본: 1]: ").strip() or "1"
        qty = int(qty_str) if qty_str.isdigit() else 1
        res = stock_service.place_kis_paper_order(sub, qty=qty, side=side)
        print(f"\n👉 {res.get('message')}")
    print("=" * 68)


def run_chatbot():
    print("\n" + "=" * 65)
    print(" 💬 AI 주식 상담 챗봇 (실시간 시세·재무·뉴스 연동)")
    print("=" * 65)
    print("• 종목명(예: 삼성전자, SK하이닉스, 현대차)이나 종목코드를 포함해 질문해 보세요.")
    print("• 대화 내역 초기화: '초기화' 또는 'reset' 입력")
    print("• 챗봇 종료 및 메인 메뉴 복귀: '종료', 'exit', 또는 'q' 입력")
    print("-" * 65)

    history = []
    while True:
        user_input = input("\n🙋 질문 입력: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("종료", "exit", "q", "quit"):
            print("\n챗봇 상담을 종료하고 메인 메뉴로 돌아갑니다.")
            break
        if user_input.lower() in ("초기화", "reset", "clear"):
            history.clear()
            print("🔄 대화 내역이 초기화되었습니다.")
            continue

        res = stock_service.chat_with_agent(user_input, history=history)
        reply = res.get("reply", "")
        source = res.get("source", "AI Chatbot")

        print(f"\n🤖 [{source}]")
        print(reply)

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})


def main():
    while True:
        print("\n" + "#" * 62)
        print("   📈 AI 주식 종합 예측 및 분석 에이전트 (KIS + DART 연동)")
        print("#" * 62)
        print(" 1. 오늘의 상승 유망 8종목 실시간 시세 모니터링")
        print(" 2. 개별 종목 검색 및 AI 심층 분석 리포트 (시세+재무+뉴스+AI)")
        print(" 3. API 키 설정 및 연동 가이드 (Gemini / KIS / DART)")
        print(" 4. 💬 AI 주식 상담 챗봇 (실시간 데이터 연동 대화)")
        print(" 5. 📢 관심종목 DART 전자공시 AI 감지 및 요약")
        print(" 6. 🏦 한국투자증권(KIS) 모의투자 잔고 조회 및 주문 테스트")
        print(" 0. 프로그램 종료")
        print("#" * 62)
        
        choice = input("원하시는 메뉴 번호를 입력하세요: ").strip()
        
        if choice == "1":
            show_top_predictions()
        elif choice == "2":
            search_and_analyze()
        elif choice == "3":
            guide_api_key()
        elif choice == "4":
            run_chatbot()
        elif choice == "5":
            run_dart_monitor()
        elif choice == "6":
            run_kis_paper_trading()
        elif choice == "0":
            print("\n프로그램을 종료합니다. 성공 투자를 기원합니다! 👋\n")
            break
        else:
            print("\n[!] 올바른 메뉴 번호를 선택해 주세요.")

if __name__ == "__main__":
    main()
