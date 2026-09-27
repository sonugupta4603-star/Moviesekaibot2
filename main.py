import os
import time
import base64
import logging
import threading
from flask import Flask
import telebot
from openai import OpenAI

# ----------------- LOGGING SETUP -----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ----------------- FLASK WEB SERVER -----------------
# Render Web Service needs an active port to keep the container running
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Telegram AI Bot is running smoothly on Render!"

@app.route("/health")
def health():
    return {"status": "ok"}, 200

# ----------------- ENVIRONMENT VARIABLES -----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
HF_TOKEN = os.environ.get("HF_TOKEN")

if not BOT_TOKEN:
    logging.warning("⚠️ BOT_TOKEN environment variable is not set!")

if not HF_TOKEN:
    logging.warning("⚠️ HF_TOKEN environment variable is not set!")

# ----------------- CLIENT INITIALIZATIONS -----------------
# Telegram Bot Client
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# Hugging Face Router Client (OpenAI SDK Compatible)
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN or "dummy-key"
)

MODEL_NAME = "deepseek-ai/DeepSeek-V4.1-Flash:novita"

# ----------------- TELEGRAM BOT HANDLERS -----------------
if bot:
    @bot.message_handler(commands=["start", "help"])
    def handle_start(message):
        welcome_text = (
            "👋 **Hello! Main aapka AI assistant bot hoon.**\n\n"
            "✨ Aap mujhse:\n"
            "1. Koi bhi question ya chat kar sakte hain.\n"
            "2. Koi bhi photo bhej sakte hain (caption ke sath ya bina caption), main use analyze karke bataunga."
        )
        bot.reply_to(message, welcome_text, parse_mode="Markdown")

    # Image / Photo handler
    @bot.message_handler(content_types=["photo"])
    def handle_photo(message):
        try:
            bot.send_chat_action(message.chat.id, "typing")
            
            # Download highest quality photo from Telegram
            photo = message.photo[-1]
            file_info = bot.get_file(photo.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Convert image to base64 Data URI
            b64_image = base64.b64encode(downloaded_file).decode("utf-8")
            image_url = f"data:image/jpeg;base64,{b64_image}"
            
            # User caption or default prompt
            prompt = message.caption if message.caption else "Describe this image in detail."
            
            # Hugging Face router multimodal call
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ]
            )
            bot.reply_to(message, response.choices[0].message.content)

        except Exception as e:
            logging.error(f"Error handling photo: {e}")
            bot.reply_to(message, f"⚠️ Error analyzing photo: {str(e)}")

    # Text message handler
    @bot.message_handler(func=lambda message: True)
    def handle_text(message):
        try:
            bot.send_chat_action(message.chat.id, "typing")
            
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a helpful, smart, and friendly AI assistant."},
                    {"role": "user", "content": message.text}
                ]
            )
            bot.reply_to(message, response.choices[0].message.content)

        except Exception as e:
            logging.error(f"Error handling text: {e}")
            bot.reply_to(message, f"⚠️ Error: {str(e)}")

# ----------------- BACKGROUND BOT THREAD -----------------
def start_bot_polling():
    if not bot:
        logging.error("Cannot start bot: BOT_TOKEN is missing!")
        return
    
    logging.info("Starting Telegram Bot Polling...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
        except Exception as e:
            logging.error(f"Polling crashed with error: {e}. Retrying in 5 seconds...")
            time.sleep(5)

# ----------------- MAIN ENTRYPOINT -----------------
if __name__ == "__main__":
    # Start Telegram polling in a separate background thread
    bot_thread = threading.Thread(target=start_bot_polling, daemon=True)
    bot_thread.start()

    # Flask runs on the port provided by Render (defaults to 5000 locally)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
