import os
import requests
import json
import time
from datetime import datetime

# ========== 설정 (사전규격 전용) ==========
SERVICE_KEY = os.environ.get("SERVICE_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

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
    # 사전규격 서비스 정식 엔드포인트 적용 (발주계획과 동일한 파라미터 구조)
    url = "https://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService/getPublicPrcureThngInfoServc"
    
    params = {
        "serviceKey": SERVICE_KEY,
        "pageNo": "1",
        "numOfRows": "300",
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
        items_data = body.get("items", [])
        
        # 사전규격 API 고유의 items > item 구조 대응 (리스트가 아닐 경우 처리)
        if isinstance(items_data, dict):
            items = items_data.get("item", [])
        else:
            items = items_data
            
        if not isinstance(items, list):
            items = [items] if items else []
            
        return items
    except Exception as e:
        print("API 호출 오류:", e)
        return []

def main_once():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 실시간 사전규격 확인 중...")
    
    sent_ids = load_sent_ids()
    items = fetch_sajun_plans()
    print(f"조회된 전체 건수: {len(items)}")
    
    new_count = 0
    
    for item in items:
        # 사전규격 API 응답 필드명 확인 (확장 매핑)
        title = item.get("bidNtceNm") or item.get("bfSpecRgstNoNm") or item.get("prcurePrnmntNoNm") or ""
        org = item.get("orderInsttNm") or item.get("ntceInsttNm") or item.get("dminsttNm") or "기관정보 없음"
        bid_no = item.get("bfSpecRgstNo") or item.get("bidNtceNo", "")
        bid_ord = item.get("bidNtceOrd", "1")
        
        # 디버깅용: 가져온 공고 제목과 번호 확인 (로그로 출력됨)
        # print(f"수집된 공고: [{bid_no}] {title}")
        
        unique_id = f"{bid_no}_{bid_ord}"
        
        if not bid_no or unique_id in sent_ids:
            continue
        
        # 1. 기술용역 필터 조건 완화 (디버깅 검증용)
        # "용역"이나 "설계", "타당성", "계획", "개발", "조성", "도시" 중 하나라도 들어가면 통과하도록 설정
        if not any(kw in title for kw in ["용역", "설계", "타당성", "계획", "개발", "조성", "도시"]):
            continue
        
        # 2. 키워드 매칭 확인
        matched = [kw for kw in KEYWORDS if kw in title]
        if not matched:
            # 키워드가 정확히 안 맞더라도 일단 테스트를 위해 제목에 용역/설계가 있으면 잡히게 하려면 이 조건을 주석 처리하면 됨
            pass
        
        # 신규 공고 알림 전송
        msg = f"""🔍 <b>신규 기술용역 사전규격 알림</b>

📌 <b>{title}</b>
🏛 발주기관: {org}
🔍 키워드: {', '.join(matched) if matched else '기본 조건 통과'}"""
        
        send_telegram(msg)
        sent_ids.add(unique_id)
        new_count += 1
        print("→ 신규 알림 전송:", title)
        time.sleep(3)
    
    save_sent_ids(sent_ids)
    
    if new_count == 0:
        print("새로운 사전규격 공고 없음 (정상 대기 중)")
    else:
        print(f"신규 사전규격 알림 {new_count}건 전송 완료")

if __name__ == "__main__":
    main_once()
