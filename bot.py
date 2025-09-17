import requests
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.background import BackgroundScheduler

TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"

# --- Buscar música no Audius ---
def buscar_audius(termo):
    url = f"https://discoveryprovider.audius.co/v1/tracks/search?query={termo}&app_name=botdemo"
    resp = requests.get(url).json()
    if "data" in resp and resp["data"]:
        track = resp["data"][0]
        return {
            "title": track["title"],
            "artist": track["user"]["name"],
            "stream_url": track["stream_url"] + "?app_name=botdemo"
        }
    return None

# --- Responder mensagens ---
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.lower()

    if "música" in msg or "manda" in msg or "toca" in msg or "quero" in msg:
        # Extrair possível termo de busca
        palavras = msg.split()
        generos = ["rock", "samba", "rap", "eletrônica", "lofi", "sertanejo"]
        termo = None
        for g in generos:
            if g in palavras:
                termo = g
                break

        if termo:
            musica = buscar_audius(termo)
            if musica:
                audio_data = requests.get(musica["stream_url"], stream=True)
                filename = f"{musica['title']}.mp3"
                with open(filename, "wb") as f:
                    for chunk in audio_data.iter_content(1024):
                        f.write(chunk)

                await update.message.reply_audio(
                    audio=open(filename, "rb"),
                    title=musica["title"],
                    performer=musica["artist"],
                    caption=f"🎶 {musica['title']}\n𐎓⃝ ĦΔŇŞ€Ł 𐎓⃝𓃦𝆺𝅥"
                )
            else:
                await update.message.reply_text("Não encontrei essa música 😢. Quer tentar outro gênero?")
        else:
            await update.message.reply_text("Qual música você quer?")

# --- Postagem automática ---
async def postar_periodico(app):
    termo = random.choice(["rock", "samba", "rap", "eletrônica", "lofi", "sertanejo"])
    musica = buscar_audius(termo)

    if musica:
        audio_data = requests.get(musica["stream_url"], stream=True)
        filename = f"{musica['title']}.mp3"
        with open(filename, "wb") as f:
            for chunk in audio_data.iter_content(1024):
                f.write(chunk)

        # ID do grupo alvo
        chat_id = -1001234567890  
        await app.bot.send_audio(
            chat_id=chat_id,
            audio=open(filename, "rb"),
            title=musica["title"],
            performer=musica["artist"],
            caption=f"🎶 {musica['title']}\n𐎓⃝ ĦΔŇŞ€Ł 𐎓⃝𓃦𝆺𝅥"
        )

# --- Main ---
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Responder mensagens normais (grupo e PV)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    # Agendar postagens
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: app.create_task(postar_periodico(app)), "interval", hours=6)
    scheduler.start()

    print("🤖 Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()
