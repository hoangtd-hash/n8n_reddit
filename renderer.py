import os
import subprocess
import shutil
import requests
from config import OUTPUT_DIR, FONTS_DIR, SUB_MODE, SUB_FONT, SUB_SIZE, SUB_MARGIN_V

ffmpeg_path  = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg" or "ffmpeg"
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

def render_single_clip(raw_clip, audio_clip, sub_file, norm_clip, duration, job_dir=None):
    cwd = job_dir or OUTPUT_DIR

    if SUB_MODE == "karaoke":
        sub_filter = (
            f'ass={sub_file}:fontsdir={FONTS_DIR}'
        )
    else:
        sub_filter = (
            f'subtitles={sub_file}:fontsdir={FONTS_DIR}:'
            f'force_style=\'Fontname={SUB_FONT},Fontsize={SUB_SIZE},Bold=1,'
            f'PrimaryColour=&HFFFFFF,OutlineColour=&H000000,'
            f'BorderStyle=1,Outline=3,Alignment=2,MarginV={SUB_MARGIN_V}\''
        )

    cmd = (
        f'{ffmpeg_path} -y -stream_loop 5 -i "{raw_clip}" -i "{audio_clip}" '
        f'-vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,{sub_filter}" '
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