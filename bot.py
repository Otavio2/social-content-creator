import os
import subprocess
from flask import Flask, request
from telegram import Update, Bot, Chat
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from telegram.ext import Dispatcher
from PIL import Image, ImageDraw, ImageFont
import asyncio

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = "@MeuBot"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # URL do Render com /webhook

# Packs fixos
STICKER_SET_NAME_STATIC = "MeuBotStatic_by_MeuBot"
STICKER_SET_TITLE_STATIC = "Figurinhas Normais do MeuBot"
STICKER_SET_NAME_ANIMATED = "MeuBotAnimated_by_MeuBot"
STICKER_SET_TITLE_ANIMATED = "Figurinhas Animadas do MeuBot"

TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

bot = Bot(BOT_TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

async def create_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat.type != Chat.PRIVATE:
        return

    user = update.effective_user
    user_id = user.id

    # FIGURINHAS NORMAIS
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        filepath = os.path.join(TEMP_DIR, f"{user_id}.jpg")
        await file.download_to_drive(filepath)

        img = Image.open(filepath).convert("RGBA")
        img.thumbnail((512, 512), Image.Resampling.LANCZOS)

        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        text = f"{BOT_USERNAME}"
        text_w, text_h = draw.textsize(text, font=font)
        draw.text((img.width - text_w - 10, img.height - text_h - 10), text, fill="white", font=font)

        final_path = os.path.join(TEMP_DIR, f"sticker_{user_id}.webp")
        img.save(final_path, "WEBP")

        try:
            await bot.add_sticker_to_set(user_id=user_id, name=STICKER_SET_NAME_STATIC,
                                         png_sticker=open(final_path, "rb"), emojis="😀")
        except:
            try:
                await bot.create_new_sticker_set(user_id=user_id, name=STICKER_SET_NAME_STATIC,
                                                 title=STICKER_SET_TITLE_STATIC,
                                                 stickers=[{"png_sticker": open(final_path, "rb"), "emoji": "😀"}])
            except:
                pass

        await update.message.reply_sticker(sticker=open(final_path, "rb"))

    # FIGURINHAS ANIMADAS
    elif update.message.animation or update.message.video:
        file = await (update.message.animation or update.message.video).get_file()
        filepath = os.path.join(TEMP_DIR, f"{user_id}.mp4")
        await file.download_to_drive(filepath)

        final_path = os.path.join(TEMP_DIR, f"sticker_{user_id}.webm")

        subprocess.run([
            "ffmpeg", "-i", filepath,
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease",
            "-an", "-c:v", "libvpx-vp9", "-b:v", "500K", final_path
        ])

        try:
            await bot.add_sticker_to_set(user_id=user_id, name=STICKER_SET_NAME_ANIMATED,
                                         webm_sticker=open(final_path, "rb"), emojis="🔥")
        except:
            try:
                await bot.create_new_sticker_set(user_id=user_id, name=STICKER_SET_NAME_ANIMATED,
                                                 title=STICKER_SET_TITLE_ANIMATED,
                                                 stickers=[{"webm_sticker": open(final_path, "rb"), "emoji": "🔥"}])
            except:
                pass

        await update.message.reply_sticker(sticker=open(final_path, "rb"))

    else:
        await update.message.reply_text("📌 Envie uma imagem, GIF ou vídeo curto para criar figurinha.")

# =====================
# Flask endpoint para webhook
# =====================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    asyncio.run(dispatcher.process_update(update))
    return "OK", 200

# =====================
# Configuração inicial do webhook
# =====================
if __name__ == "__main__":
    asyncio.run(bot.set_webhook(WEBHOOK_URL))
    print("🤖 Bot rodando no modo webhook!")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
