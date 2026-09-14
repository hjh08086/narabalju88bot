import os
import requests
import json
import time
from datetime import datetime, timedelta

# ========== 설정 (사전규격 전용) ==========
SERVICE_KEY = os.environ.get("SERVICE_KEY")
TELEGRAM_TOKEN = os.environ.get("SAJUN_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("SAJUN_CHAT_ID")

KEYWORDS = ["도시", "설계", "타당성", "개발", "조성", "계획"]
CACHE_FILE = "sent_sajun_ids.json"

# 이미 보낸 공고 기록 불러오기 (기억 유지용)
def load_sent_ids():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

# 보낸 공고 기록 저장하기
def save_sent_ids(sent_ids):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(sent_ids), f, ensure_ascii=False)
    except Exception as e:
        print("기록 저장 오류:", e)

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

def fetch_sajun_plans():
    base_url = "https://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService/getPublicPrcureThngInfoServcPPSSrch"
    
    today = datetime.now()
    bgn_dt = (today - timedelta(days=3)).strftime('%Y%m%d0000')
    end_dt = today.strftime('%Y%m%d2359')
    
    params = {
        'serviceKey': SERVICE_KEY,
        'pageNo': '1',
        'numOfRows': '500',
        'type': 'json',
        'inqryBgnDt': bgn_dt,
        'inqryEndDt': end_dt,
        'inqryDiv': '1'
    }
    
    for attempt in range(3):
        try:
            print(f"API 요청 시도 {attempt + 1}/3...")
            res = requests.get(base_url, params=params, timeout=60)
            print(f"HTTP 상태 코드: {res.status_code}")
            
            if res.status_code == 200:
                data = res.json()
                response_root = data.get("response", {})
                body = response_root.get("body", {})
                
                total_count = body.get("totalCount")
                print(f"API 응답 전체 검색 건수(totalCount): {total_count}")
                
                items_data = body.get("items", [])
                
                if isinstance(items_data, dict):
                    items = items_data.get("item", [])
                else:
                    items = items_data
                    
                if not isinstance(items, list):
                    items = [items] if items else []
                    
                return items
            else:
                print(f"API 오류 상태코드: {res.status_code}")
                print(res.text[:200])
        except Exception as e:
            print(f"시도 {attempt + 1} 실패 (타임아웃 또는 통신 오류): {e}")
        
        time.sleep(10)
        
    print("API 서버 응답 없음 (연속 타임아웃 발생)")
    return []

def main_once():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 실시간 사전규격 확인 중...")
    
    sent_ids = load_sent_ids()
    items = fetch_sajun_plans()
    print(f"최종 파싱된 공고 건수: {len(items)}")
    
    # ★ API가 보내주는 실제 데이터 구조(키값들) 확인용 디버그
    if items:
        print("--- [디버그] 첫 번째 공고의 실제 API 필드 키목록 ---")
        print(list(items[0].keys()))
        print("--- [디버그] 첫 번째 공고의 실제 데이터 내용 ---")
        print(items[0])
        print("--------------------------------------------------")
    
    new_count = 0
    
    for item in items:
        title = (
            item.get("bidNtceNm") or 
            item.get("bfSpecRgstNoNm") or 
            item.get("prcurePrnmntNoNm") or 
            item.get("ntceNm") or 
            item.get("cnstwkNm") or 
            item.get("refNoNm") or 
            ""
        )
        
        if not title and item:
            title = str(list(item.values())[0])

        org = item.get("orderInsttNm") or item.get("ntceInsttNm") or item.get("dminsttNm") or "기관정보 없음"
        bid_no = item.get("bfSpecRgstNo") or item.get("bidNtceNo", "")
        bid_ord = item.get("bidNtceOrd", "1")
        
        unique_id = f"{bid_no}_{bid_ord}"
        
        print(f"체크 중: {title}")

        if unique_id in sent_ids:
            continue
        
        # 1. 기술용역 필터
        if "기술" not in title and "용역" not in title:
            if not any(kw in title for kw in ["설계", "타당성", "계획"]):
                continue
        
        # 2. 키워드 필터
        matched = [kw for kw in KEYWORDS if kw in title]
        if not matched:
            print(" → 키워드 불일치로 제외됨")
            continue
            
        print(f" → 조건 일치! 알림 대상: {title}")
        
        # 신규 공고 알림 전송
        msg = f"""🔍 <b>신규 기술용역 사전규격 알림</b>

📌 <b>{title}</b>
🏛 발주기관: {org}
🔍 키워드: {', '.join(matched)}"""
        
        send_telegram(msg)
        sent_ids.add(unique_id)
        new_count += 1
        time.sleep(3)
    
    save_sent_ids(sent_ids)
    
    if new_count == 0:
        print("새로운 사전규격 공고 없음 (정상 대기 중)")
    else:
        print(f"신규 사전규격 알림 {new_count}건 전송 완료")

if __name__ == "__main__":
    main_once()
