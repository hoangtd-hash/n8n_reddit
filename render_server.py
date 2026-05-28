import os
import subprocess
import shutil
from flask import Flask, request, jsonify
import requests
import traceback
from gtts import gTTS

app = Flask(__name__)

OUTPUT_DIR = os.path.expanduser("~/n8n-clean/n8n-output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_srt(text, total_duration, srt_path):
    """Băm nhỏ câu thoại thành các cụm 4-5 từ để tạo hiệu ứng sub chạy từng cụm như Reels"""
    words = text.split()
    chunks = []
    chunk_size = 4 # Số từ hiển thị cùng lúc trên màn hình
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i+chunk_size]))
    
    if not chunks:
        return False
        
    time_per_chunk = total_duration / len(chunks)
    
    def format_srt_time(secs):
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)
        ms = int((secs % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, chunk in enumerate(chunks):
            start = idx * time_per_chunk
            end = (idx + 1) * time_per_chunk
            f.write(f"{idx + 1}\n")
            f.write(f"{format_srt_time(start)} --> {format_srt_time(end)}\n")
            f.write(f"{chunk}\n\n")
    return True

@app.route('/render', methods=['POST'])
def render():
    try:
        data = request.json
        clips = []

        if isinstance(data, list) and len(data) > 0:
            if 'clips' in data[0]:
                clips = data[0]['clips']
            else:
                clips = data
        elif isinstance(data, dict):
            clips = data.get('clips', [])

        if not clips:
            return jsonify({"status": "error", "message": "Không tìm thấy danh sách clips hợp lệ"}), 400

        print(f"[+] Nhận lệnh render video với {len(clips)} phân cảnh...")

        # Dọn dẹp các file rác cũ
        for f in os.listdir(OUTPUT_DIR):
            if f.startswith("clip_") or f.startswith("norm_") or f.startswith("sub_") or f.startswith("voice_") or f in ["inputs.txt", "final_output.mp4"]:
                try:
                    os.remove(os.path.join(OUTPUT_DIR, f))
                except:
                    pass

        ffmpeg_path = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg" or "/usr/local/bin/ffmpeg" or "ffmpeg"
        ffprobe_path = ffmpeg_path.replace("ffmpeg", "ffprobe")
        input_txt_content = ""
        
        for idx, clip in enumerate(clips):
            url = clip.get('url')
            text = clip.get('text', '')
            
            if not url:
                continue

            raw_clip = f"clip_{idx}.mp4"
            audio_clip = f"voice_{idx}.mp3"
            norm_clip = f"norm_{idx}.mp4"
            srt_file = f"sub_{idx}.srt"

            raw_clip_path = os.path.join(OUTPUT_DIR, raw_clip)
            audio_path = os.path.join(OUTPUT_DIR, audio_clip)
            srt_path = os.path.join(OUTPUT_DIR, srt_file)
            
            # Tải video gốc
            print(f" -> [{idx+1}/{len(clips)}] Đang tải video phân cảnh...")
            r = requests.get(url, stream=True)
            with open(raw_clip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            
            # Tạo giọng đọc AI
            tts = gTTS(text=text, lang='vi')
            tts.save(audio_path)
            
            # Đo chính xác thời gian chạy của file Voice
            duration_cmd = f'{ffprobe_path} -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{audio_path}"'
            duration_res = subprocess.run(duration_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                duration = float(duration_res.stdout.strip())
            except:
                duration = 10.0

            # Đẻ file phụ đề tự động ngắt câu theo thời gian voice
            generate_srt(text, duration, srt_path)

            print(f" -> Đang ép GPU Mac render chữ nhảy theo thời gian...")
            # Sử dụng bộ lọc subtitles bọc qua lõi libass để hiển thị mượt tiếng Việt không bao giờ lỗi font
            normalize_cmd = (
                f'{ffmpeg_path} -y -stream_loop 5 -i "{raw_clip}" -i "{audio_clip}" '
                f'-vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,'
                f'subtitles={srt_file}:force_style=\'Fontname=Arial,Fontsize=26,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=3,Alignment=2,MarginV=120\'" '
                f'-r 30 -c:v h264_videotoolbox -b:v 6000k -c:a aac -b:a 192k -t {duration} "{norm_clip}"'
            )
            
            norm_process = subprocess.run(normalize_cmd, shell=True, cwd=OUTPUT_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if norm_process.returncode != 0:
                error_details = norm_process.stderr.decode(errors='ignore')
                print(f"[❌] Lỗi render phân cảnh {idx}: {error_details}")
                return jsonify({"status": "error", "message": f"Lỗi tại phân cảnh {idx}", "details": error_details}), 500
            
            input_txt_content += f"file '{norm_clip}'\n"

        # Ghi file inputs.txt để gộp bài
        inputs_file_path = os.path.join(OUTPUT_DIR, "inputs.txt")
        with open(inputs_file_path, "w") as f:
            f.write(input_txt_content)

        # Ghép nối các phân cảnh thành phim cuối cùng
        print("[+] Đang tiến hành ghép các phân cảnh thành video thành phẩm...")
        ffmpeg_cmd = f'{ffmpeg_path} -f concat -safe 0 -i inputs.txt -y -c copy final_output.mp4'
        process = subprocess.run(ffmpeg_cmd, shell=True, cwd=OUTPUT_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if process.returncode == 0:
            print("[✔] Xuất video thành công tại: ~/n8n-clean/n8n-output/final_output.mp4")
            return jsonify({"status": "success", "video": f"{OUTPUT_DIR}/final_output.mp4"})
        else:
            error_msg = process.stderr.decode(errors='ignore')
            print(f"[❌] Lỗi FFmpeg ráp nối: {error_msg}")
            return jsonify({"status": "error", "message": "Lỗi khi ráp phim", "details": error_msg}), 500

    except Exception as e:
        print(f"[❌] Lỗi hệ thống: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print("[*] Server Render Sub Dynamic đang lắng nghe tại cổng 9000...")
    app.run(host='0.0.0.0', port=9000)