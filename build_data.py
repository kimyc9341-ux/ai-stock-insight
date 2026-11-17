"""
build_data.py - 실시간 주가, 주요 지수, KOSPI 30대 종목, 재무제표, 뉴스를 종합 빌드
"""

import os
import json
import datetime
import requests
import stock_service

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
}

LEAD_STOCKS = [
    {"name": "삼성전자", "code": "005930", "tag": "반도체 대장"},
    {"name": "SK하이닉스", "code": "000660", "tag": "AI 메모리/HBM"},
    {"name": "한미반도체", "code": "042700", "tag": "반도체 HBM 장비"},
    {"name": "LS ELECTRIC", "code": "010120", "tag": "데이터센터 전력"},
    {"name": "삼성SDS", "code": "018260", "tag": "AI 클라우드"},
    {"name": "현대차", "code": "005380", "tag": "모빌리티/밸류업"},
    {"name": "우리기술", "code": "032820", "tag": "원전/전력망"},
    {"name": "NAVER", "code": "035420", "tag": "AI 플랫폼"}
]

def fetch_market_indexes():
    """주요 증시 4대 지표 수집 (코스피, 코스닥, 코스피200, 선물)"""
    indexes = [
        {"key": "KOSPI", "name": "코스피"},
        {"key": "KOSDAQ", "name": "코스닥"},
        {"key": "KPI200", "name": "코스피 200"},
        {"key": "FUT", "name": "코스피 200 선물"}
    ]
    results = []
    for idx in indexes:
        try:
            url = f"https://m.stock.naver.com/api/index/{idx['key']}/basic"
            res = requests.get(url, headers=HEADERS, timeout=5).json()
            direction = res.get("compareToPreviousPrice", {}).get("name", "")
            sign = "▲" if direction == "RISING" else ("▼" if direction == "FALLING" else "-")
            results.append({
                "name": idx["name"],
                "price": res.get("closePrice", "0"),
                "change": res.get("compareToPreviousClosePrice", "0"),
                "rate": res.get("fluctuationsRatio", "0.00"),
                "sign": sign
            })
        except Exception as e:
            print(f"[!] 지수 수집 실패 ({idx['name']}): {e}")
            results.append({
                "name": idx["name"], "price": "-", "change": "0", "rate": "0.00", "sign": "-"
            })
    return results

def fetch_kospi_all_30():
    """KOSPI 시가총액 상위 30대 전 종목 리스트 수집"""
    url = "https://m.stock.naver.com/api/stocks/marketValue/KOSPI?page=1&pageSize=30"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5).json()
        stocks = []
        for s in res.get("stocks", []):
            direction = s.get("compareToPreviousPrice", {}).get("name", "")
            sign = "▲" if direction == "RISING" else ("▼" if direction == "FALLING" else "-")
            stocks.append({
                "rank": s.get("ranking", 0),
                "name": s.get("stockName", ""),
                "code": s.get("itemCode", ""),
                "price": s.get("closePrice", "0"),
                "change": s.get("compareToPreviousClosePrice", "0"),
                "rate": s.get("fluctuationsRatio", "0.00"),
                "sign": sign,
                "marketValue": s.get("marketValue", "0")
            })
        return stocks
    except Exception as e:
        print(f"[!] KOSPI 30 수집 실패: {e}")
        return []

def build():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] 🚀 종합 주식 데이터 빌드 시작...")
    
    # 1. 주요 증시 4대 지표
    indexes = fetch_market_indexes()
    
    # 2. KOSPI 30대 전 종목
    kospi_all = fetch_kospi_all_30()
    
    # 3. 주도주 8종목 상세 데이터 (재무, 뉴스, AI 분석)
    lead_stocks_data = {}
    for item in LEAD_STOCKS:
        code = item["code"]
        name = item["name"]
        tag = item["tag"]
        print(f"  • 상세 수집: {name} ({code})...")
        
        price = stock_service.get_realtime_price(code)
        finance = stock_service.get_financial_summary(code)
        news = stock_service.get_recent_news(code, page_size=3)
        analysis = stock_service.analyze_with_gemini(name, price, finance, news)
        
        lead_stocks_data[name] = {
            "name": name,
            "code": code,
            "tag": tag,
            "price": price,
            "finance": finance,
            "news": news,
            "analysis": analysis
        }
        
    out_data = {
        "updated_at": now_str,
        "indexes": indexes,
        "kospi_all": kospi_all,
        "stocks": lead_stocks_data
    }
    
    out_path = os.path.join(DATA_DIR, "stocks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)
        
    print(f"[{now_str}] ✅ 전체 데이터 빌드 완료 -> '{out_path}'")

if __name__ == "__main__":
    build()
