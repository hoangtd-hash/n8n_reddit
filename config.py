import os

ZALO_API_KEY = "G53uzQYPHKfkRPUvUc2YmjYENxp8P3Pa"
WHISPER_MODEL_NAME = "small"  # "base" hoặc "small"
WORDS_PER_SUB_GROUP = 4      # Số từ tối đa trên một cụm sub Reels

OUTPUT_DIR = os.path.expanduser("~/n8n-clean/n8n-output")
os.makedirs(OUTPUT_DIR, exist_ok=True)