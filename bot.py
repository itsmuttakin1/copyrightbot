import os
import glob
import time
import html
import shutil
import subprocess
import threading
from flask import Flask
import telebot
import yt_dlp
import requests

# ১. Render পোর্টের জন্য ওয়েব সার্ভার
app = Flask(__name__)

@app.route('/')
def home():
    return "Editor Bot is Running Healthy!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ২. টেলিগ্রাম বট কনফিগারেশন
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN এনভায়রনমেন্ট ভ্যারিয়েবল পাওয়া যায়নি!")

bot = telebot.TeleBot(BOT_TOKEN)

FFMPEG_PATH = os.path.abspath("ffmpeg_bin/ffmpeg") if os.path.exists("ffmpeg_bin/ffmpeg") else "ffmpeg"
FFPROBE_PATH = os.path.abspath("ffmpeg_bin/ffprobe") if os.path.exists("ffmpeg_bin/ffprobe") else "ffprobe"

def resolve_url(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.url
    except Exception:
        return url

def edit_video_with_ffmpeg(input_video, overlay_image, output_video):
    """
    নিখুঁত স্কেলিং ও পিক্সেল ফরম্যাট ফিক্স করা FFmpeg ফাংশন
    """
    # ১. scale2ref ফিল্টারে মূল ভিডিওর সাপেক্ষে ইমেজকে 45% স্কেল করা
    # ২. format=rgba নিশ্চিত করে ট্র্যান্সপারেন্ট পিএনজি ওভারলে করা
    # ৩. format=yuv420p দিয়ে টেলিগ্রামের কমপ্যাটিবিলিটি বজায় রাখা
    filter_complex = (
        "[0:v]eq=contrast=1.12:brightness=0.03:saturation=1.22[enhanced];"
        "[1:v]format=rgba[img];"
        "[img][enhanced]scale2ref=w='iw*0.48':h='ow/mdar'[overlay_scaled][bg];"
        "[bg][overlay_scaled]overlay=(W-w)/2:H-h-90:shortest=1,format=yuv420p[v_out]"
    )

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_video,
        "-loop", "1",
        "-i", overlay_image,
        "-filter_complex", filter_complex,
        "-map", "[v_out]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",           # aac দিলে অডিও কোডেক এরর পুরোপুরি বন্ধ হবে
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_video
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg Error: {result.stderr[-350:]}")

@bot.message_handler(commands=['start', 'help'])
def start_cmd(message):
    welcome_text = (
        f"👋 **স্বাগতম {message.from_user.first_name}!** 🎬\n\n"
        "Facebook, TikTok অথবা Instagram-এর যেকোনো ভিডিওর লিংক পাঠান।\n\n"
        "⚡ **বট স্বয়ংক্রিয়ভাবে:**\n"
        "• ভিডিওটি ডাউনলোড করবে\n"
        "• কালার ভাইব্র্যান্ট করবে\n"
        "• 'Comment Box Check' ব্যাজ ওভারলে করবে\n"
        "• এডিট করে সরাসরি আপনাকে পাঠিয়ে দেবে!\n\n"
        "👉 এখনই একটি লিংক পাঠিয়ে পরীক্ষা করুন।"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def process_video(message):
    raw_url = message.text.strip()

    if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        bot.reply_to(message, "⚠️ দয়া করে একটি সঠিক ভিডিও URL দিন।")
        return

    if "youtu" in raw_url:
        bot.reply_to(message, "⚠️ ইউটিউব ভিডিও সাপোর্ট করে না। ফেসবুক, ইনস্টাগ্রাম বা টিকটকের লিংক দিন।")
        return

    valid_platforms = ["facebook.com", "fb.watch", "tiktok.com", "instagram.com"]
    if not any(p in raw_url.lower() for p in valid_platforms):
        bot.reply_to(message, "⚠️ শুধুমাত্র Facebook, TikTok এবং Instagram ভিডিও লিংক সাপোর্ট করে।")
        return

    overlay_png = "comnt.png"
    if not os.path.exists(overlay_png):
        bot.reply_to(message, "⚠️ রিপোজিটরিতে `comnt.png` ফাইলটি পাওয়া যায়নি! দয়া করে GitHub-এ ফাইলটি আপলোড করুন।")
        return

    status_msg = bot.reply_to(message, "⏳ সম্পূর্ণ ভিডিও ডাউনলোড করা হচ্ছে...")
    user_id = message.chat.id
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)

    resolved_url = resolve_url(raw_url)
    raw_video_path = f"{output_dir}/raw_video.mp4"
    edited_video_path = f"{output_dir}/edited_video.mp4"

    ydl_opts = {
        'format': 'best[filesize<45M]/bestvideo[filesize<35M]+bestaudio[filesize<10M]/best',
        'merge_output_format': 'mp4',
        'outtmpl': raw_video_path,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    if os.path.exists("ffmpeg_bin"):
        ydl_opts['ffmpeg_location'] = os.path.abspath("ffmpeg_bin")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(resolved_url, download=True)
            video_title = info.get('title') or info.get('description') or "Social Video"
            if len(video_title) > 200:
                video_title = video_title[:200] + "..."

        if not os.path.exists(raw_video_path):
            found_files = glob.glob(f"{output_dir}/raw_video*")
            if found_files:
                raw_video_path = found_files[0]
            else:
                bot.edit_message_text("❌ ভিডিও ডাউনলোড করা সম্ভব হয়নি।", user_id, status_msg.message_id)
                return

        bot.edit_message_text("🎨 কালার অ্যাডজাস্ট এবং ফটো ওভারলে এডিটিং চলছে...", user_id, status_msg.message_id)
        edit_video_with_ffmpeg(raw_video_path, overlay_png, edited_video_path)

        file_size_mb = os.path.getsize(edited_video_path) / (1024 * 1024)
        if file_size_mb > 49.5:
            bot.edit_message_text("❌ এডিটের পর ফাইল সাইজ ৫০MB অতিক্রম করায় টেলিগ্রামে পাঠানো সম্ভব নয়।", user_id, status_msg.message_id)
            return

        bot.edit_message_text("📤 এডিটেড সম্পূর্ণ ভিডিও আপলোড হচ্ছে...", user_id, status_msg.message_id)

        escaped_title = html.escape(video_title)
        caption_text = (
            f"🎬 <b>ভিডিও রেডি!</b>\n\n"
            f"📝 <b>ক্যাপশন (ক্লিক করলে কপি হবে):</b>\n"
            f"<code>{escaped_title}</code>\n\n"
            f'video download by "<a href="https://t.me/mrghost_121">Mr Ghost</a>"'
        )

        with open(edited_video_path, 'rb') as vf:
            bot.send_video(user_id, vf, caption=caption_text, parse_mode="HTML", supports_streaming=True)

        bot.delete_message(user_id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ ত্রুটি: {str(e)[:150]}", user_id, status_msg.message_id)

    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()

    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass

    print("Bot is successfully running...")

    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 409:
                time.sleep(5)
            else:
                time.sleep(3)
        except Exception:
            time.sleep(3)
