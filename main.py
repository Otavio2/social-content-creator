import os
import io
import random
import requests
from flask import Flask, request, jsonify, send_file
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import base64

app = Flask(__name__)

# --- Configurações ---
BOT_NAME = os.getenv("BOT_NAME", "Hansel")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@Group_klbBot")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

HISTORY_LIMIT = 30
DEFAULT_TIMEZONE = "UTC"
conversations = {}
group_ids = set()
group_languages = {}
cache = {"musicas": {}, "piadas": {}, "fatos": {}, "memes": {}, "quizzes": {}}

scheduler = BackgroundScheduler()
scheduler.start()

# --- Envio para Telegram ---
def send_telegram_message(chat_id, text, reply_to=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=5)
    except Exception as e:
        print("Erro sendMessage:", e)

def send_telegram_poll(chat_id, quiz):
    try:
        correct_index = quiz["options"].index(quiz["correct"])
    except ValueError:
        correct_index = 0
    payload = {
        "chat_id": chat_id,
        "question": quiz["question"],
        "options": quiz["options"],
        "is_anonymous": False,
        "type": "quiz",
        "correct_option_id": correct_index
    }
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json=payload, timeout=5)
    except Exception as e:
        print("Erro sendPoll:", e)

def send_telegram_audio(chat_id, music):
    if not music or not music.get("url"):
        send_telegram_message(chat_id, "Não encontrei música com esse nome 😢")
        return
    payload = {
        "chat_id": chat_id,
        "audio": music["url"],
        "caption": music.get("title", BOT_NAME)
    }
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendAudio", data=payload, timeout=5)
    except Exception as e:
        print("Erro sendAudio:", e)
        send_telegram_message(chat_id, "Ops, não consegui tocar a música agora 😢")

# --- Conteúdos ---
def get_joke():
    try:
        r = requests.get("https://us-central1-kivson.cloudfunctions.net/charada-aleatoria", timeout=5)
        if r.status_code == 200:
            js = r.json()
            pergunta = js.get("pergunta")
            resposta = js.get("resposta")
            if pergunta and resposta:
                return f"{pergunta}?\n👉 {resposta}"
    except:
        pass
    fallback = [
        "O que é o que é: quanto mais você tira, maior fica? 👉 Buraco.",
        "Por que o livro de matemática estava triste? 👉 Porque tinha muitos problemas.",
        "O que o zero disse para o oito? 👉 Belo cinto!"
    ]
    return random.choice(fallback)

def get_fact():
    try:
        r = requests.get("https://meowfacts.herokuapp.com/", timeout=5)  # curiosidades de gatos
        if r.status_code == 200:
            js = r.json()
            fact = js.get("data")
            if fact:
                return fact[0]
    except:
        pass
    fatos = [
        "🐢 As tartarugas podem viver mais de 150 anos.",
        "🌌 O espaço não tem som porque não há ar para propagar ondas sonoras.",
        "🔥 O Sol é 109 vezes maior que a Terra.",
        "🦋 As borboletas sentem o gosto com os pés."
    ]
    return random.choice(fatos)

def get_meme():
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=5)
        if r.status_code == 200:
            js = r.json()
            return js.get("url")
    except:
        pass
    return "https://i.imgur.com/4M7IWwP.jpeg"  # fallback

def get_quiz():
    quiz_pt = [
        {"question": "Qual é a capital do Brasil?", "options": ["Brasília", "Rio de Janeiro", "São Paulo", "Salvador"], "correct": "Brasília"},
        {"question": "Qual é o maior planeta do sistema solar?", "options": ["Júpiter", "Saturno", "Terra", "Marte"], "correct": "Júpiter"},
        {"question": "Quem pintou a Mona Lisa?", "options": ["Leonardo da Vinci", "Michelangelo", "Van Gogh", "Picasso"], "correct": "Leonardo da Vinci"},
        {"question": "Qual elemento químico tem símbolo O?", "options": ["Oxigênio", "Ouro", "Ósmio", "Óxon"], "correct": "Oxigênio"},
        {"question": "Qual país é conhecido como Terra do Sol Nascente?", "options": ["Japão", "China", "Índia", "Tailândia"], "correct": "Japão"},
    ]
    return random.choice(quiz_pt)

def get_message():
    mensagens = [
        "💡 Nunca desista dos seus sonhos!",
        "🚀 Um passo de cada vez te leva longe.",
        "🌟 Você é capaz de coisas incríveis!",
        "🔥 Acredite em você e faça acontecer.",
        "🎯 Hoje é um novo dia para realizar algo grande."
    ]
    return random.choice(mensagens)

def get_music(query=None):
    try:
        if not query:
            query = "pop"
        q = requests.utils.quote(query)
        url = f"https://itunes.apple.com/search?term={q}&media=music&limit=1&country=BR"
        r = requests.get(url, timeout=5).json()
        results = r.get("results", [])
        if results:
            track = results[0]
            return {
                "title": f"{track.get('trackName')} - {track.get('artistName')}",
                "url": track.get("previewUrl")
            }
    except:
        pass
    # fallback
    sample_music = [
        {"title": "Música Aleatória 1", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"},
        {"title": "Música Aleatória 2", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"},
        {"title": "Música Aleatória 3", "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"},
    ]
    return random.choice(sample_music)

# --- Postagens automáticas ---
def auto_post_content():
    for gid in group_ids:
        content_type = random.choice(["piada", "fato", "meme", "quiz"])
        if content_type == "piada":
            send_telegram_message(gid, f"🤣 PIADA\n{get_joke()}")
        elif content_type == "fato":
            send_telegram_message(gid, f"📚 FATO CURIOSO\n{get_fact()}")
        elif content_type == "meme":
            url = get_meme()
            send_telegram_message(gid, f"MEME\n{url}")
        elif content_type == "quiz":
            quiz = get_quiz()
            send_telegram_poll(gid, quiz)

def auto_post_music():
    for gid in group_ids:
        music = get_music()
        send_telegram_audio(gid, music)

scheduler.add_job(auto_post_content, "interval", hours=6)
scheduler.add_job(auto_post_music, "interval", hours=3)

# --- Webhook ---
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    chat_type = message.get("chat", {}).get("type")
    text = message.get("text", "").strip()

    if not text or message.get("from", {}).get("is_bot"):
        return jsonify({"ok": True})

    if chat_type in ["group", "supergroup"]:
        group_ids.add(chat_id)

    reply_to = message.get("message_id")

    if text.lower().startswith("/start"):
        send_telegram_message(chat_id, f"Olá! Eu sou {BOT_NAME}. 🤖\n\nUse:\n/piada\n/fato\n/quiz\n/musica <nome>\n/mensagem\n/meme", reply_to)
    elif text.lower().startswith("/piada"):
        send_telegram_message(chat_id, f"🤣 PIADA\n{get_joke()}", reply_to)
    elif text.lower().startswith("/fato"):
        send_telegram_message(chat_id, f"📚 FATO CURIOSO\n{get_fact()}", reply_to)
    elif text.lower().startswith("/quiz"):
        quiz = get_quiz()
        send_telegram_poll(chat_id, quiz)
    elif text.lower().startswith("/musica"):
        query = text.replace("/musica", "").strip()
        music = get_music(query)
        send_telegram_audio(chat_id, music)
    elif text.lower().startswith("/mensagem"):
        send_telegram_message(chat_id, get_message(), reply_to)
    elif text.lower().startswith("/meme"):
        url = get_meme()
        send_telegram_message(chat_id, f"MEME\n{url}")
    else:
        if BOT_NAME.lower() in text.lower() or (BOT_USERNAME and BOT_USERNAME.lower() in text.lower()):
            send_telegram_message(chat_id, f"Oi! Eu posso ajudar com /piada, /fato, /quiz, /musica, /mensagem e /meme 😉", reply_to)

    return jsonify({"ok": True})

@app.route("/")
def index():
    return f"{BOT_NAME} rodando com piadas, fatos, memes, quizzes, músicas e mensagens motivacionais! 🎉"

@app.route("/favicon.ico")
def favicon():
    ico_base64 = b"AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAA"
    ico_bytes = base64.b64decode(ico_base64)
    return send_file(io.BytesIO(ico_bytes), mimetype="image/vnd.microsoft.icon")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
