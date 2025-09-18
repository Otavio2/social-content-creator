import os
import requests
import random
import io
import base64
from flask import Flask, request, jsonify, send_file
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# --- Variáveis de ambiente ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")

# Configurações
BOT_NAME = "Hansel"
BOT_USERNAME = f"@{BOT_NAME}"
HISTORY_LIMIT = 30
DEFAULT_TIMEZONE = "UTC"

# --- Estruturas de dados ---
conversations = {}
user_timezones = {}
group_ids = set()
group_languages = {}  # idioma do grupo
cache = {"músicas": [], "memes": []}

# --- Funções de suporte ---
def get_user_time(user_id):
    tz_name = user_timezones.get(user_id, DEFAULT_TIMEZONE)
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")

def auto_manage_cache():
    for key in cache:
        if len(cache[key]) > 50:
            cache[key] = cache[key][-50:]

# --- Funções de API ---
def buscar_audius(termo):
    url = f"https://discoveryprovider.audius.co/v1/tracks/search?query={termo}&app_name=botdemo"
    try:
        resp = requests.get(url, timeout=10).json()
        if "data" in resp and resp["data"]:
            track = resp["data"][0]
            return {
                "title": track["title"],
                "artist": track["user"]["name"],
                "stream_url": track["stream_url"] + "?app_name=botdemo"
            }
    except:
        return None
    return None

def get_joke_api():
    try:
        r = requests.get("https://api.chucknorris.io/jokes/random", timeout=5)
        return r.json().get('value', '😅 Não consegui pegar uma piada agora.')
    except:
        return "😅 Não consegui pegar uma piada agora."

def get_fact_api():
    try:
        r = requests.get("https://uselessfacts.jsph.pl/random.json?language=pt", timeout=5)
        return r.json().get('text', '🤔 Não consegui achar um fato agora.')
    except:
        return "🤔 Não consegui achar um fato agora."

def get_quiz_api():
    try:
        r = requests.get("https://opentdb.com/api.php?amount=1&type=multiple&language=pt", timeout=5)
        data = r.json()
        if data.get("results"):
            q = data["results"][0]
            question = q["question"]
            correct = q["correct_answer"]
            options = q["incorrect_answers"] + [correct]
            random.shuffle(options)
            return {"question": question, "options": options, "answer": correct}
    except:
        return None

def get_meme_api():
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=5).json()
        return r.get("url")
    except:
        return None

# --- Função Telegram ---
def send_telegram_message(chat_id, text, reply_to_message_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def send_telegram_audio(chat_id, audio_url, title, performer):
    try:
        audio_data = requests.get(audio_url, stream=True, timeout=15)
        filename = f"{title}.mp3"
        with open(filename, "wb") as f:
            for chunk in audio_data.iter_content(1024):
                f.write(chunk)
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendAudio"
        payload = {
            "chat_id": chat_id,
            "title": title,
            "performer": performer,
            "caption": f"{title}\n🎵 {BOT_NAME} 🎵"
        }
        files = {"audio": open(filename, "rb")}
        requests.post(url, data=payload, files=files, timeout=15)
    except:
        send_telegram_message(chat_id, "Ops, não consegui tocar a música agora 😢")

def send_quiz_poll(chat_id, quiz):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll"
    payload = {
        "chat_id": chat_id,
        "question": quiz["question"],
        "options": quiz["options"],
        "is_anonymous": False
    }
    try:
        resp = requests.post(url, json=payload, timeout=5).json()
        if resp.get("ok"):
            poll_id = resp["result"]["message_id"]
            # Apaga poll após 2 minutos
            scheduler.add_job(
                lambda: requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage",
                    json={"chat_id": chat_id, "message_id": poll_id},
                    timeout=5
                ),
                "date",
                run_date=datetime.now(pytz.UTC) + timedelta(minutes=2)
            )
    except:
        pass

# --- Postagens automáticas ---
def auto_post_music():
    if not group_ids:
        return
    termo = random.choice(["rock", "samba", "rap", "eletrônica", "lofi", "sertanejo"])
    musica = buscar_audius(termo)
    if musica:
        for gid in group_ids:
            send_telegram_audio(gid, musica["stream_url"], musica["title"], musica["artist"])
    auto_manage_cache()

def auto_post_content():
    if not group_ids:
        return
    post_type = random.choice(["piada", "fato", "quiz", "meme"])
    for gid in group_ids:
        if post_type == "piada":
            send_telegram_message(gid, f"🤣 {get_joke_api()}")
        elif post_type == "fato":
            send_telegram_message(gid, f"📚 {get_fact_api()}")
        elif post_type == "quiz":
            quiz = get_quiz_api()
            if quiz:
                send_quiz_poll(gid, quiz)
        elif post_type == "meme":
            meme_url = get_meme_api()
            if meme_url:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                requests.post(url, json={"chat_id": gid, "photo": meme_url}, timeout=5)
    auto_manage_cache()

# --- Scheduler ---
scheduler = BackgroundScheduler()
scheduler.add_job(auto_post_music, "interval", hours=3)
scheduler.add_job(auto_post_content, "interval", hours=6)
scheduler.add_job(lambda: cache.clear(), "interval", days=7)  # limpa cache semanal
scheduler.start()

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

    if "text" in message:
        user_msg = message["text"].strip().lower()
        should_reply = False

        if chat_type == "private":
            should_reply = True
        elif BOT_NAME.lower() in user_msg or BOT_USERNAME.lower() in user_msg:
            should_reply = True

        if should_reply:
            if any(g in user_msg for g in ["música", "toca", "manda", "quero"]):
                termo = None
                generos = ["rock", "samba", "rap", "eletrônica", "lofi", "sertanejo"]
                for g in generos:
                    if g in user_msg:
                        termo = g
                        break
                if not termo:
                    termo = random.choice(generos)
                musica = buscar_audius(termo)
                if musica:
                    send_telegram_audio(chat_id, musica["stream_url"], musica["title"], musica["artist"])
                else:
                    send_telegram_message(chat_id, "Não encontrei música 😢")
            elif any(k in user_msg for k in ["piada", "fato", "quiz", "meme"]):
                if "piada" in user_msg:
                    send_telegram_message(chat_id, f"🤣 {get_joke_api()}")
                elif "fato" in user_msg:
                    send_telegram_message(chat_id, f"📚 {get_fact_api()}")
                elif "quiz" in user_msg:
                    quiz = get_quiz_api()
                    if quiz:
                        send_quiz_poll(chat_id, quiz)
                elif "meme" in user_msg:
                    meme_url = get_meme_api()
                    if meme_url:
                        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                        requests.post(url, json={"chat_id": chat_id, "photo": meme_url}, timeout=5)

    return jsonify({"ok": True})

# --- Index e favicon ---
@app.route("/")
def index():
    return f"{BOT_NAME} rodando com cache, música, piada, quiz, memes e postagens automáticas! 🎉"

@app.route("/favicon.ico")
def favicon():
    ico_base64 = b"""
    AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAA
    AAAAAAD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///
    wD///8A////AP///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    """
    ico_bytes = base64.b64decode(ico_base64)
    return send_file(io.BytesIO(ico_bytes), mimetype="image/vnd.microsoft.icon")

# --- Main ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
