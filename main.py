import os
import io
import random
import json
import requests
from flask import Flask, request, jsonify, send_file
from datetime import datetime, timedelta
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
conversations = {}  # histórico de usuários
group_ids = set()
group_languages = {}  # idioma do grupo
cache = {"musicas": {}, "piadas": {}, "fatos": {}, "memes": {}, "quizzes": {}}

scheduler = BackgroundScheduler()
scheduler.start()

# --- Funções de suporte ---
def get_user_time(user_id):
    tz_name = DEFAULT_TIMEZONE
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")

def auto_manage_history(user_id):
    history = conversations.get(user_id, [])
    if len(history) > HISTORY_LIMIT:
        conversations[user_id] = history[-HISTORY_LIMIT:]

# --- APIs de conteúdo ---
def get_joke():
    try:
        r = requests.get("https://api.chucknorris.io/jokes/random", timeout=5)
        return r.json().get("value", "😅 Não consegui pegar uma piada agora.")
    except:
        return "😅 Não consegui pegar uma piada agora."

def get_fact():
    try:
        r = requests.get("https://uselessfacts.jsph.pl/random.json?language=en", timeout=5)
        return r.json().get("text", "🤔 Não consegui achar um fato agora.")
    except:
        return "🤔 Não consegui achar um fato agora."

def get_quiz():
    try:
        r = requests.get("https://opentdb.com/api.php?amount=1&type=multiple", timeout=5)
        data = r.json()
        if data.get("results"):
            q = data["results"][0]
            question = q["question"]
            correct = q["correct_answer"]
            options = q["incorrect_answers"] + [correct]
            random.shuffle(options)
            return {"question": question, "options": options, "correct": correct}
    except:
        return None

def get_meme():
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=5)
        data = r.json()
        return data.get("url")
    except:
        return None

def get_music(query=None):
    # Exemplo: usa uma API ou banco de dados de MP3
    sample_music = {
        "forró": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "sertanejo": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
        "pop": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"
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

def send_telegram_poll(chat_id, question, options):
    payload = {
        "chat_id": chat_id,
        "question": question,
        "options": options,
        "is_anonymous": False
    }
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json=payload, timeout=5)
    except:
        pass

def send_telegram_audio(chat_id, url, title):
    payload = {"chat_id": chat_id, "audio": url, "caption": f"{title} - {BOT_NAME}"}
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendAudio", json=payload, timeout=5)
    except:
        send_telegram_message(chat_id, "Ops, não consegui tocar a música agora 😢")

# --- Postagens automáticas ---
def auto_post_content():
    for gid in group_ids:
        content_type = random.choice(["piada", "fato", "meme", "quiz"])
        if content_type == "piada":
            text = get_joke()
            send_telegram_message(gid, f"PIADA\n🤣 {text}")
        elif content_type == "fato":
            text = get_fact()
            send_telegram_message(gid, f"FATO CURIOSO\n📚 {text}")
        elif content_type == "meme":
            url = get_meme()
            if url:
                send_telegram_message(gid, f"MEME\n🖼️ {url}")
        elif content_type == "quiz":
            quiz = get_quiz()
            if quiz:
                send_telegram_poll(gid, quiz["question"], quiz["options"])

def auto_post_music():
    for gid in group_ids:
        url = get_music()
        send_telegram_audio(gid, url, f"Música para animar - {BOT_NAME}")

# Agendamento
scheduler.add_job(auto_post_content, "interval", hours=6)
scheduler.add_job(auto_post_music, "interval", hours=3)

# Limpar cache semanalmente
def clear_cache():
    for k in cache:
        cache[k] = {}
scheduler.add_job(clear_cache, "interval", days=7)

# --- Webhook ---
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    chat_type = message.get("chat", {}).get("type")

    if chat_type in ["group", "supergroup"]:
        group_ids.add(chat_id)
        if chat_id not in group_languages:
            lang_code = message.get("from", {}).get("language_code", "pt")
            group_languages[chat_id] = lang_code

    if message.get("from", {}).get("is_bot"):
        return jsonify({"ok": True})

    text = message.get("text", "").strip()
    if not text:
        return jsonify({"ok": True})

    should_reply = (
        chat_type == "private" or
        BOT_NAME.lower() in text.lower() or
        (BOT_USERNAME and BOT_USERNAME.lower() in text.lower())
    )

    if should_reply:
        reply_to = message.get("message_id")
        if text.lower().startswith("/piada"):
            send_telegram_message(chat_id, f"PIADA\n🤣 {get_joke()}", reply_to)
        elif text.lower().startswith("/fato"):
            send_telegram_message(chat_id, f"FATO CURIOSO\n📚 {get_fact()}", reply_to)
        elif text.lower().startswith("/quiz"):
            quiz = get_quiz()
            if quiz:
                send_telegram_poll(chat_id, quiz["question"], quiz["options"])
        elif text.lower().startswith("/musica") or True:
            url = get_music(text.replace("/musica", "").strip())
            send_telegram_audio(chat_id, url, f"{text or 'Música aleatória'} - {BOT_NAME}")

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

# --- Main ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
