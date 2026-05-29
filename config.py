import os

ZALO_API_KEY = "wATKT4mrJdGjuv77VeZRAeUQpV4o8ugn"
WHISPER_MODEL_NAME = "small"  # "base" hoặc "small"
WORDS_PER_SUB_GROUP = 4      # Số từ tối đa trên một cụm sub Reels

OUTPUT_DIR = os.path.expanduser("~/n8n-clean/n8n-output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

FONTS_DIR = os.path.expanduser("~/n8n-clean/fonts")

# ── CHẾ ĐỘ SUB ──
# "classic"  : Trắng to, viền đen, đơn giản — đang hoạt động tốt với stock video
# "karaoke"  : Highlight từng từ màu vàng theo thời gian đọc
SUB_MODE = "classic"

# ── CẤU HÌNH STYLE SUB ──
SUB_FONT     = "Arial"
SUB_SIZE     = 24       # classic mode
SUB_MARGIN_V = 140      # khoảng cách từ dưới lên
