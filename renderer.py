import os
import subprocess
import shutil
import requests
from config import OUTPUT_DIR

ffmpeg_path  = shutil.which("ffmpeg")  or "/opt/homebrew/bin/ffmpeg" or "ffmpeg"
ffprobe_path = ffmpeg_path.replace("ffmpeg", "ffprobe")

def download_video(url, path):
    r = requests.get(url, stream=True)
    with open(path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024*1024):
            if chunk: f.write(chunk)

def get_audio_duration(audio_path):
    cmd = f'{ffprobe_path} -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{audio_path}"'
    res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try: return float(res.stdout.strip())
    except: return 10.0

def render_single_clip(raw_clip, audio_clip, srt_file, norm_clip, duration, job_dir=None):
    """
    Render một phân cảnh, chạy trong job_dir.
    -map 0:v -map 1:a → chỉ lấy hình Pexels + tiếng TTS.
    -ar 44100 -ac 2   → chuẩn Stereo để concat không bị câm tiếng.
    """
    cwd = job_dir or OUTPUT_DIR
    cmd = (
        f'{ffmpeg_path} -y -stream_loop 5 -i "{raw_clip}" -i "{audio_clip}" '
        f'-vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,'
        f'subtitles={srt_file}:force_style=\'Fontname=Arial,Fontsize=24,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=3,Alignment=2,MarginV=140\'" '
        f'-map 0:v -map 1:a '
        f'-r 30 -c:v h264_videotoolbox -b:v 6000k -c:a aac -b:a 192k -ar 44100 -ac 2 -t {duration} "{norm_clip}"'
    )
    process = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise Exception(process.stderr.decode(errors='ignore'))

def concat_all_clips(input_txt_content, output_filename="final_output.mp4", job_dir=None):
    cwd = job_dir or OUTPUT_DIR
    inputs_file_path = os.path.join(cwd, "inputs.txt")
    with open(inputs_file_path, "w") as f:
        f.write(input_txt_content)

    cmd = f'{ffmpeg_path} -f concat -safe 0 -i inputs.txt -y -c copy "{output_filename}"'
    process = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise Exception(process.stderr.decode(errors='ignore'))
