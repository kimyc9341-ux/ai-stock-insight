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

def _load_kospi_cache():
    """data/stocks.json에 저장된 KOSPI 전체 종목 캐시 로드"""
    try:
        import json
        data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stocks.json")
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("kospi_search") or data.get("kospi_all") or []
    except Exception:
        pass
    return []


def resolve_stock_code(query: str):
    """종목명 또는 코드를 입력받아 정규화된 (종목명, 종목코드) 반환 (KOSPI 전 종목 API 연동)"""
    query = query.strip()
    if not query:
        return query, None

    if query in STOCK_DIRECTORY:
        return query, STOCK_DIRECTORY[query]

    # 코드로 들어왔을 때
    for name, code in STOCK_DIRECTORY.items():
        if code == query:
            return name, code

    # 로컬 KOSPI 전체 종목 캐시(kospi_search) 확인
    kospi_cache = _load_kospi_cache()
    for item in kospi_cache:
        if item.get("name") == query or item.get("code") == query:
            return item.get("name"), item.get("code")

    # 6자리 숫자 코드인 경우 실시간 시세 API로 종목명 확인
    if len(query) == 6 and query.isdigit():
        price_data = get_realtime_price(query)
        if price_data and price_data.get("name"):
            return price_data["name"], query
        return query, query

    # 캐시 부분 일치 검색
    for item in kospi_cache:
        name = item.get("name", "")
        if name and (query in name or name in query):
            return name, item.get("code")

    # 실시간 종목 검색 JSON API 호출 (크롤링 없이 공식 자동완성 API 연동)
    try:
        url = "https://ac.stock.naver.com/ac"
        res = requests.get(url, params={"q": query, "target": "stock"}, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            items = res.json().get("items", [])
            for item in items:
                if item.get("typeCode") in ("KOSPI", "KOSDAQ") or item.get("nationCode") == "KOR":
                    return item.get("name", query), item.get("code")
            if items:
                return items[0].get("name", query), items[0].get("code")
    except Exception:
        pass

    # 기본 사전 부분 일치 검색
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
    """사용자 질문에서 종목명이나 6자리 종목코드를 추출 (KOSPI 전체 종목 지원)"""
    if not text:
        return None, None
    for name, code in STOCK_DIRECTORY.items():
        if name in text:
            return name, code
    for item in _load_kospi_cache():
        name = item.get("name", "")
        if len(name) >= 2 and name in text:
            return name, item.get("code")
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


# =====================================================================
# 1. 한국투자증권 KIS Developers Open API (REST + 모의투자 시세·잔고·주문)
# =====================================================================

_KIS_TOKEN_CACHE = {"access_token": None}


def _get_kis_base_url():
    is_paper = os.getenv("KIS_IS_PAPER", "true").lower() != "false"
    return (
        "https://openapivts.koreainvestment.com:29443"
        if is_paper
        else "https://openapi.koreainvestment.com:9443"
    )


def get_kis_access_token():
    """KIS Developers OAuth2 접근 토큰 발급"""
    if _KIS_TOKEN_CACHE.get("access_token"):
        return _KIS_TOKEN_CACHE["access_token"]
    app_key = os.getenv("KIS_APP_KEY")
    app_secret = os.getenv("KIS_APP_SECRET")
    if not app_key or not app_secret:
        return None
    try:
        url = f"{_get_kis_base_url()}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret,
        }
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            token = res.json().get("access_token")
            _KIS_TOKEN_CACHE["access_token"] = token
            return token
    except Exception as e:
        print(f"[!] KIS 토큰 발급 실패: {e}")
    return None


def get_kis_quote(code: str):
    """KIS 국내주식 실시간 현재가 시세 조회 (FHKST01010100)"""
    token = get_kis_access_token()
    app_key = os.getenv("KIS_APP_KEY")
    app_secret = os.getenv("KIS_APP_SECRET")
    if token and app_key and app_secret:
        try:
            url = f"{_get_kis_base_url()}/uapi/domestic-stock/v1/quotations/inquire-price"
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "appkey": app_key,
                "appsecret": app_secret,
                "tr_id": "FHKST01010100",
            }
            params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
            res = requests.get(url, headers=headers, params=params, timeout=5)
            if res.status_code == 200:
                out = res.json().get("output", {})
                if out:
                    return {
                        "source": "KIS Developers Open API",
                        "code": code,
                        "price": f"{int(out.get('stck_prpr', 0)):,}",
                        "change_val": f"{abs(int(out.get('prdy_vrss', 0))):,}",
                        "change_rate": out.get("prdy_ctrt", "0.00"),
                        "sign": "▲" if out.get("prdy_vrss_sign") in ("1", "2") else ("▼" if out.get("prdy_vrss_sign") in ("4", "5") else "-"),
                        "per": out.get("per", "-"),
                        "pbr": out.get("pbr", "-"),
                        "volume": f"{int(out.get('acml_vol', 0)):,}",
                    }
        except Exception as e:
            print(f"[!] KIS 시세 조회 오류: {e}")

    base_price = get_realtime_price(code)
    if base_price:
        base_price["source"] = "KIS 호환 실시간 시세 (모의투자 연동 모드)"
    return base_price


def get_kis_paper_balance():
    """KIS 모의투자 잔고 조회 (VTTC8434R) 또는 로컬 모의투자 계좌 시뮬레이터"""
    token = get_kis_access_token()
    app_key = os.getenv("KIS_APP_KEY")
    app_secret = os.getenv("KIS_APP_SECRET")
    account_no = os.getenv("KIS_ACCOUNT_NO", "")
    if token and app_key and app_secret and "-" in account_no:
        cano, acnt_prdt_cd = account_no.split("-", 1)
        try:
            url = f"{_get_kis_base_url()}/uapi/domestic-stock/v1/trading/inquire-balance"
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "appkey": app_key,
                "appsecret": app_secret,
                "tr_id": "VTTC8434R",
            }
            params = {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            }
            res = requests.get(url, headers=headers, params=params, timeout=7)
            if res.status_code == 200:
                data = res.json()
                holdings = [
                    {
                        "name": h.get("prdt_name"),
                        "code": h.get("pdno"),
                        "qty": int(h.get("hldg_qty", 0)),
                        "avg_price": int(float(h.get("pchs_avg_pric", 0))),
                        "cur_price": int(h.get("prpr", 0)),
                        "profit_rate": h.get("evlu_pfls_rt", "0.00"),
                    }
                    for h in data.get("output1", [])
                    if int(h.get("hldg_qty", 0)) > 0
                ]
                summary = (data.get("output2") or [{}])[0]
                return {
                    "source": "KIS 모의투자 실계좌 API (VTTC8434R)",
                    "cash": int(summary.get("dnca_tot_amt", 50000000)),
                    "total_eval": int(summary.get("tot_evlu_amt", 50000000)),
                    "holdings": holdings,
                }
        except Exception as e:
            print(f"[!] KIS 모의투자 잔고 조회 실패: {e}")

    return {
        "source": "KIS 모의투자 시뮬레이션 계좌 (무료 테스트 모드)",
        "cash": 50000000,
        "total_eval": 50000000,
        "holdings": [],
    }


def place_kis_paper_order(query: str, qty: int, side: str = "BUY"):
    """KIS 모의투자 현금 매수(VTTC0802U) / 매도(VTTC0801U) 주문 실행"""
    name, code = resolve_stock_code(query)
    if not code:
        return {"ok": False, "message": f"'{query}' 종목코드를 찾을 수 없습니다."}
    price_info = get_realtime_price(code)
    cur_price_str = price_info.get("price", "0") if price_info else "0"
    cur_price = int(cur_price_str.replace(",", "") or 0)

    token = get_kis_access_token()
    app_key = os.getenv("KIS_APP_KEY")
    app_secret = os.getenv("KIS_APP_SECRET")
    account_no = os.getenv("KIS_ACCOUNT_NO", "")
    side_upper = side.upper()

    if token and app_key and app_secret and "-" in account_no:
        cano, acnt_prdt_cd = account_no.split("-", 1)
        tr_id = "VTTC0802U" if side_upper == "BUY" else "VTTC0801U"
        try:
            url = f"{_get_kis_base_url()}/uapi/domestic-stock/v1/trading/order-cash"
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "appkey": app_key,
                "appsecret": app_secret,
                "tr_id": tr_id,
            }
            payload = {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "PDNO": code,
                "ORD_DVSN": "01",  # 시장가 주문
                "ORD_QTY": str(qty),
                "ORD_UNPR": "0",
            }
            res = requests.post(url, headers=headers, json=payload, timeout=7)
            data = res.json()
            if res.status_code == 200 and data.get("rt_cd") == "0":
                odno = data.get("output", {}).get("ODNO", "-")
                return {
                    "ok": True,
                    "source": f"KIS 모의투자 API ({tr_id})",
                    "message": f"[모의투자 {'매수' if side_upper == 'BUY' else '매도'} 체결 완료] {name}({code}) {qty}주 @ {cur_price:,}원 (주문번호: {odno})",
                }
        except Exception as e:
            print(f"[!] KIS 주문 호출 예외: {e}")

    total_amt = cur_price * qty
    return {
        "ok": True,
        "source": "KIS 모의투자 시뮬레이터",
        "message": (
            f"[모의투자 {'매수' if side_upper == 'BUY' else '매도'} 시뮬레이션 완료] "
            f"{name}({code}) {qty}주 × 현재가 {cur_price:,}원 = 총 {total_amt:,}원"
        ),
    }


# =====================================================================
# 2. DART 오픈API (금융감독원 전자공시시스템 - 실시간 공시 감지 및 요약)
# =====================================================================

DART_CATEGORY_RULES = [
    ("실적/정기보고", ["사업보고서", "분기보고서", "반기보고서", "잠정실적", "영업(잠정)실적", "매출액또는손익구조"]),
    ("수주/공급계약", ["단일판매", "공급계약", "수주", "계약체결", "양수결정", "특허"]),
    ("자본/메자닌(주의)", ["유상증자", "전환사채", "신주인수권부사채", "교환사채", "감자", "합병", "분할"]),
    ("지분/배당/주주환원", ["대량보유", "임원ㆍ주요주주", "자기주식", "배당", "현금ㆍ현물배당", "소각"]),
]


def _classify_disclosure(title: str):
    for category, keywords in DART_CATEGORY_RULES:
        for kw in keywords:
            if kw in title:
                impact = "호재/긍정" if category in ("수주/공급계약", "지분/배당/주주환원") else (
                    "단기주의/희석점검" if "자본/메자닌" in category else "핵심실적/중립"
                )
                return category, impact
    return "기타경영공시", "중립/내용확인"


def get_dart_disclosures(query: str, page_count: int = 5):
    """
    DART 오픈API(opendart.fss.or.kr) 및 KRX/네이버 공시 피드를 결합하여
    특정 종목의 최근 중요 공시(실적 발표, 계약 체결, 유상증자/CB, 대주주 지분 변동 등)를 수집·분류합니다.
    """
    name, code = resolve_stock_code(query)
    if not code:
        return []

    dart_key = os.getenv("DART_API_KEY")
    disclosures = []

    # 1) DART_API_KEY가 설정된 경우 공식 DART list.json API 조회
    if dart_key:
        try:
            url = "https://opendart.fss.or.kr/api/list.json"
            params = {
                "crtfc_key": dart_key,
                "page_count": page_count,
            }
            res = requests.get(url, params=params, timeout=6)
            if res.status_code == 200:
                data = res.json()
                for item in data.get("list", []):
                    corp_name = item.get("corp_name", "")
                    stock_code = item.get("stock_code", "")
                    if stock_code == code or name in corp_name or corp_name in name:
                        report_nm = item.get("report_nm", "")
                        cat, impact = _classify_disclosure(report_nm)
                        disclosures.append({
                            "source": "DART 전자공시 API",
                            "stock_name": name,
                            "code": code,
                            "title": report_nm,
                            "category": cat,
                            "impact": impact,
                            "date": item.get("rcept_dt", ""),
                            "rcept_no": item.get("rcept_no", ""),
                            "flr_nm": item.get("flr_nm", corp_name),
                        })
        except Exception as e:
            print(f"[!] DART 오픈API 조회 실패 ({name}): {e}")

    # 2) 실시간 종목 통합/뉴스 피드에서 공시·실적·계약·지분 키워드 감지 보완
    if not disclosures:
        news_items = get_recent_news(code, page_size=5)
        for n in news_items:
            title = n.get("title", "")
            cat, impact = _classify_disclosure(title)
            disclosures.append({
                "source": "DART/KRX 실시간 공시·이슈 감지기",
                "stock_name": name,
                "code": code,
                "title": title,
                "category": cat,
                "impact": impact,
                "date": n.get("datetime", "")[:10],
                "rcept_no": "",
                "flr_nm": n.get("office", "KRX/공시"),
            })

    return disclosures[:page_count]


def summarize_watchlist_disclosures(watchlist: list):
    """
    관심 종목 리스트에 대해 중요 공시(실적 발표, 계약 체결, 유상증자/CB, 대주주 지분 변동 등)를
    에이전트가 자동 감지하여 요약 브리핑을 반환합니다.
    """
    summary_items = []
    for stock_query in watchlist:
        items = get_dart_disclosures(stock_query, page_count=2)
        if items:
            top = items[0]
            summary_items.append(
                f"• [{top['stock_name']}({top['code']})] [{top['category']} | {top['impact']}] {top['title']} ({top['date']})"
            )
        else:
            summary_items.append(f"• [{stock_query}] 최근 특이 공시 없음")
    return "\n".join(summary_items)

