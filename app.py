import os
import uuid
import threading
import subprocess
from flask import Flask, request, render_template_string, send_file, after_this_request
import telebot

# ================= Configuration =================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Render Environment Variable থেকে টোকেন নেবে
UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# ================= FFmpeg Processor =================
def process_video(input_path, output_path):
    """
    ভিডিওর মেটাডাটা স্ট্রিপ, স্পিড ও ফ্রেম সামান্য পরিবর্তন করে রেন্ডার করে
    """
    # ফিল্টার: সামান্য জুম + স্পিড ১.০৩x + অডিও পিচ শিফট + কালার টিউন
    vf_filter = "scale=1.03*iw:1.03*ih,crop=iw:ih,setpts=PTS/1.03,eq=contrast=1.05:saturation=1.05"
    af_filter = "atempo=1.03,asetrate=44100*1.02"

    command = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf_filter,
        "-af", af_filter,
        "-map_metadata", "-1",  # মেটাডাটা সম্পূর্ণ রিমুভ
        "-c:v", "libx264",
        "-preset", "ultrafast",   # ফাস্ট প্রসেসিং
        "-crf", "26",
        "-c:a", "aac",
        output_path
    ]
    
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0


# ================= Web Interface (Flask) =================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Copyright Modifier</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-white min-h-screen flex items-center justify-center p-4">
    <div class="bg-slate-800 border border-slate-700 p-8 rounded-2xl shadow-2xl max-w-md w-full text-center">
        <h1 class="text-2xl font-bold mb-2 text-indigo-400">Video Copyright Modifier</h1>
        <p class="text-slate-400 text-sm mb-6">ভিডিও আপলোড করুন, স্বয়ংক্রিয়ভাবে ফিল্টার ও মেটাডাটা চেঞ্জ হয়ে ডাউনলোড শুরু হবে।</p>
        
        <form action="/" method="post" enctype="multipart/form-data" class="space-y-4" onsubmit="showLoading()">
            <div class="border-2 border-dashed border-slate-600 rounded-xl p-6 hover:border-indigo-500 transition cursor-pointer">
                <input type="file" name="video" id="video" accept="video/*" required class="block w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-600 file:text-white hover:file:bg-indigo-700 cursor-pointer"/>
            </div>
            
            <button type="submit" id="submitBtn" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-3 rounded-xl transition duration-200">
                Process & Download
            </button>
        </form>

        <div id="loader" class="hidden mt-6 text-sm text-amber-400 animate-pulse">
            প্রসেসিং চলছে, দয়া করে অপেক্ষা করুন...
        </div>
    </div>

    <script>
        function showLoading() {
            document.getElementById('loader').classList.remove('hidden');
            document.getElementById('submitBtn').disabled = true;
            document.getElementById('submitBtn').classList.add('opacity-50', 'cursor-not-allowed');
        }
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("video")
        if not file or file.filename == "":
            return "No video uploaded", 400

        task_id = str(uuid.uuid4())[:8]
        raw_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_{file.filename}")
        clean_path = os.path.join(PROCESSED_FOLDER, f"clean_{task_id}_{file.filename}")

        file.save(raw_path)
        success = process_video(raw_path, clean_path)

        # র ফাইল মুছে ফেলা
        if os.path.exists(raw_path):
            os.remove(raw_path)

        if not success:
            return "Processing failed with FFmpeg", 500

        # ইউজার ডাউনলোড শেষ করার পর ক্লিন ফাইলটি রিমুভ করে দেওয়া
        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(clean_path):
                    os.remove(clean_path)
            except Exception as e:
                app.logger.error(f"Cleanup error: {e}")
            return response

        return send_file(clean_path, as_attachment=True, download_name=f"clean_{file.filename}")

    return render_template_string(HTML_TEMPLATE)


# ================= Telegram Bot Handlers =================
if bot:
    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.reply_to(message, "👋 স্বাগতম! যেকোনো ভিডিও সেন্ড করুন, আমি মেটাডাটা ও ফিল্টার পরিবর্তন করে কপিরাইট বাইপাস উপযোগী করে ফেরত দেব।")

    @bot.message_handler(content_types=['video'])
    def handle_video(message):
        chat_id = message.chat.id
        status_msg = bot.reply_to(message, "📥 ভিডিও ডাউনলোড হচ্ছে...")
        
        task_id = str(uuid.uuid4())[:8]
        input_filename = os.path.join(UPLOAD_FOLDER, f"tg_{task_id}.mp4")
        output_filename = os.path.join(PROCESSED_FOLDER, f"tg_clean_{task_id}.mp4")

        try:
            file_info = bot.get_file(message.video.file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            with open(input_filename, 'wb') as f:
                f.write(downloaded_file)

            bot.edit_message_text("⚙️ প্রসেসিং চলছে (FFmpeg)...", chat_id=chat_id, message_id=status_msg.message_id)

            if process_video(input_filename, output_filename):
                bot.edit_message_text("📤 আপলোড হচ্ছে...", chat_id=chat_id, message_id=status_msg.message_id)
                with open(output_filename, 'rb') as video:
                    bot.send_video(chat_id, video, caption="✅ আপনার প্রসেস করা ভিডিও তৈরি!")
                bot.delete_message(chat_id, status_msg.message_id)
            else:
                bot.edit_message_text("❌ ভিডিও প্রসেস করতে ব্যর্থ হয়েছে।", chat_id=chat_id, message_id=status_msg.message_id)

        except Exception as e:
            bot.send_message(chat_id, f"⚠️ ত্রুটি: {str(e)}")
        finally:
            # ডিস্কের জায়গা খালি করতে ফাইল ডিলিট
            for f in [input_filename, output_filename]:
                if os.path.exists(f):
                    os.remove(f)

    def run_bot():
        print("Telegram bot started...")
        bot.infinity_polling(skip_pending=True)

    # ব্যাকগ্রাউন্ড থ্রেডে টেলিগ্রাম বট চালু
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()


# ================= Local / Entry Point =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
