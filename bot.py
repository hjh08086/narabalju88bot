import os
import requests
import json
import time
from datetime import datetime

# ========== 여기 세 곳만 수정 ==========
SERVICE_KEY = os.environ.get("SERVICE_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
# =====================================

KEYWORDS = ["도시", "설계", "타당성", "계획"]
CHECK_INTERVAL = 300  # 5분 (초 단위)

# 이미 보낸 공고 저장 (중복 방지)
sent_ids = set()

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        res = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        print("텔레그램 전송:", res.status_code)
    except Exception as e:
        print("텔레그램 오류:", e)

def fetch_order_plans():
    url = "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService/getOrderPlanSttusListServcPPSSrch"
    
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": "1",
        "numOfRows": "50",
        "inqryDiv": "1",
        "type": "json"
    }
    
    try:
        res = requests.get(url, params=params, timeout=30)
        if res.status_code != 200:
            print("API 오류 상태코드:", res.status_code)
            return []
        
        data = res.json()
        body = data.get("response", {}).get("body", {})
        items = body.get("items", [])
        
        if not isinstance(items, list):
            items = [items] if items else []
            
        return items
    except Exception as e:
        print("API 호출 오류:", e)
        return []

def main_once():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 발주계획 확인 중...")
    
    items = fetch_order_plans()
    print(f"조회된 건수: {len(items)}")
    
    new_count = 0
    
    for item in items:
        title = item.get("bizNm") or ""
        org = item.get("orderInsttNm") or "기관정보 없음"
        div_name = item.get("bsnsDivNm") or ""  # 용역 구분 (일반용역, 기술용역 등)
        amount = item.get("sumOrderAmt") or ""
        year = item.get("orderYear") or ""
        month = item.get("orderMnth") or ""
        
        # 고유 ID 만들기 (중복 방지용)
        unique_id = f"{org}_{title}_{year}{month}"
        
        if not title or unique_id in sent_ids:
            continue
        
        # 1. 기술용역만 필터
        if "기술" not in div_name and "기술용역" not in title:
            # 제목에 설계/타당성 등이 있으면 기술용역으로 간주
            if not any(kw in title for kw in ["설계", "타당성", "계획"]):
                continue
        
        # 2. 키워드 필터
        matched = [kw for kw in KEYWORDS if kw in title]
        if not matched:
            continue
        
        # 알림 전송
        msg = f"""📋 <b>기술용역 발주계획 알림</b>

📌 <b>{title}</b>
🏛 발주기관: {org}
🏷 구분: {div_name}
📅 발주시점: {year}년 {month}월
💰 금액: {amount}원
🔍 키워드: {', '.join(matched)}"""
        
        send_telegram(msg)
        sent_ids.add(unique_id)
        new_count += 1
        print("→ 알림 전송:", title)
        time.sleep(1)
    
    if new_count == 0:
        print("새로운 기술용역 공고 없음")
    else:
        print(f"신규 알림 {new_count}건 전송 완료")

# ===== 5분마다 반복 실행 =====
print("🚀 나라장터 기술용역 발주계획 모니터링 시작")
print("5분마다 자동 확인합니다. (멈추려면 앱을 종료하세요)")

send_telegram("🚀 나라장터 기술용역 발주계획 모니터링이 시작되었습니다.")

while True:
    try:
        main_once()
    except Exception as e:
        print("실행 중 오류:", e)
    
    print(f"{CHECK_INTERVAL}초 후 다시 확인합니다...\n")
    time.sleep(CHECK_INTERVAL)
