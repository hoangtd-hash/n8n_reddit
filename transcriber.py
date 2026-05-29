import re
import torch
import stable_whisper
from config import WHISPER_MODEL_NAME

_whisper_model = None

def get_model():
    global _whisper_model
    if _whisper_model is None:
        # Bắt buộc dùng CPU vì PyTorch MPS trên Mac chưa support float64 cho thuật toán DTW của Whisper
        device = "cpu" 
        print(f"[*] Đang nạp model Stable-Whisper '{WHISPER_MODEL_NAME}' lên {device.upper()}...")
        _whisper_model = stable_whisper.load_model(WHISPER_MODEL_NAME, device=device)
    return _whisper_model

PUNCT_STRONG = re.compile(r'[.?!…]$')
PUNCT_WEAK   = re.compile(r'[,;:]$')

def flush(chunk, groups):
    if chunk:
        groups.append((
            chunk[0]["start"],
            chunk[-1]["end"],
            list(chunk),
        ))
        chunk.clear()

def group_words_in_segment(words, n):
    if n == 1:
        return [(w["start"], w["end"], [w]) for w in words if w.get("word", "").strip()]

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

def to_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def generate_local_whisper_srt(audio_path, srt_path, original_text, n):
    from config import SUB_MODE, SUB_FONT, SUB_SIZE, SUB_MARGIN_V

    model = get_model()
    result = model.align(audio_path, original_text, language="vi")
    result_dict = result.to_dict()
    segments = result_dict.get("segments", [])

    all_groups = []
    for seg in segments:
        words = seg.get("words", [])
        if not words: continue
        all_groups.extend(group_words_in_segment(words, n))

    if SUB_MODE == "karaoke":
        ass_path = srt_path.replace(".srt", ".ass")
        ass_header = f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{SUB_FONT},{SUB_SIZE},&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0.8,0,2,10,10,{SUB_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_header)
            for start, end, word_list in all_groups:
                s = to_ass_time(start)
                e = to_ass_time(end)
                line = ""
                for w in word_list:
                    word_text = w.get("word", "").strip()
                    if not word_text: continue
                    duration_cs = int(round((w.get("end", end) - w.get("start", start)) * 100))
                    line += f"{{\\k{duration_cs}}}{word_text} "
                f.write(f"Dialogue: 0,{s},{e},Default,,0,0,0,,{line.strip()}\n")
        return ass_path
    else:
        with open(srt_path, "w", encoding="utf-8") as f:
            for idx, (start, end, word_list) in enumerate(all_groups, 1):
                text = "".join(w.get("word", "") for w in word_list).strip()
                s = to_srt_time(start)
                e = to_srt_time(end)
                f.write(f"{idx}\n{s} --> {e}\n{text}\n\n")
        return srt_path