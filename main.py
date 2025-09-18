import os
import requests
import json
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from threading import Lock

# CONFIGURAÇÃO
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Seu token do bot
BOT_NAME = os.environ.get("BOT_NAME", "Hansel")  # Nome do bot
CHAT_ID = os.environ.get("CHAT_ID")  # Para postagens automáticas
PORT = int(os.environ.get("PORT", 5000))

app = Flask(__name__)

# CACHE SIMPLES PARA MEMÓRIA SAUDÁVEL
cache = {"musicas": {}, "piadas": {}, "memes": {}, "quizzes": {}}
cache_lock = Lock()

def limpar_cache():
    with cache_lock:
        cache.clear()
        print(f"[{datetime.now()}] Cache limpo!")

scheduler = BackgroundScheduler()
scheduler.add_job(limpar_cache, 'interval', days=7)  # Limpa cache a cada semana
scheduler.start()

# FUNÇÃO PARA ENVIAR MENSAGENS
def send_telegram_message(chat_id, text, reply_id=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_id:
        data["reply_to_message_id"] = reply_id
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=data)

# FUNÇÃO PARA ENVIAR MÚSICA
def send_musica(chat_id, nome_musica):
    with cache_lock:
        if nome_musica in cache["musicas"]:
            musica_url = cache["musicas"][nome_musica]
        else:
            # Exemplo de API de música fictícia
            res = requests.get(f"https://api.musicas.com/buscar?nome={nome_musica}")
            if res.status_code != 200:
                send_telegram_message(chat_id, f"Não encontrei a música *{nome_musica}* 😢")
                return
            data = res.json()
            musica_url = data.get("url")
            cache["musicas"][nome_musica] = musica_url
    send_telegram_message(chat_id, f"🎵 *{nome_musica}* via *{BOT_NAME}*\n{musica_url}")

# FUNÇÃO PARA PEGAR PIADA
def send_piada(chat_id):
    with cache_lock:
        res = requests.get("https://api.piadas.com/random")
        if res.status_code != 200:
            send_telegram_message(chat_id, "Não consegui buscar uma piada 😢")
            return
        data = res.json()
        piada = data.get("texto", "Não achei nenhuma piada 😢")
        cache["piadas"][piada] = True
    send_telegram_message(chat_id, f"😂 {piada}")

# FUNÇÃO PARA PEGAR MEME
def send_meme(chat_id):
    with cache_lock:
        res = requests.get("https://api.memes.com/random")
        if res.status_code != 200:
            send_telegram_message(chat_id, "Não consegui buscar um meme 😢")
            return
        data = res.json()
        meme_url = data.get("url")
        cache["memes"][meme_url] = True
    send_telegram_message(chat_id, f"🤣 Meme do dia: {meme_url}")

# FUNÇÃO PARA QUIZ
def send_quiz(chat_id):
    res = requests.get("https://api.quiz.com/random")
    if res.status_code != 200:
        send_telegram_message(chat_id, "Não consegui buscar um quiz 😢")
        return
    data = res.json()
    pergunta = data.get("pergunta")
    opcoes = data.get("opcoes")  # lista de strings
    if not pergunta or not opcoes:
        return
    cache["quizzes"][pergunta] = opcoes
    texto = f"❓ *Quiz*: {pergunta}\n"
    for i, opc in enumerate(opcoes, 1):
        texto += f"{i}. {opc}\n"
    send_telegram_message(chat_id, texto)

# ROTA DO WEBHOOK
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json()
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "").strip()

        # COMANDOS
        if text.lower() == "/start":
            send_telegram_message(chat_id, f"Olá! Eu sou o *{BOT_NAME}* 🎉\nUse /musica para tocar músicas, ou diga o nome de uma música!")
        elif text.lower().startswith("/musica"):
            nome_musica = text[len("/musica"):].strip()
            if nome_musica:
                send_musica(chat_id, nome_musica)
            else:
                send_telegram_message(chat_id, "Por favor, envie o nome da música após o comando /musica")
        # PEDIR MÚSICA DIGITANDO NOME
        elif "musica" in text.lower():
            send_musica(chat_id, text)
        # PIADA
        elif "piada" in text.lower():
            send_piada(chat_id)
        # MEME
        elif "meme" in text.lower():
            send_meme(chat_id)
        # QUIZ
        elif "quiz" in text.lower():
            send_quiz(chat_id)

    return {"ok": True}

# POSTAGENS AUTOMÁTICAS
def postar_automaticamente():
    if CHAT_ID:
        send_piada(CHAT_ID)
        send_meme(CHAT_ID)
        send_quiz(CHAT_ID)

scheduler.add_job(postar_automaticamente, 'interval', hours=6)  # postagens a cada 6h

if __name__ == "__main__":
    print(f"{BOT_NAME} rodando com cache, música, piada, quiz, memes e postagens automáticas! 🎉")
    app.run(host="0.0.0.0", port=PORT)
