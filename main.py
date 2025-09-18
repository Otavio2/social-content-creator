import os
import json
import random
import requests
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

# ================= Configurações =================
TOKEN = os.environ.get("TELEGRAM_TOKEN")  # Coloque seu token do bot
BOT_NOME = os.environ.get("BOT_NOME", "Hansel")
CHAT_ID = os.environ.get("CHAT_ID")  # Coloque seu chat/grupo ID

app = Flask(__name__)

# Cache em memória
cache = {
    "musicas": [],
    "piadas": [],
    "quizzes": [],
    "memes": []
}

# ================= Funções básicas =================
def send_telegram_message(chat_id, texto, reply_to_message_id=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML"
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    requests.post(url, data=payload)

def limpar_cache():
    global cache
    cache = {"musicas": [], "piadas": [], "quizzes": [], "memes": []}
    print(f"[{datetime.now()}] Cache limpo com sucesso!")

# ================= Funções de conteúdo =================
def pegar_musica(nome_musica=None):
    # Exemplo genérico de música
    musicas_exemplo = [
        {"nome": "Forró do Amor", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"},
        {"nome": "Samba da Alegria", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"},
        {"nome": "Axé Animado", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"}
    ]
    if nome_musica:
        # Procurar por nome
        for m in musicas_exemplo:
            if nome_musica.lower() in m["nome"].lower():
                return m
        return None
    return random.choice(musicas_exemplo)

def pegar_piada():
    piadas = [
        "Por que o computador foi ao médico? Porque estava com vírus!",
        "O que é um pontinho vermelho no céu? Uma pimenta voadora!",
        "Por que a bicicleta não conseguiu levantar? Porque estava cansada!"
    ]
    return random.choice(piadas)

def pegar_meme():
    memes = [
        "https://i.imgflip.com/4/30b1gx.jpg",
        "https://i.imgflip.com/1bij.jpg",
        "https://i.imgflip.com/26am.jpg"
    ]
    return random.choice(memes)

def pegar_quiz():
    quizzes = [
        {
            "pergunta": "Qual é a capital do Brasil?",
            "opcoes": ["São Paulo", "Brasília", "Rio de Janeiro", "Salvador"],
            "resposta": "Brasília"
        },
        {
            "pergunta": "Qual é o maior planeta do sistema solar?",
            "opcoes": ["Terra", "Júpiter", "Saturno", "Marte"],
            "resposta": "Júpiter"
        }
    ]
    return random.choice(quizzes)

# ================= Postagens automáticas =================
scheduler = BackgroundScheduler()

def postar_musica():
    musica = pegar_musica()
    texto = f"🎵 Música: {musica['nome']} - enviada por {BOT_NOME}\n{musica['url']}"
    send_telegram_message(CHAT_ID, texto)

def postar_piada():
    piada = pegar_piada()
    send_telegram_message(CHAT_ID, f"😂 Piada do dia: {piada}")

def postar_meme():
    meme = pegar_meme()
    send_telegram_message(CHAT_ID, f"😆 Meme do dia: {meme}")

def postar_quiz():
    quiz = pegar_quiz()
    opcoes = "\n".join([f"{i+1}. {o}" for i, o in enumerate(quiz["opcoes"])])
    texto = f"📝 Quiz: {quiz['pergunta']}\n{opcoes}\nResponda digitando o número da opção!"
    send_telegram_message(CHAT_ID, texto)

# Agendamento
scheduler.add_job(postar_musica, 'interval', hours=3)
scheduler.add_job(postar_piada, 'interval', hours=6)
scheduler.add_job(postar_meme, 'interval', hours=6)
scheduler.add_job(postar_quiz, 'interval', hours=8)
scheduler.add_job(limpar_cache, 'interval', days=7)
scheduler.start()

# ================= Webhook =================
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        mensagem = data["message"]
        chat_id = mensagem["chat"]["id"]
        texto = mensagem.get("text", "").strip()

        # Comandos
        if texto.lower() == "/start":
            send_telegram_message(chat_id, f"Olá! Eu sou {BOT_NOME}. Use /musica para ouvir músicas, /piada para piadas, /quiz para quizzes e /meme para memes!")
        elif texto.lower().startswith("/musica"):
            nome = texto[7:].strip()
            m = pegar_musica(nome if nome else None)
            if m:
                send_telegram_message(chat_id, f"🎵 Música: {m['nome']} - enviada por {BOT_NOME}\n{m['url']}")
            else:
                send_telegram_message(chat_id, "Desculpe, não encontrei essa música 😢")
        elif texto.lower() == "/piada":
            send_telegram_message(chat_id, f"😂 Piada: {pegar_piada()}")
        elif texto.lower() == "/meme":
            send_telegram_message(chat_id, f"😆 Meme: {pegar_meme()}")
        elif texto.lower() == "/quiz":
            quiz = pegar_quiz()
            opcoes = "\n".join([f"{i+1}. {o}" for i, o in enumerate(quiz["opcoes"])])
            send_telegram_message(chat_id, f"📝 Quiz: {quiz['pergunta']}\n{opcoes}\nResponda digitando o número da opção!")
        else:
            # Se escrever nome de música diretamente
            m = pegar_musica(texto)
            if m:
                send_telegram_message(chat_id, f"🎵 Música: {m['nome']} - enviada por {BOT_NOME}\n{m['url']}")

    return {"ok": True}

@app.route("/", methods=["GET"])
def index():
    return "Bot está online!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
