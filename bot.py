import os
import logging
import subprocess
from flask import Flask, request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import asyncio
from PIL import Image

# Config
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://social-content-creator.onrender.com/webhook")

# Flask app
app = Flask(__name__)

# Telegram app
application = Application.builder().token(TOKEN).build()

# Logs
logging.basicConfig(level=logging.INFO)

# --- Funções do Bot ---

async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("🖼️ Imagem", callback_data="imagem")],
        [InlineKeyboardButton("🎞️ Animada", callback_data="animada")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Escolha o tipo de figurinha:", reply_markup=reply_markup)

async def button(update: Update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "imagem":
        await query.edit_message_text("📷 Envie uma imagem para transformar em figurinha.")
        context.user_data["modo"] = "imagem"

    elif query.data == "animada":
        await query.edit_message_text("🎞️ Envie um GIF ou vídeo curto para transformar em figurinha animada.")
        context.user_data["modo"] = "animada"

async def handle_media(update: Update, context):
    modo = context.user_data.get("modo")

    if modo == "imagem" and update.message.photo:
        file = await update.message.photo[-1].get_file()
        file_path = "temp.jpg"
        await file.download_to_drive(file_path)

        # Converter imagem para figurinha
        img = Image.open(file_path)
        img.thumbnail((512, 512))
        webp_path = "sticker.webp"
        img.save(webp_path, "WEBP")

        await update.message.reply_sticker(sticker=InputFile(webp_path))

        os.remove(file_path)
        os.remove(webp_path)

    elif modo == "animada" and (update.message.animation or update.message.video):
        file = await (update.message.animation or update.message.video).get_file()
        file_path = "temp.mp4"
        await file.download_to_drive(file_path)

        # Converter para WEBM com ffmpeg
        webm_path = "sticker.webm"
        subprocess.run([
            "ffmpeg", "-y", "-i", file_path,
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease,fps=30",
            "-c:v", "libvpx-vp9", "-b:v", "500K",
            webm_path
        ], check=True)

        await update.message.reply_sticker(sticker=InputFile(webm_path))

        os.remove(file_path)
        os.remove(webm_path)

# --- Registrar Handlers ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.ANIMATION, handle_media))

# --- Webhook ---
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.process_update(update))
    return "ok"

if __name__ == "__main__":
    # Define webhook no Telegram
    import requests
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}"
    requests.get(url)

    print("🤖 Bot rodando no modo webhook com botões e figurinhas animadas!")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
