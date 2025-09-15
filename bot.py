import logging
import json
import os
import random
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from apscheduler.schedulers.background import BackgroundScheduler

# ===== CONFIGURAÇÃO =====
TOKEN = "SEU_TOKEN_AQUI"
WEBHOOK_URL = "https://SEU_DOMINIO.COM/{}".format(TOKEN)
ADMIN_LOG_CHAT_ID = -1001234567890
MAX_WARNINGS = 3
FLOOD_LIMIT = 5
PROIBIDO = ["palavrão1", "palavrão2"]
FILTROS = ["http://", "https://", "t.me/"]
MENSAGEM_BOAS_VINDAS = "👋 Bem-vindo {user}! Leia as regras e clique em aceitar."
MENSAGEM_REGRAS = "📜 Regras do grupo:\n1. Sem spam\n2. Sem links\n3. Respeite todos"
TEMPO_MUTE_FLOOD = 1
TEMPO_MUTE_FILTRO = 1
BACKUP_INTERVAL_MIN = 30

DATA_FILE = "users.json"
USUARIOS = {}
REPUTACAO = {}

STICKERS = [
    "CAACAgIAAxkBAAEBYzBfP1W6yZJ8q3fOtmq5yN71-4R8CwACXAADwZxgDk3yP4X3AxxXiHgQ",
]

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== FLASK APP =====
app = Flask(__name__)
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

# ===== FUNÇÕES DE ARQUIVO =====
def load_data():
    global USUARIOS, REPUTACAO
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            USUARIOS = data.get("users", {})
            REPUTACAO = data.get("reputation", {})
    else:
        USUARIOS = {}
        REPUTACAO = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"users":USUARIOS,"reputation":REPUTACAO}, f, indent=2, ensure_ascii=False)

def backup():
    save_data()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_users_{timestamp}.json"
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump({"users":USUARIOS,"reputation":REPUTACAO}, f, indent=2, ensure_ascii=False)
    logger.info(f"Backup salvo em {backup_file}")

# ===== COMANDOS =====
def start(update: Update, context):
    update.message.reply_text("🤖 Bot admin ativo!")

def regras(update: Update, context):
    update.message.reply_text(MENSAGEM_REGRAS)

def boas_vindas(update: Update, context):
    for user in update.message.new_chat_members:
        msg = MENSAGEM_BOAS_VINDAS.format(user=user.mention_html())
        keyboard = [[InlineKeyboardButton("✅ Aceitar regras", callback_data=f"aceitar_{user.id}")]]
        update.message.reply_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        update.effective_chat.restrict_member(user.id, ChatPermissions(can_send_messages=False))

def aceitar_regras(update: Update, context):
    query = update.callback_query
    user_id = int(query.data.split("_")[1])
    bot.restrict_chat_member(query.message.chat.id, user_id, ChatPermissions(can_send_messages=True, can_send_media_messages=True))
    query.answer("Regras aceitas ✅")

def ban(update: Update, context):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        update.effective_chat.ban_member(user.id)
        update.message.reply_text(f"🚫 {user.mention_html()} banido!", parse_mode="HTML")

def kick(update: Update, context):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        update.effective_chat.ban_member(user.id)
        update.effective_chat.unban_member(user.id)
        update.message.reply_text(f"👢 {user.mention_html()} expulso!", parse_mode="HTML")

def mute(update: Update, context):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        until = datetime.now() + timedelta(minutes=10)
        update.effective_chat.restrict_member(user.id, ChatPermissions(), until_date=until)
        update.message.reply_text(f"🔇 {user.mention_html()} silenciado!", parse_mode="HTML")

def unmute(update: Update, context):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        update.effective_chat.restrict_member(user.id, ChatPermissions(can_send_messages=True, can_send_media_messages=True))
        update.message.reply_text(f"🔊 {user.mention_html()} liberado!", parse_mode="HTML")

def warn(update: Update, context):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        uid = str(user.id)
        USUARIOS.setdefault(uid, {"warns":0,"msgs":[]})
        USUARIOS[uid]["warns"] += 1
        save_data()
        warns = USUARIOS[uid]["warns"]
        if warns >= MAX_WARNINGS:
            update.effective_chat.ban_member(user.id)
            update.message.reply_text(f"🚫 {user.mention_html()} banido (3/3 warns)!", parse_mode="HTML")
        else:
            update.message.reply_text(f"⚠️ {user.mention_html()} recebeu warn ({warns}/{MAX_WARNINGS}).", parse_mode="HTML")

def antiflood(update: Update, context):
    user = update.message.from_user
    uid = str(user.id)
    now = datetime.now()
    USUARIOS.setdefault(uid, {"warns":0,"msgs":[]})
    USUARIOS[uid]["msgs"] = [m for m in USUARIOS[uid]["msgs"] if (now - datetime.fromisoformat(m)).seconds < 10]
    USUARIOS[uid]["msgs"].append(now.isoformat())
    save_data()
    if len(USUARIOS[uid]["msgs"]) > FLOOD_LIMIT:
        update.effective_chat.restrict_member(user.id, ChatPermissions(can_send_messages=False), until_date=now+timedelta(minutes=TEMPO_MUTE_FLOOD))
        update.message.reply_text(f"🤐 {user.mention_html()} silenciado por flood!", parse_mode="HTML")

def filtro(update: Update, context):
    text = update.message.text.lower()
    if any(p in text for p in PROIBIDO) or any(f in text for f in FILTROS):
        update.message.delete()
        update.effective_chat.restrict_member(update.message.from_user.id, ChatPermissions(can_send_messages=False), until_date=datetime.now()+timedelta(minutes=TEMPO_MUTE_FILTRO))
        bot.send_message(ADMIN_LOG_CHAT_ID,f"🚨 Mensagem apagada de {update.message.from_user.mention_html()}",parse_mode="HTML")

def rep(update: Update, context):
    if not update.message.reply_to_message:
        update.message.reply_text("Responda a mensagem do usuário para dar reputação (+rep ou -rep).")
        return
    user = update.message.reply_to_message.from_user
    uid = str(user.id)
    REPUTACAO.setdefault(uid,0)
    if update.message.text.startswith("+rep"):
        REPUTACAO[uid] +=1
    elif update.message.text.startswith("-rep"):
        REPUTACAO[uid] -=1
    save_data()
    update.message.reply_text(f"{user.mention_html()} agora tem {REPUTACAO[uid]} pontos de reputação",parse_mode="HTML")

def ranking(update: Update, context):
    if not REPUTACAO:
        update.message.reply_text("Nenhum ponto de reputação registrado.")
        return
    rank = sorted(REPUTACAO.items(), key=lambda x:x[1], reverse=True)
    msg = "🏆 Ranking de reputação:\n"
    for i,(uid,pontos) in enumerate(rank[:10],1):
        msg+=f"{i}. [{uid}](tg://user?id={uid}) — {pontos} pts\n"
    update.message.reply_text(msg,parse_mode="Markdown")

def stats(update: Update, context):
    total_users = len(USUARIOS)
    total_warns = sum(u["warns"] for u in USUARIOS.values())
    update.message.reply_text(f"📊 Estatísticas:\nUsuários monitorados: {total_users}\nWarns totais: {total_warns}")

def sticker_dia(update: Update, context):
    if STICKERS:
        sticker = random.choice(STICKERS)
        update.message.reply_sticker(sticker)

# ===== VOTEBAN =====
VOTEBAN = {}

def voteban(update: Update, context):
    if not update.message.reply_to_message:
        update.message.reply_text("Responda a mensagem do usuário que deseja votar banir")
        return
    user = update.message.reply_to_message.from_user
    uid = str(user.id)
    chat_id = update.effective_chat.id
    VOTEBAN.setdefault(chat_id,{})
    VOTEBAN[chat_id].setdefault(uid,set())
    VOTEBAN[chat_id][uid].add(update.message.from_user.id)
    votos = len(VOTEBAN[chat_id][uid])
    if votos >=3:  # 3 votos = ban automático
        update.effective_chat.ban_member(user.id)
        update.message.reply_text(f"🚫 {user.mention_html()} banido por votação!",parse_mode="HTML")
        del VOT
        del VOTEBAN[chat_id][uid]
    else:
        update.message.reply_text(f"🗳️ Voto registrado ({votos}/3). Mais {3-votos} votos para banir.")

# ===== HANDLER WEBHOOK =====
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

# ===== CONFIGURAÇÃO HANDLERS =====
def main():
    load_data()

    # Comandos básicos
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("regras", regras))
    dispatcher.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, boas_vindas))
    dispatcher.add_handler(CallbackQueryHandler(aceitar_regras, pattern="^aceitar_"))

    # Admin
    dispatcher.add_handler(CommandHandler("ban", ban))
    dispatcher.add_handler(CommandHandler("kick", kick))
    dispatcher.add_handler(CommandHandler("mute", mute))
    dispatcher.add_handler(CommandHandler("unmute", unmute))
    dispatcher.add_handler(CommandHandler("warn", warn))

    # Anti-flood e filtro
    dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, antiflood))
    dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filtro))

    # Reputação e ranking
    dispatcher.add_handler(MessageHandler(filters.Regex(r"^\+rep$|^\-rep$"), rep))
    dispatcher.add_handler(CommandHandler("ranking", ranking))

    # Estatísticas e sticker
    dispatcher.add_handler(CommandHandler("stats", stats))
    dispatcher.add_handler(CommandHandler("sticker", sticker_dia))

    # Voteban
    dispatcher.add_handler(MessageHandler(filters.Regex(r"^/voteban$"), voteban))

    # Scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(backup, 'interval', minutes=BACKUP_INTERVAL_MIN)
    scheduler.start()

    # Define webhook
    bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook configurado em {WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    main()
