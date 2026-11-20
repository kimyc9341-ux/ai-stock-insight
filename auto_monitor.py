"""
auto_monitor.py - WSL2 백그라운드 자동화 주식 모니터링 및 AI 리포트 생성기
- 설정된 주기(기본 30초, 혹은 매 정각)마다 8개 주도주 시세 및 뉴스 자동 수집
- 일별 자동 리포트 파일(logs/daily_report_YYYY-MM-DD.md)에 누적 기록
- 터미널이나 백그라운드에서 상시 가동 가능
"""

import os
import time
import datetime
import schedule
import stock_service

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(WORKSPACE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

WATCH_LIST = [
    {"name": "삼성전자", "code": "005930", "tag": "반도체 대장"},
    {"name": "SK하이닉스", "code": "000660", "tag": "AI 메모리/HBM"},
    {"name": "한미반도체", "code": "042700", "tag": "반도체 HBM 장비"},
    {"name": "LS ELECTRIC", "code": "010120", "tag": "데이터센터 전력"},
    {"name": "삼성SDS", "code": "018260", "tag": "AI 클라우드"},
    {"name": "현대차", "code": "005380", "tag": "모빌리티/밸류업"},
    {"name": "우리기술", "code": "032820", "tag": "원전/전력망"},
    {"name": "NAVER", "code": "035420", "tag": "AI 플랫폼"}
]

def run_automated_check():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_file = os.path.join(LOG_DIR, f"report_{datetime.datetime.now().strftime('%Y%m%d')}.md")
    
    print(f"\n[{now_str}] 🤖 WSL 자동화 에이전트: 실시간 시세 및 AI 지표 분석 시작...")
    
    entries = []
    entries.append(f"\n## 🕒 분석 일시: {now_str}\n")
    entries.append("| 종목명 | 코드 | 현재가 | 전일대비 | 등락률 | 상태 |")
    entries.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for item in WATCH_LIST:
        price = stock_service.get_realtime_price(item["code"])
        if price:
            p_val = price['price']
            c_val = price['change_val']
            rate = price['change_rate']
            sign = price['sign']
            entries.append(f"| {item['name']} | {item['code']} | {p_val}원 | {sign} {c_val}원 | {rate}% | {price['market_status']} |")
            print(f"  • {item['name']}: {p_val}원 ({sign} {rate}%)")
        else:
            entries.append(f"| {item['name']} | {item['code']} | 지연 | - | - | - |")
            
    # 로그 파일에 자동 기록
    with open(today_file, "a", encoding="utf-8") as f:
        f.write("\n".join(entries) + "\n\n")
        
    print(f"[{now_str}] ✅ 자동 분석 완료 -> '{os.path.basename(today_file)}' 파일에 자동 저장됨.")

def main():
    print("=" * 60)
    print(" 🚀 [WSL2 AI 주식 자동화 모니터링 시스템]")
    print("=" * 60)
    print("• 모니터링 대상: KOSPI/KOSDAQ 8대 핵심 주도주")
    print("• 자동화 주기: 1분마다 자동 수집 및 Markdown 리포트 기록")
    print("• 결과 저장 위치: agent/logs/")
    print("• 종료하려면 언제든 [Ctrl + C]를 누르세요.")
    print("=" * 60)
    
    # 1회 즉시 실행
    run_automated_check()
    
    # 1분마다 자동 실행 등록
    schedule.every(1).minutes.do(run_automated_check)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] 자동화 시스템을 안전하게 종료했습니다. 👋\n")
