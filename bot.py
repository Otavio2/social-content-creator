import os
import logging
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from PIL import Image

# --- CONFIGURAÇÃO ---
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Ex.: https://seu-bot.onrender.com/webhook

logging.basicConfig(level=logging.INFO)

# --- APLICATIVO TELEGRAM ---
application = Application.builder().token(TOKEN).build()

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🖼️ Imagem", callback_data="imagem")],
        [InlineKeyboardButton("🎞️ Animada", callback_data="animada")],
    ]
    await update.message.reply_text(
        "Escolha o tipo de figurinha:", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "imagem":
        await query.edit_message_text("📷 Envie uma imagem para transformar em figurinha.")
        context.user_data["modo"] = "imagem"
    elif query.data == "animada":
        await query.edit_message_text("🎞️ Envie um GIF ou vídeo curto para transformar em figurinha animada.")
        context.user_data["modo"] = "animada"

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    modo = context.user_data.get("modo")
    
    if modo == "imagem" and update.message.photo:
        file = await update.message.photo[-1].get_file()
        file_path = "temp.jpg"
        await file.download_to_drive(file_path)
        img = Image.open(file_path)
        img.thumbnail((512,512))
        webp_path = "sticker.webp"
        img.save(webp_path, "WEBP")
        await update.message.reply_sticker(InputFile(webp_path))
        os.remove(file_path)
        os.remove(webp_path)

    elif modo == "animada" and (update.message.animation or update.message.video):
        file = await (update.message.animation or update.message.video).get_file()
        file_path = "temp.mp4"
        await file.download_to_drive(file_path)
        webm_path = "sticker.webm"
        subprocess.run([
            "ffmpeg", "-y", "-i", file_path,
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease,fps=30",
            "-c:v", "libvpx-vp9", "-b:v", "500K",
            webm_path
        ], check=True)
        await update.message.reply_sticker(InputFile(webm_path))
        os.remove(file_path)
        os.remove(webm_path)

# --- REGISTRAR HANDLERS ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.ANIMATION, handle_media))

# --- EXECUÇÃO COM WEBHOOK ---
if __name__ == "__main__":
    import asyncio
    async def main():
        await application.bot.set_webhook(WEBHOOK_URL)
        await application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL
        )
    asyncio.run(main())
