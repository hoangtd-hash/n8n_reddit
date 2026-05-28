import os
import re
import time
from flask import Flask, request, jsonify
import traceback

from config import OUTPUT_DIR, WORDS_PER_SUB_GROUP
import tts
import transcriber
import renderer

app = Flask(__name__)

def make_folder_name(clips):
    """
    Lấy text của clip đầu tiên, bốc 5 từ đầu làm tên thư mục.
    Xóa ký tự đặc biệt, thay space bằng _, giới hạn 40 ký tự.
    Ví dụ: "AI đang thay thế lập trình viên" → "AI_đang_thay_thế_lập"
    """
    raw = clips[0].get('text', '') if clips else ''
    words = raw.strip().split()[:5]
    name = '_'.join(words)
    # Xóa ký tự không hợp lệ cho tên thư mục
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    name = name[:40].strip('_')
    # Thêm timestamp phía sau để không bao giờ trùng
    timestamp = str(int(time.time()))
    return f"{name}_{timestamp}" if name else f"output_{timestamp}"

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

        # Tạo thư mục riêng cho job này
        folder_name = make_folder_name(clips)
        job_dir = os.path.join(OUTPUT_DIR, folder_name)
        os.makedirs(job_dir, exist_ok=True)
        print(f"[+] Khởi động render → thư mục: {folder_name} ({len(clips)} phân cảnh)")

        input_txt_content = ""

        # Chạy luồng tuần tự qua từng module
        for idx, clip in enumerate(clips):
            url  = clip.get('url')
            text = clip.get('text', '')
            if not url: continue

            raw_clip   = f"clip_{idx}.mp4"
            audio_clip = f"voice_{idx}.mp3"
            norm_clip  = f"norm_{idx}.mp4"
            srt_file   = f"sub_{idx}.srt"

            raw_clip_path = os.path.join(job_dir, raw_clip)
            audio_path    = os.path.join(job_dir, audio_clip)
            srt_path      = os.path.join(job_dir, srt_file)

            # Module 1: Tải video
            print(f" -> [{idx+1}/{len(clips)}] Đang tải video...")
            renderer.download_video(url, raw_clip_path)

            # Module 2: Tạo giọng nói
            print(f" -> Đang gọi module TTS...")
            tts.get_zalo_voice(text, audio_path)

            # Module 3: Whisper Forced Alignment
            print(f" -> Đang gọi module Whisper Local (Forced Alignment)...")
            transcriber.generate_local_whisper_srt(audio_path, srt_path, text, WORDS_PER_SUB_GROUP)

            # Module 4: Render từng phân cảnh bằng GPU Mac
            duration = renderer.get_audio_duration(audio_path)
            print(f" -> Đang gọi module FFmpeg Render (GPU)...")
            renderer.render_single_clip(raw_clip, audio_clip, srt_file, norm_clip, duration, job_dir)

            input_txt_content += f"file '{norm_clip}'\n"

        # Module 5: Ghép phim tổng hợp
        final_output = "final_output.mp4"
        print(f"[+] Đang gộp toàn bộ phân cảnh thành {final_output}...")
        renderer.concat_all_clips(input_txt_content, final_output, job_dir)

        # Giữ nguyên file trung gian để tham khảo khi test
        # Sau khi test xong sẽ thêm lệnh xóa ở đây

        final_path = os.path.join(job_dir, final_output)
        print(f"[✔] Render hoàn tất: {final_path}")
        return jsonify({
            "status": "success",
            "video": final_path,
            "folder": folder_name
        })

    except Exception as e:
        print(f"[❌] Lỗi hệ thống: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000)
