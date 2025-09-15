import os
import asyncio
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from PIL import Image
import io

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "SEU_TOKEN_AQUI")
WEBHOOK_URL = "https://social-content-creator.onrender.com"

# Flask app
app = Flask(__name__)

# Bot app
application = Application.builder().token(BOT_TOKEN).build()

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🖼️ Figurinha Normal", callback_data="normal")],
        [InlineKeyboardButton("🎞️ Figurinha Animada", callback_data="animada")]
    ]
    await update.message.reply_text(
        "🤖 Olá! Me envie uma imagem ou vídeo curto que eu transformo em figurinha.\n"
        "Escolha abaixo como quer salvar:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe imagem/foto enviada"""
    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("⚠️ Só aceito imagens ou vídeos curtos!")
        return

    file = await context.bot.get_file(file_id)
    image_bytes = await file.download_as_bytearray()

    # converte para WEBP (formato de sticker)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img.thumbnail((512, 512))
    bio = io.BytesIO()
    bio.name = "sticker.webp"
    img.save(bio, "WEBP")
    bio.seek(0)

    keyboard = [
        [InlineKeyboardButton("🖼️ Figurinha Normal", callback_data="normal")],
        [InlineKeyboardButton("🎞️ Figurinha Animada", callback_data="animada")]
    ]
    await update.message.reply_sticker(sticker=InputFile(bio))
    await update.message.reply_text(
        "✅ Figurinha criada! Quer salvar em um pack?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "normal":
        await query.edit_message_text("🖼️ Figurinha normal gerada!")
    elif query.data == "animada":
        await query.edit_message_text("🎞️ Figurinha animada (vídeos curtos) em breve!")

# ===== Registrar handlers =====
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_media))
application.add_handler(CallbackQueryHandler(button_handler))

# ===== Webhook =====
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

if __name__ == "__main__":
    async def set_webhook():
        await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        print("🤖 Webhook registrado com sucesso!")

    asyncio.run(set_webhook())
    app.run(host="0.0.0.0", port=10000)
