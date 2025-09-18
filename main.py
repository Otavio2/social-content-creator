import os
import requests
import random
import io
import base64
import shutil
from flask import Flask, request, jsonify, send_file
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

# --- Flask app ---
app = Flask(__name__)

# --- Variáveis de ambiente ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_ID = os.getenv("OWNER_ID", "123456")  # fallback
BOT_NAME = os.getenv("BOT_NAME", "Hansel")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@Group_klbBot")

# --- Configurações fixas ---
HISTORY_LIMIT = 30
DEFAULT_TIMEZONE = "UTC"
conversations = {}
user_timezones = {}
group_ids = set()
group_languages = {}

# --- Cache ---
CACHE_DIR = "cache/musicas"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# --- Funções utilitárias ---
def detect_timezone(ip):
    try:
        r = requests.get(f"https://ipapi.co/{ip}/timezone/", timeout=5)
        if r.status_code == 200 and r.text.strip():
            return r.text.strip()
    except:
        pass
    return DEFAULT_TIMEZONE

def get_user_time(user_id):
    tz_name = user_timezones.get(user_id, DEFAULT_TIMEZONE)
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")

def cleanup_cache():
    """Limpa o cache semanalmente"""
    try:
        if os.path.exists(CACHE_DIR):
            shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR)
        print("🧹 Cache limpo!")
    except Exception as e:
        print("Erro limpando cache:", e)

# --- Enviar mensagens no Telegram ---
def send_telegram_message(chat_id, text, reply_to_message_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Erro Telegram:", e)

# --- MÚSICAS (Audius API) ---
def buscar_audius(termo):
    try:
        url = f"https://discoveryprovider.audius.co/v1/tracks/search?query={termo}&app_name=botdemo"
        resp = requests.get(url, timeout=10).json()
        if "data" in resp and resp["data"]:
            track = resp["data"][0]
            return {
                "title": track["title"],
                "artist": track["user"]["name"],
                "stream_url": track["stream_url"] + "?app_name=botdemo"
            }
    except Exception as e:
        print("Erro buscar Audius:", e)
    return None

def baixar_musica(musica):
    """Baixa ou usa cache"""
    filename = os.path.join(CACHE_DIR, f"{musica['title']}.mp3")
    if os.path.exists(filename):
        return filename

    try:
        audio_data = requests.get(musica["stream_url"], stream=True, timeout=15)
        with open(filename, "wb") as f:
            for chunk in audio_data.iter_content(1024):
                f.write(chunk)
        return filename
    except Exception as e:
        print("Erro baixando música:", e)
    return None

def send_music(chat_id, musica, reply_to_message_id=None):
    filename = baixar_musica(musica)
    if not filename:
        send_telegram_message(chat_id, "Ops, não consegui tocar a música agora 😢", reply_to_message_id)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendAudio"
    with open(filename, "rb") as audio:
        files = {"audio": audio}
        data = {
            "chat_id": chat_id,
            "title": musica["title"],
            "performer": musica["artist"],
            "caption": f"🎶 {musica['title']}\n𐎓⃝ {BOT_NAME} 𐎓⃝𓃦𝆺𝅥"
        }
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        try:
            requests.post(url, data=data, files=files, timeout=20)
        except Exception as e:
            print("Erro enviando música:", e)

# --- PIADAS ---
def get_joke_api():
    try:
        r = requests.get("https://api.chucknorris.io/jokes/random", timeout=5)
        return r.json().get('value', '😅 Não consegui pegar uma piada agora.')
    except:
        return "😅 Não consegui pegar uma piada agora."

# --- FATOS ---
def get_fact_api():
    try:
        r = requests.get("https://uselessfacts.jsph.pl/random.json?language=en", timeout=5)
        return r.json().get('text', '🤔 Não consegui achar um fato agora.')
    except:
        return "🤔 Não consegui achar um fato agora."

# --- QUIZ ---
def get_quiz_api():
    try:
        r = requests.get("https://opentdb.com/api.php?amount=1&type=multiple", timeout=5)
        data = r.json()
        if data.get("results"):
            q = data["results"][0]
            question = q["question"]
            correct = q["correct_answer"]
            options = q["incorrect_answers"] + [correct]
            random.shuffle(options)
            return question, correct, options
    except:
        return None, None, None
    return None, None, None

def send_quiz(chat_id):
    question, correct, options = get_quiz_api()
    if not question:
        send_telegram_message(chat_id, "🤔 Não consegui gerar um quiz agora.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll"
    payload = {
        "chat_id": chat_id,
        "question": question,
        "options": options,
        "is_anonymous": False,
        "type": "quiz",
        "correct_option_id": options.index(correct)
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Erro ao enviar quiz:", e)

# --- MEMES / IMAGENS ENGRAÇADAS ---
def get_meme_api():
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=5).json()
        return r.get("url", None)
    except:
        return None

def send_meme(chat_id):
    url = get_meme_api()
    if not url:
        send_telegram_message(chat_id, "😅 Não consegui achar uma imagem engraçada agora.")
        return
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": url, "caption": f"😂 Meme enviado por {BOT_NAME}"}
    try:
        requests.post(api_url, data=payload, timeout=10)
    except Exception as e:
        print("Erro enviando meme:", e)

# --- SCHEDULER ---
scheduler = BackgroundScheduler()
scheduler.start()

# --- Limpeza de cache semanal ---
scheduler.add_job(cleanup_cache, "interval", days=7)

# --- Postagens automáticas escalonadas ---
def auto_post_music():
    if not group_ids:
        return
    genero = random.choice(["rock", "samba", "rap", "eletrônica", "lofi", "sertanejo", "forró", "sertanejo universitário"])
    musica = buscar_audius(genero)
    if not musica:
        return
    for gid in group_ids:
        send_music(gid, musica)

def auto_post_joke():
    if not group_ids:
        return
    for gid in group_ids:
        post = get_joke_api()
        send_telegram_message(gid, f"🤣 {post}")

def auto_post_fact():
    if not group_ids:
        return
    for gid in group_ids:
        post = get_fact_api()
        send_telegram_message(gid, f"📚 {post}")

def auto_post_quiz():
    if not group_ids:
        return
    for gid in group_ids:
        send_quiz(gid)

def auto_post_meme():
    if not group_ids:
        return
    for gid in group_ids:
        send_meme(gid)

# --- Agendamento das postagens ---
# Músicas a cada 3h
scheduler.add_job(auto_post_music, "interval", hours=3)
# Piadas a cada 12h
scheduler.add_job(auto_post_joke, "interval", hours=12)
# Fatos a cada 12h (em horários alternados)
scheduler.add_job(auto_post_fact, "interval", hours=12, start_date=datetime.now() + timedelta(hours=1))
# Quiz diário
scheduler.add_job(auto_post_quiz, "interval", hours=24)
# Memes diários
scheduler.add_job(auto_post_meme, "interval", hours=24, start_date=datetime.now() + timedelta(hours=2))

# --- Função para processar pedidos de música no texto ---
def detectar_pedido_musica(texto):
    texto_lower = texto.lower()
    palavras_chave = ["toca", "manda", "quero ouvir", "play", "tocando"]
    if any(p in texto_lower for p in palavras_chave):
        # tenta extrair gênero ou nome da música
        generos = ["rock", "samba", "rap", "eletrônica", "lofi", "forró", "sertanejo", "sertanejo universitário"]
        for g in generos:
            if g in texto_lower:
                return g
        # se não encontrar gênero, usa a própria mensagem como termo de busca
        return texto
    return None

# --- Webhook Flask ---
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    message = data.get("message", {})
    if not message:
        return jsonify({"ok": True})

    chat_id = message.get("chat", {}).get("id")
    chat_type = message.get("chat", {}).get("type")
    user_msg = message.get("text", "").strip()
    from_bot = message.get("from", {}).get("is_bot", False)
    user_id = message.get("from", {}).get("id")

    if from_bot or not user_msg:
        return jsonify({"ok": True})

    # --- Registrar grupo e idioma ---
    if chat_type in ["group", "supergroup"]:
        group_ids.add(chat_id)
        if chat_id not in group_languages:
            lang_code = message.get("from", {}).get("language_code", "pt")
            group_languages[chat_id] = lang_code

    # --- Detectar se a mensagem é comando ---
    is_command = user_msg.startswith(("/", "!", "."))

    # --- Detectar menção ao bot ---
    mentioned = BOT_NAME.lower() in user_msg.lower() or (BOT_USERNAME and BOT_USERNAME.lower() in user_msg.lower())

    # --- Determinar se deve responder ---
    should_reply = is_command or mentioned or detectar_pedido_musica(user_msg)

    if not should_reply:
        return jsonify({"ok": True})

    # --- Processar comandos ---
    if user_msg.lower().startswith("/musica") or detectar_pedido_musica(user_msg) or mentioned:
        # Extrair termo
        termo = user_msg
        if user_msg.lower().startswith("/musica"):
            termo = user_msg[7:].strip()
        elif mentioned:
            # Remove menção
            termo = user_msg.replace(BOT_NAME, "").replace(BOT_USERNAME, "").strip()
        if not termo:
            termo = random.choice(["rock", "samba", "rap", "eletrônica", "lofi", "forró"])
        musica = buscar_audius(termo)
        if musica:
            send_music(chat_id, musica, reply_to_message_id=message.get("message_id"))
        else:
            send_telegram_message(chat_id, f"Não encontrei música de {termo} 😢", reply_to_message_id=message.get("message_id"))

    elif user_msg.lower().startswith("/piada"):
        post = get_joke_api()
        send_telegram_message(chat_id, f"🤣 {post}", reply_to_message_id=message.get("message_id"))

    elif user_msg.lower().startswith("/fato"):
        post = get_fact_api()
        send_telegram_message(chat_id, f"📚 {post}", reply_to_message_id=message.get("message_id"))

    elif user_msg.lower().startswith("/quiz"):
        send_quiz(chat_id)

    elif user_msg.lower().startswith("/meme"):
        send_meme(chat_id)

    # --- Apagar comando para não poluir ---
    if chat_type in ["group", "supergroup"] and is_command:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message.get("message_id")},
                timeout=5
            )
        except Exception as e:
            print("Erro deletando comando:", e)

    return jsonify({"ok": True})

# --- Rota de teste / index ---
@app.route("/")
def index():
    return f"{BOT_NAME} rodando com cache, música, piada, quiz, memes e postagens automáticas! 🎉"

# --- favicon simples ---
@app.route("/favicon.ico")
def favicon():
    ico_base64 = b"""
    AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAA
    AAAAAAD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///
    wD///8A////AP///wD///8A////AP///wD///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    """
    ico_bytes = base64.b64decode(ico_base64)
    return send_file(io.BytesIO(ico_bytes), mimetype="image/vnd.microsoft.icon")

# --- MAIN ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
