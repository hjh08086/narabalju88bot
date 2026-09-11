import os
import time
import requests
from datetime import datetime 

# ========== 1. 설정 정보 (사전규격 전용 시크릿 연결) ==========
SERVICE_KEY = os.environ.get("SERVICE_KEY")
TELEGRAM_TOKEN = os.environ.get("SAJUN_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("SAJUN_CHAT_ID")

# 중복 알림 방지용 기록 파일 (발주계획과 안 꼬이게 따로 분리!)
CACHE_FILE = "sent_sajun_ids.json"

# 원하는 키워드 설정 (필요에 따라 수정 가능)
KEYWORDS = ["도시", "설계", "타당성", "조성", "개발", "계획"]

def load_sent_ids():
    if os.path.exists(CACHE_FILE):
        import json
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_sent_ids(sent_ids):
    import json
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent_ids), f, ensure_ascii=False)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def main():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{current_time}] 실시간 사전규격 확인 중...")
    
    # 나라장터 사전규격 API 주소 (공공데이터포털)
    url = "https://apis.data.go.kr/1230000/ad/PrdlstPrtcndSpceInfoService/getPrdlstPrtcndSpceList"
    
    params = {
        "serviceKey": SERVICE_KEY,
        "numOfRows": "300",
        "pageNo": "1",
        "type": "json"
    }
    
    res = None
    for attempt in range(3):
        try:
            res = requests.get(url, params=params, timeout=30)
            if res.status_code == 200:
                break
        except Exception as e:
            print(f"API 연결 시도 {attempt+1}실패, 재시도 중...")
            time.sleep(2)
            
    if not res or res.status_code != 200:
        print("API 호출 오류 또는 타임아웃 발생")
        return

    try:
        data = res.json()
        items = data.get("response", {}).get("body", {}).get("items", [])
    except Exception as e:
        print(f"데이터 파싱 에러: {e}")
        return

    print(f"조회된 전체 건수: {len(items)}")
    
    sent_ids = load_sent_ids()
    new_count = 0

    for item in items:
        # 사전규격 API 응답 필드명에 맞춘 데이터 추출
        title = item.get("bidNtceNm") or "제목 없음"
        org = item.get("ntceInsttNm") or "기관정보 없음"
        
        # 고유 ID 생성 (발주계획과 겹치지 않게 고유 식별)
        bid_no = item.get("bidNtceNo", "")
        bid_ord = item.get("bidNtceOrd", "")
        unique_id = f"{bid_no}_{bid_ord}"

        if not bid_no or unique_id in sent_ids:
            continue

        # 키워드 필터링
        matched = [kw for kw in KEYWORDS if kw in title]
        if not matched:
            continue

        # 텔레그램 알림 메시지 포맷
        msg = f"""<b>[신규 사전규격 알림]</b>

📌 <b>{title}</b>
🏛️ 발주기관: {org}
🔍 키워드: {', '.join(matched)}"""

        send_telegram(msg)
        sent_ids.add(unique_id)
        new_count += 1
        print(f"→ 신규 알림 전송: {title}")
        time.sleep(3)  # 429 에러 방지용 딜레이

    save_sent_ids(sent_ids)
    
    if new_count == 0:
        print("새로운 사전규격 공고 없음 (정상 대기 중)")
    else:
        print(f"신규 사전규격 알림 {new_count}건 전송 완료")

if __name__ == "__main__":
    main()
