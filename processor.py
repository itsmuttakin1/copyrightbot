import subprocess
import os

def process_video(input_path, output_path):
    """
    FFmpeg দিয়ে ভিডিওর মেটাডাটা রিমুভ, সামান্য জুম, স্পিড ও অডিও পরিবর্তন
    """
    # ফিল্টার: সামান্য জুম + স্পিড ১.০৩x + অডিও পিচ শিফট + কালার টিউন
    vf_filter = "scale=1.03*iw:1.03*ih,crop=iw:ih,setpts=PTS/1.03,eq=contrast=1.05:saturation=1.05"
    af_filter = "atempo=1.03,asetrate=44100*1.02"

    command = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf_filter,
        "-af", af_filter,
        "-map_metadata", "-1",  # সমস্ত মেটাডাটা মুছে ফেলা
        "-c:v", "libx264",
        "-preset", "ultrafast",   # Render-এর ফ্রি CPU রিসোর্সের জন্য ফাস্ট রেন্ডার
        "-crf", "26",
        "-c:a", "aac",
        output_path
    ]
    
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0
