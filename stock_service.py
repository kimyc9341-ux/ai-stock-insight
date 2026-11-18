"""
stock_service.py - 실시간 주가, 재무제표, 뉴스 수집 및 Gemini AI 분석 모듈
"""

import os
import requests
from dotenv import load_dotenv

# .env 로드
load_dotenv()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 기본 관심 종목 데이터베이스 (종목명 -> 종목코드)
STOCK_DIRECTORY = {
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "한미반도체": "042700",
    "LS ELECTRIC": "010120",
    "LS일렉트릭": "010120",
    "삼성SDS": "018260",
    "현대차": "005380",
    "현대자동차": "005380",
    "우리기술": "032820",
    "NAVER": "035420",
    "네이버": "035420",
    "카카오": "035720",
    "LG에너지솔루션": "373220",
    "기아": "000270",
    "셀트리온": "068270",
    "POSCO홀딩스": "005490",
    "포스코홀딩스": "005490",
    "에코프로비엠": "247540",
    "알테오젠": "196170",
    "두산에너빌리티": "034020",
    "한화에어로스페이스": "012450"
}

def resolve_stock_code(query: str):
    """종목명 또는 코드를 입력받아 정규화된 (종목명, 종목코드) 반환"""
    query = query.strip()
    if query in STOCK_DIRECTORY:
        return query, STOCK_DIRECTORY[query]
    
    # 코드로 들어왔을 때
    for name, code in STOCK_DIRECTORY.items():
        if code == query:
            return name, code
            
    # 6자리 숫자 코드인 경우
    if len(query) == 6 and query.isdigit():
        return query, query
        
    # 부분 일치 검색
    for name, code in STOCK_DIRECTORY.items():
        if query in name or name in query:
            return name, code
            
    return query, None

def get_realtime_price(code: str):
    """네이버 금융 공식 모바일 API를 통한 실시간 주가 조회"""
    url = f"https://m.stock.naver.com/api/stock/{code}/basic"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            direction = data.get("compareToPreviousPrice", {}).get("name", "")
            sign = "▲" if direction == "RISING" else ("▼" if direction == "FALLING" else "-")
            return {
                "name": data.get("stockName", code),
                "code": code,
                "market": data.get("stockExchangeName", "KRX"),
                "price": data.get("closePrice", "0"),
                "change_val": data.get("compareToPreviousClosePrice", "0"),
                "change_rate": data.get("fluctuationsRatio", "0.00"),
                "sign": sign,
                "market_status": data.get("marketStatus", ""),
                "traded_at": data.get("localTradedAt", "")
            }
    except Exception as e:
        print(f"[!] 실시간 시세 조회 실패 ({code}): {e}")
    return None

def get_financial_summary(code: str):
    """연간 재무제표 (매출액, 영업이익, 당기순이익, 영업이익률 등) 조회"""
    url = f"https://m.stock.naver.com/api/stock/{code}/finance/annual"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            summary = data.get("corporationSummary", {})
            finance_info = data.get("financeInfo", {})
            tr_titles = finance_info.get("trTitleList", [])
            row_list = finance_info.get("rowList", [])
            
            # 결산 연도 키 목록 (예: '202412', '202512')
            year_keys = [t.get("key") for t in tr_titles[-2:] if isinstance(t, dict)]
            year_labels = [t.get("title") for t in tr_titles[-2:] if isinstance(t, dict)]

            rows = {}
            for r in row_list:
                title = r.get("title", "")
                if title in ["매출액", "영업이익", "당기순이익", "영업이익률", "ROE", "PER", "PBR"]:
                    cols = r.get("columns", {})
                    recent_vals = []
                    for k in year_keys:
                        val = cols.get(k, {}).get("value", "-") if isinstance(cols, dict) else "-"
                        recent_vals.append(val)
                    rows[title] = recent_vals
                    
            return {
                "summary": [summary.get("comment1", ""), summary.get("comment2", ""), summary.get("comment3", "")],
                "years": year_labels,
                "metrics": rows
            }
    except Exception as e:
        print(f"[!] 재무제표 조회 실패 ({code}): {e}")
    return None

def get_recent_news(code: str, page_size: int = 4):
    """해당 종목의 최근 시장 뉴스 헤드라인 및 요약 조회"""
    url = f"https://m.stock.naver.com/api/news/stock/{code}?pageSize={page_size}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            items = []
            for item in data:
                for sub in item.get("items", []):
                    items.append({
                        "title": sub.get("titleFull", sub.get("title", "")),
                        "office": sub.get("officeName", ""),
                        "datetime": sub.get("datetime", ""),
                        "body": sub.get("body", "")
                    })
            return items[:page_size]
    except Exception as e:
        print(f"[!] 뉴스 조회 실패 ({code}): {e}")
    return []

def analyze_with_gemini(stock_name: str, price_info: dict, finance_info: dict, news_list: list):
    """Google Gemini API를 통한 실시간 뉴스·재무 종합 예측 분석"""
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        # API 키가 등록되지 않았을 때의 스마트 폴백 분석 엔진
        reasons = []
        if price_info:
            rate = float(price_info['change_rate'].replace('+', '').replace('-', ''))
            sign = "상승" if price_info['sign'] == "▲" else "조정"
            reasons.append(f"현재 주가는 {price_info['price']}원({price_info['sign']} {price_info['change_rate']}%)으로 시장에서 {sign} 모멘텀을 형성 중입니다.")
        if finance_info and finance_info.get("summary"):
            reasons.append(" ".join([c for c in finance_info['summary'] if c]))
        if news_list:
            reasons.append(f"최근 주요 뉴스 이슈: '{news_list[0]['title']}'")
        
        return {
            "source": "Smart Rules Engine (Gemini API 키 미등록)",
            "analysis": "\n\n".join(reasons) if reasons else "데이터 분석 결과 단기 관망 및 실적 추이 확인이 필요합니다."
        }
        
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        # 분석용 프롬프트 패킷 조립
        news_context = "\n".join([f"- [{n['office']}] {n['title']}: {n['body'][:80]}..." for n in news_list])
        finance_context = ""
        if finance_info:
            finance_context = "\n".join([f"- {k}: 최근 수치 {v}" for k, v in finance_info.get("metrics", {}).items()])
            
        prompt = f"""
당신은 대한민국 최고의 AI 퀀트 및 주식 애널리스트 에이전트입니다.
제공된 실시간 시장 데이터와 뉴스, 재무 정보를 종합하여 투자자를 위한 핵심 3단계 분석 리포트를 작성해 주세요.

[종목 정보]
- 종목명: {stock_name} (코드: {price_info.get('code', '')})
- 현재가: {price_info.get('price', '')}원 ({price_info.get('sign', '')} {price_info.get('change_rate', '')}%)

[최신 재무 핵심 지표]
{finance_context}

[최근 시장 뉴스 헤드라인]
{news_context}

[작성 양식]
1. 🎯 주가 및 수급 모멘텀 평가 (현재 추세 진단)
2. 📊 재무 건전성 및 실적 포인트 (수익성 및 밸류에이션)
3. 📰 핵심 뉴스 이슈 및 AI 향후 전망 (상승/하락 변수 및 투자 포인트)
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return {
            "source": "Google Gemini 2.5 Flash API",
            "analysis": response.text.strip()
        }
    except Exception as e:
        return {
            "source": "Fallback Engine",
            "analysis": f"Gemini API 호출 중 오류 발생 ({e}). 실시간 데이터 기반 기본 리포트를 참조하세요."
        }


def _extract_stock_from_text(text: str):
    """사용자 질문에서 종목명이나 6자리 종목코드를 추출"""
    if not text:
        return None, None
    for name, code in STOCK_DIRECTORY.items():
        if name in text:
            return name, code
    import re
    match = re.search(r"\b(\d{6})\b", text)
    if match:
        code = match.group(1)
        name, resolved_code = resolve_stock_code(code)
        return name, resolved_code
    return None, None


def chat_with_agent(user_message: str, history: list = None):
    """
    멀티턴 대화를 지원하는 AI 주식 상담 챗봇 함수.
    - .env의 GEMINI_API_KEY(또는 API_KEY)와 MODEL_NAME(기본값: gemini-2.5-flash)을 런타임에 참조
    - 질문 내 종목 감지 시 실시간 시세·재무·뉴스 컨텍스트 자동 결합
    - API 키 미설정 시 실시간 데이터 기반 스마트 폴백 응답 반환
    """
    if history is None:
        history = []

    stock_name, stock_code = _extract_stock_from_text(user_message)
    if not stock_code and history:
        for past in reversed(history):
            s_name, s_code = _extract_stock_from_text(past.get("content", ""))
            if s_code:
                stock_name, stock_code = s_name, s_code
                break

    price_info = get_realtime_price(stock_code) if stock_code else None
    finance_info = get_financial_summary(stock_code) if stock_code else None
    news_list = get_recent_news(stock_code, page_size=3) if stock_code else []

    context_blocks = []
    if stock_code:
        if price_info:
            context_blocks.append(
                f"[실시간 시세] {stock_name}({stock_code}): 현재가 {price_info.get('price')}원 "
                f"({price_info.get('sign')} {price_info.get('change_val')}원 / {price_info.get('change_rate')}%), "
                f"시장 {price_info.get('market')}, 체결시간 {price_info.get('traded_at')}"
            )
        if finance_info and finance_info.get("metrics"):
            years = ", ".join(finance_info.get("years", []))
            metrics_str = "; ".join([f"{k}: {v}" for k, v in finance_info["metrics"].items()])
            context_blocks.append(f"[재무 요약 ({years})] {metrics_str}")
        if news_list:
            news_str = " / ".join([f"[{n['office']}] {n['title']}" for n in news_list])
            context_blocks.append(f"[최근 뉴스] {news_str}")

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")
    model_name = os.getenv("MODEL_NAME", "gemini-2.5-flash")

    if not api_key:
        if stock_code and (price_info or finance_info or news_list):
            reply_lines = [f"💬 [{stock_name} ({stock_code})] 실시간 데이터 기반 답변입니다:"]
            if price_info:
                reply_lines.append(
                    f"• 현재 주가: {price_info['price']}원 ({price_info['sign']} {price_info['change_val']}원, {price_info['change_rate']}%)"
                )
            if finance_info and finance_info.get("metrics"):
                per = finance_info["metrics"].get("PER", ["-"])[-1]
                roe = finance_info["metrics"].get("ROE", ["-"])[-1]
                op_margin = finance_info["metrics"].get("영업이익률", ["-"])[-1]
                reply_lines.append(f"• 주요 재무지표(최근 결산): 영업이익률 {op_margin}%, ROE {roe}%, PER {per}배")
            if news_list:
                reply_lines.append(f"• 최신 뉴스: [{news_list[0]['office']}] {news_list[0]['title']}")
            reply_lines.append("※ .env에 API 키(GEMINI_API_KEY)와 모델 이름(MODEL_NAME)을 설정하시면 심층 자유 대화 추론이 활성화됩니다.")
            return {
                "source": "Smart Rules Chatbot (API 키 미설정)",
                "reply": "\n".join(reply_lines),
                "stock": {"name": stock_name, "code": stock_code}
            }
        return {
            "source": "Smart Rules Chatbot (API 키 미설정)",
            "reply": (
                "궁금하신 종목명(예: 삼성전자, SK하이닉스, 현대차 등)이나 6자리 종목코드를 포함해 질문해 주시면 "
                "실시간 시세·재무제표·뉴스를 즉시 조회해 답변해 드립니다.\n"
                "※ 자유로운 AI 심층 대화를 원하시면 API 키를 설정해 주세요."
            ),
            "stock": None
        }

    history_text = "\n".join(
        [f"{'사용자' if m.get('role') == 'user' else 'AI'}: {m.get('content', '')}" for m in history[-6:]]
    )
    market_context = "\n".join(context_blocks) if context_blocks else "특정 종목 지정 없음 (일반 주식/시장 상담)"

    prompt = f"""당신은 친절하고 전문적인 대한민국 AI 주식 투자 상담 챗봇입니다.
아래 제공된 실시간 시장 데이터와 이전 대화 내역을 참고하여 사용자의 질문에 명확하고 핵심적으로 답변해 주세요.

[실시간 종목 컨텍스트]
{market_context}

[최근 대화 내역]
{history_text}

[사용자 질문]
{user_message}
"""

    try:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return {
                "source": f"Google Gemini ({model_name})",
                "reply": response.text.strip(),
                "stock": {"name": stock_name, "code": stock_code} if stock_code else None
            }
        except ImportError:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, timeout=15)
            res.raise_for_status()
            data = res.json()
            reply_text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            return {
                "source": f"Google Gemini REST ({model_name})",
                "reply": reply_text or "응답을 생성하지 못했습니다.",
                "stock": {"name": stock_name, "code": stock_code} if stock_code else None
            }
    except Exception as e:
        return {
            "source": "Fallback Chatbot Engine",
            "reply": f"API 호출 중 오류가 발생했습니다 ({e}). 키 또는 모델 이름 설정을 확인해 주세요.",
            "stock": {"name": stock_name, "code": stock_code} if stock_code else None
        }
