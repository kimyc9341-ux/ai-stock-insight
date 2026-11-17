"""
build_data.py - 실시간 주가, 재무제표, 뉴스를 수집하여 data/stocks.json 파일 생성
GitHub Actions 자동화 봇이 매시간/매일 실행하여 최신 시장 데이터로 사이트를 자동 업데이트합니다.
"""

import os
import json
import datetime
import stock_service

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

TARGET_STOCKS = [
    {"name": "삼성전자", "code": "005930", "tag": "반도체 대장"},
    {"name": "SK하이닉스", "code": "000660", "tag": "AI 메모리/HBM"},
    {"name": "한미반도체", "code": "042700", "tag": "반도체 HBM 장비"},
    {"name": "LS ELECTRIC", "code": "010120", "tag": "데이터센터 전력"},
    {"name": "삼성SDS", "code": "018260", "tag": "AI 클라우드"},
    {"name": "현대차", "code": "005380", "tag": "모빌리티/밸류업"},
    {"name": "우리기술", "code": "032820", "tag": "원전/전력망"},
    {"name": "NAVER", "code": "035420", "tag": "AI 플랫폼"}
]

def build():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] 실시간 데이터 빌드 시작...")
    
    result = {
        "updated_at": now_str,
        "stocks": {}
    }
    
    for item in TARGET_STOCKS:
        code = item["code"]
        name = item["name"]
        tag = item["tag"]
        print(f"  수집 중: {name} ({code})...")
        
        price = stock_service.get_realtime_price(code)
        finance = stock_service.get_financial_summary(code)
        news = stock_service.get_recent_news(code, page_size=3)
        analysis = stock_service.analyze_with_gemini(name, price, finance, news)
        
        result["stocks"][name] = {
            "name": name,
            "code": code,
            "tag": tag,
            "price": price,
            "finance": finance,
            "news": news,
            "analysis": analysis
        }
        
    out_path = os.path.join(DATA_DIR, "stocks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        
    print(f"[{now_str}] 빌드 완료 -> '{out_path}' 저장됨.")

if __name__ == "__main__":
    build()
