import re
import stable_whisper # Đổi từ whisper sang stable_whisper
from config import WHISPER_MODEL_NAME

print(f"[*] Đang nạp model Stable-Whisper Local '{WHISPER_MODEL_NAME}' vào RAM...")
# Load model bằng cấu trúc của stable_whisper
whisper_model = stable_whisper.load_model(WHISPER_MODEL_NAME)

PUNCT_STRONG = re.compile(r'[.?!…]$')
PUNCT_WEAK   = re.compile(r'[,;:]$')

def flush(chunk, groups):
    if chunk:
        groups.append((
            chunk[0]["start"],
            chunk[-1]["end"],
            "".join(c.get("word", "") for c in chunk).strip(),
        ))
        chunk.clear()

def group_words_in_segment(words, n):
    if n == 1:
        return [(w["start"], w["end"], w.get("word", "").strip()) for w in words if w.get("word", "").strip()]

    groups, chunk = [], []
    half_n = max(1, n // 2)

    for w in words:
        raw = w.get("word", "")
        if not raw.strip(): continue
        chunk.append(w)
        text = raw.strip()

        if len(chunk) >= n or PUNCT_STRONG.search(text):
            flush(chunk, groups)
        elif PUNCT_WEAK.search(text) and len(chunk) >= half_n:
            flush(chunk, groups)

    flush(chunk, groups)
    return groups

def to_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def generate_local_whisper_srt(audio_path, srt_path, original_text, n):
    """
    SỬ DỤNG FORCED ALIGNMENT:
    Ép Whisper khớp timeline dựa trên TEXT GỐC, không tự nhận diện chữ nữa.
    """
    # Gọi hàm align thay vì transcribe, ném thẳng original_text vào đối chiếu
    result = whisper_model.align(audio_path, original_text, language="vi")
    
    # Ép kết quả về dạng dict cấu trúc chuẩn để giữ nguyên thuật toán băm sub cũ
    result_dict = result.to_dict()
    segments = result_dict.get("segments", [])
    
    all_groups = []
    for seg in segments:
        words = seg.get("words", [])
        if not words: continue
        all_groups.extend(group_words_in_segment(words, n))
        
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, (start, end, text) in enumerate(all_groups, 1):
            s = to_srt_time(start)
            e = to_srt_time(end)
            f.write(f"{idx}\n{s} --> {e}\n{text}\n\n")