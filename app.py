import os
from flask import Flask, request, jsonify
import traceback

from config import OUTPUT_DIR, WORDS_PER_SUB_GROUP
import tts
import transcriber
import renderer

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render():
    try:
        data = request.json
        clips = []

        if isinstance(data, list) and len(data) > 0:
            clips = data[0]['clips'] if 'clips' in data[0] else data
        elif isinstance(data, dict):
            clips = data.get('clips', [])

        if not clips:
            return jsonify({"status": "error", "message": "Không tìm thấy danh sách phân cảnh"}), 400

        print(f"[+] Khởi động render hệ thống module với {len(clips)} phân cảnh...")

        # 1. Clear file cũ
        for f in os.listdir(OUTPUT_DIR):
            if f.startswith("clip_") or f.startswith("norm_") or f.startswith("sub_") or f.startswith("voice_") or f in ["inputs.txt", "final_output.mp4"]:
                try: os.remove(os.path.join(OUTPUT_DIR, f))
                except: pass

        input_txt_content = ""

        # 2. Chạy luồng tuần tự qua từng module
        for idx, clip in enumerate(clips):
            url = clip.get('url')
            text = clip.get('text', '')
            if not url: continue

            # Định nghĩa tên file tương đối
            raw_clip = f"clip_{idx}.mp4"
            audio_clip = f"voice_{idx}.mp3"
            norm_clip = f"norm_{idx}.mp4"
            srt_file = f"sub_{idx}.srt"

            raw_clip_path = os.path.join(OUTPUT_DIR, raw_clip)
            audio_path = os.path.join(OUTPUT_DIR, audio_clip)
            srt_path = os.path.join(OUTPUT_DIR, srt_file)

            # Module 1: Tải video
            print(f" -> [{idx+1}/{len(clips)}] Đang tải video...")
            renderer.download_video(url, raw_clip_path)

            # Module 2: Tạo giọng nói Zalo AI
            print(f" -> Đang gọi module Zalo TTS...")
            tts.get_zalo_voice(text, audio_path)

            # Module 3: Chạy Whisper băm sub
            print(f" -> Đang gọi module Whisper Local...")
            transcriber.generate_local_whisper_srt(audio_path, srt_path, WORDS_PER_SUB_GROUP)

            # Module 4: Đo độ dài và render từng phân cảnh bằng GPU Mac
            duration = renderer.get_audio_duration(audio_path)
            print(f" -> Đang gọi module FFmpeg Render (GPU)...")
            renderer.render_single_clip(raw_clip, audio_clip, srt_file, norm_clip, duration)

            input_txt_content += f"file '{norm_clip}'\n"

        # Module 5: Ghép phim tổng hợp
        print("[+] Đang gộp toàn bộ phân cảnh thành video cuối cùng...")
        renderer.concat_all_clips(input_txt_content)

        return jsonify({"status": "success", "video": f"{OUTPUT_DIR}/final_output.mp4"})

    except Exception as e:
        print(f"[❌] Lỗi hệ thống: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000)