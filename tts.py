import time
import requests
from config import ZALO_API_KEY

def get_zalo_voice(text, audio_path):
    """
    Gọi API Zalo AI kèm bộ lọc Polling kéo dài 40 giây chống sập CDN 404
    """
    url = "https://api.zalo.ai/v1/tts/synthesize"
    headers = {
        "apikey": ZALO_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    payload = {
        "input": text,
        "speaker_id": "4",      # 4: Nam Bắc xịn
        "speed": "1.0",
        "encode_type": "1"      # MP3
    }
    
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code != 200:
        raise Exception(f"Lỗi kết nối Zalo API: HTTP {response.status_code} - {response.text}")
        
    res_json = response.json()
    error_code = res_json.get("error_code")
    
    if error_code == 0:
        audio_url = res_json["data"]["url"]
        
        # GIA HẠN THỜI GIAN: Thử lại 20 lần, mỗi lần nghỉ 2 giây (Chờ tối đa 40 giây)
        max_retries = 20
        for attempt in range(max_retries):
            print(f"   [->] Check file trên CDN Zalo (Lần {attempt + 1}/{max_retries})...")
            audio_data = requests.get(audio_url, stream=True)
            
            if audio_data.status_code == 200:
                with open(audio_path, "wb") as f:
                    for chunk in audio_data.iter_content(chunk_size=1024*1024):
                        if chunk: f.write(chunk)
                print("   [✔] Zalo đã render xong! Tải audio thành công.")
                return True
                
            elif audio_data.status_code == 404:
                # Chờ 2 giây cho hệ thống Zalo xử lý render
                time.sleep(2)
            else:
                raise Exception(f"Lỗi CDN Zalo không xác định: HTTP {audio_data.status_code}")
                
        raise Exception(f"Zalo render quá chậm (Vượt quá 40 giây chờ đợi).")
            
    elif error_code == 155:
        raise Exception("Zalo API Lỗi: Nội dung kịch bản vượt quá giới hạn 2000 ký tự.")
    elif error_code == 401:
        raise Exception("Zalo API Lỗi: Sai apikey. Check lại file config.py")
    else:
        raise Exception(f"Zalo API Lỗi (code {error_code}): {res_json.get('error_message')}")