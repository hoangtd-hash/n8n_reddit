import os
import re
import time
import traceback
import threading  # Thêm thư viện khóa luồng
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, send_file

from config import OUTPUT_DIR, WORDS_PER_SUB_GROUP, SUB_MODE
import tts
import transcriber
import renderer

app = Flask(__name__)

# KHỞI TẠO LOCK: Đảm bảo tại một thời điểm chỉ có duy nhất 1 thread được gọi API TTS
tts_lock = threading.Lock()

def make_folder_name(clips):
    raw = clips[0].get('text', '') if clips else ''
    words = raw.strip().split()[:5]
    name = '_'.join(words)
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    name = name[:40].strip('_')
    timestamp = str(int(time.time()))
    return f"{name}_{timestamp}" if name else f"output_{timestamp}"

def process_io_task(idx, clip, job_dir):
    try:
        url = clip.get('url')
        text = clip.get('text', '')
        
        if not url:
            return idx, None, None, text, "Thiếu URL video"

        raw_clip = f"clip_{idx}.mp4"
        audio_clip = f"voice_{idx}.mp3"
        raw_clip_path = os.path.join(job_dir, raw_clip)
        audio_path = os.path.join(job_dir, audio_clip)

        # 1. Download video chạy song song tối đa hiệu suất mạng
        renderer.download_video(url, raw_clip_path)
        
        # 2. KHÓA TUẦN TỰ: Thằng nào tải video xong trước thì vào ăn API trước, thằng sau phải xếp hàng chờ
        with tts_lock:
            # VÒNG LẶP RETRY: Nếu API TTS lỗi, tự động thử lại tối đa 3 lần
            for attempt in range(3):
                try:
                    tts.get_zalo_voice(text, audio_path)
                    
                    # Kiểm tra file audio có tồn tại và có dung lượng thật không
                    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                        break # Thành công thì thoát vòng lặp retry
                except Exception as tts_err:
                    if attempt == 2:  # Quá 3 lần vẫn chết thì mới ném lỗi ra ngoài
                        raise tts_err
                    print(f"[!] Lỗi TTS phân cảnh {idx}, đang thử lại lần {attempt + 1}... Chi tiết: {str(tts_err)}")
                    time.sleep(2) # Nghỉ 2 giây trước khi thử lại
            
            # Khoảng nghỉ nhỏ 0.5 giây giữa các thread sau khi nhả khóa để tránh Microsoft quét spam IP
            time.sleep(0.5)

        return idx, raw_clip, audio_clip, text, None
    except Exception as e:
        return idx, None, None, None, str(e)

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

        folder_name = make_folder_name(clips)
        job_dir = os.path.join(OUTPUT_DIR, folder_name)
        os.makedirs(job_dir, exist_ok=True)
        print(f"\n[+] Khởi động render → thư mục: {folder_name} ({len(clips)} phân cảnh)")

        # Module 1 & 2: Chạy song song I/O
        print(f"[+] Bắt đầu I/O song song (Download + TTS)...")
        io_results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_io_task, idx, clip, job_dir) for idx, clip in enumerate(clips)]
            for future in futures:
                io_results.append(future.result())

        io_results.sort(key=lambda x: x[0])

        input_txt_content = ""

        # Module 3 & 4: Chạy tuần tự Compute để không tràn tài nguyên
        for res in io_results:
            idx, raw_clip, audio_clip, text, err = res
            if err:
                return jsonify({"status": "error", "message": f"Lỗi IO clip {idx}: {err}"}), 500
            if not raw_clip: continue

            raw_clip_path = os.path.join(job_dir, raw_clip)
            audio_path    = os.path.join(job_dir, audio_clip)
            norm_clip     = f"norm_{idx}.mp4"
            srt_file      = f"sub_{idx}.srt"
            srt_path      = os.path.join(job_dir, srt_file)

            print(f" -> [{idx+1}/{len(clips)}] Đang chạy Whisper & Render FFmpeg...")
            result_path = transcriber.generate_local_whisper_srt(audio_path, srt_path, text, WORDS_PER_SUB_GROUP)
            sub_file = os.path.basename(result_path)

            duration = renderer.get_audio_duration(audio_path)
            renderer.render_single_clip(raw_clip, audio_clip, sub_file, norm_clip, duration, job_dir)

            input_txt_content += f"file '{norm_clip}'\n"

        # Module 5: Ghép phim
        final_output = "final_output.mp4"
        print(f"[+] Đang gộp toàn bộ phân cảnh thành {final_output}...")
        renderer.concat_all_clips(input_txt_content, final_output, job_dir)

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

@app.route('/get_video', methods=['GET'])
def get_video():
    try:
        video_path = request.args.get('path', '')
        if not video_path:
            return jsonify({"status": "error", "message": "Thiếu tham số ?path="}), 400

        if not os.path.exists(video_path):
            return jsonify({"status": "error", "message": f"File không tồn tại: {video_path}"}), 404

        print(f"[+] Đang gửi file về n8n: {video_path}")
        return send_file(
            video_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name=os.path.basename(video_path)
        )

    except Exception as e:
        print(f"[❌] Lỗi get_video: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000)