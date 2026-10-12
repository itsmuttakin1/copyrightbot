import os
import telebot
from processor import process_video

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "ভিডিওটি সেন্ড করুন, আমি প্রসেস করে মেটাডাটা ও ফিল্টার পরিবর্তন করে দিচ্ছি!")

@bot.message_handler(content_types=['video'])
def handle_video(message):
    status_msg = bot.reply_to(message, "ভিডিও ডাউনলোড হচ্ছে...")
    try:
        file_info = bot.get_file(message.video.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        input_filename = f"tg_{message.chat.id}_input.mp4"
        output_filename = f"tg_{message.chat.id}_clean.mp4"

        with open(input_filename, 'wb') as f:
            f.write(downloaded_file)

        bot.edit_message_text("প্রসেসিং চলছে (FFmpeg)...", chat_id=message.chat.id, message_id=status_msg.message_id)
        
        if process_video(input_filename, output_filename):
            with open(output_filename, 'rb') as video:
                bot.send_video(message.chat.id, video, caption="এখানে আপনার প্রসেস করা ভিডিও!")
        else:
            bot.send_message(message.chat.id, "প্রসেসিং ব্যর্থ হয়েছে।")

    except Exception as e:
        bot.send_message(message.chat.id, f"এরর: {str(e)}")
    finally:
        # ফাইল ডিলিট করে র‍্যাম/ডিস্ক খালি করা
        for f in [input_filename, output_filename]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    bot.infinity_polling()
