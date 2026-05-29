import asyncio
import re
import edge_tts

VOICE = "vi-VN-HoaiMyNeural"

REPLACEMENTS = {
    "ChatGPT":      "Chat-GPT",
    "GPT-4":        "GPT bốn",
    "GPT-4o":       "GPT bốn o",
    "GPT4":         "GPT bốn",
    "GPT":          "G P T",
    "OpenAI":       "Open AI",
    "DeepSeek":     "Deep Seek",
    "Gemini":       "Gemini",
    "Claude":       "Claude",
    "LLM":          "L L M",
    "RAG":          "R A G",
    "API":          "A P I",
    "CEO":          "C E O",
    "AI":           "AI", 
    "AGI":          "A G I",
    "GPU":          "G P U",
    "CPU":          "C P U",
    "SaaS":         "Sát", 
    "USD":          "đô la Mỹ",
    "Reddit":       "Reddit",
    "YouTube":      "YouTube",
    "TikTok":       "TikTok",
    "Pexels":       "Pexels",
}

def normalize_text(text: str) -> str:
    for word, replacement in REPLACEMENTS.items():
        text = re.sub(rf'\b{re.escape(word)}\b', replacement, text)
    return text

async def _synthesize(text: str, audio_path: str):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(audio_path)

def get_zalo_voice(text, audio_path):
    cleaned = normalize_text(text)
    asyncio.run(_synthesize(cleaned, audio_path))
    return True

"""
### ZALO TTS — bỏ triple-quote này khi quota hồi phục ###

import time
import requests
from config import ZALO_API_KEY

def get_zalo_voice(text, audio_path):
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

    # ── BỘ LỌC 1: CHỐNG LỖI 429 RATE LIMIT ──
    response = None
    max_429_retries = 5
    for r_429 in range(max_429_retries):
        response = requests.post(url, headers=headers, data=payload)

        if response.status_code == 429:
            print(f"   [!] Zalo chặn 429 (Rate Limit). Đang ngủ 5 giây chờ nhả băng thông (Lần {r_429 + 1}/{max_429_retries})...")
            time.sleep(5)
            continue
        break

    if response.status_code != 200:
        raise Exception(f"Lỗi kết nối Zalo API: HTTP {response.status_code} - {response.text}")

    res_json = response.json()
    error_code = res_json.get("error_code")

    if error_code == 0:
        audio_url = res_json["data"]["url"]

        # ── BỘ LỌC 2: CHỐNG LỖI 404 CDN ──
        max_retries = 20
        for attempt in range(max_retries):
            print(f"   [->] Check file trên CDN Zalo (Lần {attempt + 1}/{max_retries})...")
            audio_data = requests.get(audio_url, stream=True)

            if audio_data.status_code == 200:
                with open(audio_path, "wb") as f:
                    for chunk in audio_data.iter_content(chunk_size=1024*1024):
                        if chunk: f.write(chunk)
                print("   [✔] Tải audio từ Zalo thành công!")
                return True

            elif audio_data.status_code == 404:
                time.sleep(2)
            else:
                raise Exception(f"Lỗi CDN Zalo không xác định: HTTP {audio_data.status_code}")

        raise Exception("Zalo render quá chậm (Vượt quá 40 giây chờ đợi).")

    elif error_code == 155:
        raise Exception("Zalo API Lỗi: Nội dung kịch bản vượt quá giới hạn 2000 ký tự.")
    elif error_code == 401:
        raise Exception("Zalo API Lỗi: Sai apikey. Check lại file config.py")
    else:
        raise Exception(f"Zalo API Lỗi (code {error_code}): {res_json.get('error_message')}")
"""