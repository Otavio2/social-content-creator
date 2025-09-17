import os
import requests
import random
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler

# ======================================================
# CONFIGURAÇÕES
# ======================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TOKEN_AQUI")
BOT_USERNAME = "𐎓⃝ ĦΔŇŞ€Ł 𐎓⃝𓃦𝆺𝅥"

# ======================================================
# FUNÇÕES DE SUPORTE
# ======================================================

def send_telegram_message(chat_id, text, reply_to_message_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_to_message_id": reply_to_message_id,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload)

def send_telegram_audio(chat_id, musica, reply_to_message_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendAudio"

    # Baixa a música em MP3
    audio_data = requests.get(musica["stream_url"], stream=True)
    filename = f"{musica['title']}.mp3"
    with open(filename, "wb") as f:
        for chunk in audio_data.iter_content(1024):
            f.write(chunk)

    # Envia pro Telegram
    files = {"audio": open(filename, "rb")}
    data = {
        "chat_id": chat_id,
        "title": musica["title"],
        "performer": musica["artist"],
        "caption": f"🎶 {musica['title']}\n{BOT_USERNAME}",
        "reply_to_message_id": reply_to_message_id
    }
    requests.post(url, data=data, files=files)

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

# ======================================================
# FUNÇÃO DE IA (Groq ou outra)
# ======================================================

def groq_chat(user_id, prompt):
    """
    Função simulada de IA.
    Aqui você conecta seu modelo de IA real (Groq, OpenAI, etc).
    """
    # Simulação: responde com o gênero encontrado em prompt
    prompt = prompt.lower()
    if "forró" in prompt:
        return "Forró"
    if "rock" in prompt:
        return "Rock"
    if "samba" in prompt:
        return "Samba"
    if "rap" in prompt:
        return "Rap"
    if "eletrônica" in prompt:
        return "Eletrônica"
    if "lofi" in prompt:
        return "Lofi"
    if "sertanejo" in prompt:
        return "Sertanejo"
    return "Música"

# ======================================================
# PROCESSAMENTO DE MÚSICA
# ======================================================

def processar_musica(chat_id, user_msg, user_id, reply_to_message_id=None):
    try:
        # IA detecta o gênero
        prompt = (
            f"Responda apenas com o nome do gênero musical (exemplo: rock, forró, samba, jazz). "
            f"Mensagem do usuário: '{user_msg}'"
        )
        genero_detectado = groq_chat(user_id, prompt).strip()

        # Pega só a primeira palavra e remove emojis/símbolos
        genero_detectado = genero_detectado.split()[0].capitalize()

        if not genero_detectado:
            send_telegram_message(chat_id, "Não consegui identificar o gênero 😢", reply_to_message_id)
            return

        # Busca música no Audius
        musica = buscar_audius(genero_detectado)
        if musica:
            send_telegram_audio(chat_id, musica, reply_to_message_id)
        else:
            send_telegram_message(chat_id, f"Não encontrei música de {genero_detectado} 😢", reply_to_message_id)
    except Exception as e:
        print("Erro ao processar música:", e)
        send_telegram_message(chat_id, "Ops, não consegui tocar a música agora 😢", reply_to_message_id)

# ======================================================
# FLASK APP (WEBHOOK)
# ======================================================

app = Flask(__name__)

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json()
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        user_msg = message.get("text", "")
        reply_id = message.get("message_id")
        user_id = message["from"]["id"]

        if any(x in user_msg.lower() for x in ["música", "toca", "manda", "quero"]):
            processar_musica(chat_id, user_msg, user_id, reply_id)
        else:
            reply = groq_chat(user_id, user_msg)
            send_telegram_message(chat_id, reply, reply_id)

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot rodando com sucesso!"

# ======================================================
# POSTAGENS AUTOMÁTICAS
# ======================================================

def postar_periodico():
    termo = random.choice(["Rock", "Samba", "Rap", "Eletrônica", "Lofi", "Sertanejo", "Forró"])
    musica = buscar_audius(termo)

    if musica:
        chat_id = -1001234567890  # substitua pelo ID do grupo alvo
        send_telegram_audio(chat_id, musica)

# Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(postar_periodico, "interval", hours=6)
scheduler.start()

# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
