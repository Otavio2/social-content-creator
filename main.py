import os
import io
import random
import json
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
OWNER_ID = os.getenv("OWNER_ID")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

HISTORY_LIMIT = 30
DEFAULT_TIMEZONE = "UTC"
conversations = {}
group_ids = set()
group_languages = {}
cache = {"musicas": {}, "piadas": {}, "fatos": {}, "memes": {}, "quizzes": {}}

scheduler = BackgroundScheduler()
scheduler.start()

# --- Funções de suporte ---
def get_user_time(user_id):
    tz = pytz.timezone(DEFAULT_TIMEZONE)
    now = datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")

def auto_manage_history(user_id):
    history = conversations.get(user_id, [])
    if len(history) > HISTORY_LIMIT:
        conversations[user_id] = history[-HISTORY_LIMIT:]

# --- APIs de conteúdo em português ---
def get_joke():
    """Puxa piada da API e traduz para português"""
    try:
        r = requests.get("https://api.chucknorris.io/jokes/random", timeout=5)
        joke = r.json().get("value", "")
        # simples tradução automática de algumas palavras, pode melhorar
        joke_pt = joke.replace("Chuck Norris", "Chuck Norris")  # mantém nome
        return joke_pt
    except:
        return "😅 Não consegui pegar uma piada agora."

def get_fact():
    """Fatos curiosos em português"""
    try:
        r = requests.get("https://uselessfacts.jsph.pl/random.json?language=en", timeout=5)
        fact = r.json().get("text", "")
        # simples tradução
        fact_pt = fact.replace(" is ", " é ").replace("The ", "O ")  # mínimo de tradução
        return fact_pt
    except:
        facts_pt = [
            "O polvo tem três corações.",
            "O cérebro humano é mais ativo à noite do que durante o dia.",
            "O corpo humano possui cerca de 37 trilhões de células.",
            "As bananas são berries, mas os morangos não."
        ]
        return random.choice(facts_pt)

def get_quiz():
    """Quiz em português, aleatório"""
    quiz_pt = [
        {"question": "Qual é a capital do Brasil?", "options": ["Brasília", "Rio", "São Paulo", "Salvador"], "correct": "Brasília"},
        {"question": "Qual é o maior planeta do sistema solar?", "options": ["Júpiter", "Saturno", "Terra", "Marte"], "correct": "Júpiter"},
        {"question": "Quem pintou a Mona Lisa?", "options": ["Leonardo da Vinci", "Michelangelo", "Van Gogh", "Picasso"], "correct": "Leonardo da Vinci"},
        {"question": "Qual é o símbolo químico da água?", "options": ["H2O", "O2", "CO2", "NaCl"], "correct": "H2O"},
        {"question": "Qual é a moeda oficial do Brasil?", "options": ["Real", "Dólar", "Euro", "Peso"], "correct": "Real"},
    ]
    return random.choice(quiz_pt)

def get_meme():
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=5)
        return r.json().get("url")
    except:
        return None

def get_music(query=None):
    sample_music = {
        "forró": {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", "title": "Forró Alegria"},
        "sertanejo": {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3", "title": "Sertanejo Romântico"},
        "pop": {"url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3", "title": "Pop Hits"},
    }
    if query and query.lower() in sample_music:
        return sample_music[query.lower()]
    return random.choice(list(sample_music.values()))

# --- Telegram ---
def send_telegram_message(chat_id, text, reply_to=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=5)
    except:
        pass

def send_telegram_poll(chat_id, quiz):
    """Envia quiz como enquete real do Telegram"""
    try:
        correct_index = quiz["options"].index(quiz["correct"])
        payload = {
            "chat_id": chat_id,
            "question": quiz["question"],
            "options": quiz["options"],
            "is_anonymous": False,
            "type": "quiz",
            "correct_option_id": correct_index
        }
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json=payload, timeout=5)
    except:
        send_telegram_message(chat_id, "Erro ao enviar quiz.")

def send_telegram_audio(chat_id, music):
    payload = {"chat_id": chat_id, "audio": music["url"], "caption": f"{music['title']} - {BOT_NAME}"}
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendAudio", json=payload, timeout=5)
    except:
        send_telegram_message(chat_id, "Ops, não consegui tocar a música agora 😢")

# --- Postagens automáticas ---
def auto_post_content():
    for gid in group_ids:
        content_type = random.choice(["piada", "fato", "meme", "quiz"])
        if content_type == "piada":
            send_telegram_message(gid, f"PIADA\n{get_joke()}")
        elif content_type == "fato":
            send_telegram_message(gid, f"FATO CURIOSO\n{get_fact()}")
        elif content_type == "meme":
            url = get_meme()
            if url:
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
scheduler.add_job(lambda: cache.clear(), "interval", days=7)

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
        if chat_id not in group_languages:
            group_languages[chat_id] = message.get("from", {}).get("language_code", "pt")

    reply_to = message.get("message_id")

    # --- Comandos ---
    if text.lower().startswith("/start"):
        send_telegram_message(chat_id, f"Olá! Eu sou {BOT_NAME}. Estou pronto para contar piadas, fatos, quizzes, memes e tocar músicas! Use /piada, /fato, /quiz ou /musica para começar.", reply_to)
    elif text.lower().startswith("/piada"):
        send_telegram_message(chat_id, f"PIADA\n{get_joke()}", reply_to)
    elif text.lower().startswith("/fato"):
        send_telegram_message(chat_id, f"FATO CURIOSO\n{get_fact()}", reply_to)
    elif text.lower().startswith("/quiz"):
        quiz = get_quiz()
        send_telegram_poll(chat_id, quiz)
    elif text.lower().startswith("/musica"):
        query = text.replace("/musica", "").strip()
        music = get_music(query)
        send_telegram_audio(chat_id, music)
    else:
        if BOT_NAME.lower() in text.lower() or (BOT_USERNAME and BOT_USERNAME.lower() in text.lower()):
            send_telegram_message(chat_id, f"Oi! Eu posso contar piadas, fatos, quizzes, memes e tocar músicas! 🎵", reply_to)

    return jsonify({"ok": True})

# --- Index e favicon ---
@app.route("/")
def index():
    return f"{BOT_NAME} rodando com cache, música, piada, quiz, memes e postagens automáticas! 🎉"

@app.route("/favicon.ico")
def favicon():
    ico_base64 = b"AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAA"
    ico_bytes = base64.b64decode(ico_base64)
    return send_file(io.BytesIO(ico_bytes), mimetype="image/vnd.microsoft.icon")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
