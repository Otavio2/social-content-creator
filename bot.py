import os
import io
import subprocess
from flask import Flask, request
from telegram import Update, Chat, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import asyncio

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = "@MeuBot"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Packs fixos
STICKER_SET_NAME_STATIC = "MeuBotStatic_by_MeuBot"
STICKER_SET_TITLE_STATIC = "Figurinhas Normais do MeuBot"
STICKER_SET_NAME_ANIMATED = "MeuBotAnimated_by_MeuBot"
STICKER_SET_TITLE_ANIMATED = "Figurinhas Animadas doMeuBot"

app = Flask(__name__)
bot = Bot(BOT_TOKEN)
application = Application.builder().token(BOT_TOKEN).build()

user_files = {}  # armazena arquivos temporariamente

# -----------------------------
# Função para processar figurinha
# -----------------------------
async def process_sticker(user_id, is_animated, context: ContextTypes.DEFAULT_TYPE):
    if user_id not in user_files:
        return

    file_bytes = user_files[user_id]
    del user_files[user_id]

    if is_animated:
        temp_input = f"/tmp/{user_id}.mp4"
        temp_output = f"/tmp/{user_id}.webm"
        with open(temp_input, "wb") as f:
            f.write(file_bytes.getbuffer())

        subprocess.run([
            "ffmpeg", "-i", temp_input,
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease",
            "-an", "-c:v", "libvpx-vp9", "-b:v", "500K", temp_output
        ], check=True)

        with open(temp_output, "rb") as sticker_file:
            try:
                await context.bot.add_sticker_to_set(user_id=user_id,
                                                     name=STICKER_SET_NAME_ANIMATED,
                                                     webm_sticker=sticker_file, emojis="🔥")
            except:
                sticker_file.seek(0)
                await context.bot.create_new_sticker_set(user_id=user_id,
                                                         name=STICKER_SET_NAME_ANIMATED,
                                                         title=STICKER_SET_TITLE_ANIMATED,
                                                         stickers=[{"webm_sticker": sticker_file, "emoji": "🔥"}])
            with open(temp_output, "rb") as sfile:
                await context.bot.send_sticker(chat_id=user_id, sticker=sfile)

    else:
        img = Image.open(file_bytes).convert("RGBA")
        img.thumbnail((512, 512), Image.Resampling.LANCZOS)

        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        text_w, text_h = draw.textsize(BOT_USERNAME, font=font)
        draw.text((img.width - text_w - 10, img.height - text_h - 10), BOT_USERNAME, fill="white", font=font)

        bio = io.BytesIO()
        bio.name = "sticker.webp"
        img.save(bio, "WEBP")
        bio.seek(0)

        try:
            await context.bot.add_sticker_to_set(user_id=user_id,
                                                 name=STICKER_SET_NAME_STATIC,
                                                 png_sticker=bio, emojis="😀")
        except:
            bio.seek(0)
            await context.bot.create_new_sticker_set(user_id=user_id,
                                                     name=STICKER_SET_NAME_STATIC,
                                                     title=STICKER_SET_TITLE_STATIC,
                                                     stickers=[{"png_sticker": bio, "emoji": "😀"}])
        bio.seek(0)
        await context.bot.send_sticker(chat_id=user_id, sticker=bio)

# -----------------------------
# Mensagem recebida
# -----------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat.type != Chat.PRIVATE:
        return

    user_id = update.effective_user.id

    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        bio = io.BytesIO()
        await file.download_to_memory(out=bio)
        bio.seek(0)
        user_files[user_id] = bio
    elif update.message.video or update.message.animation:
        file = await (update.message.video or update.message.animation).get_file()
        bio = io.BytesIO()
        await file.download_to_memory(out=bio)
        bio.seek(0)
        user_files[user_id] = bio
    else:
        await update.message.reply_text("📌 Envie uma imagem, GIF ou vídeo curto para criar figurinha.")
        return

    keyboard = [[InlineKeyboardButton("Figurinha Normal", callback_data="normal"),
                 InlineKeyboardButton("Figurinha Animada", callback_data="animated")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Escolha o tipo de figurinha:", reply_markup=reply_markup)

# -----------------------------
# Botão clicado
# -----------------------------
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "normal":
        await process_sticker(user_id, is_animated=False, context=context)
    elif query.data == "animated":
        await process_sticker(user_id, is_animated=True, context=context)

# -----------------------------
# Webhook Flask
# -----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    asyncio.run(application.update_queue.put(update))
    return "OK", 200

# -----------------------------
# Inicialização
# -----------------------------
application.add_handler(MessageHandler(filters.ALL, handle_message))
application.add_handler(CallbackQueryHandler(handle_button))

if __name__ == "__main__":
    asyncio.run(bot.set_webhook(WEBHOOK_URL))
    print("🤖 Bot rodando no modo webhook com botões!")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
