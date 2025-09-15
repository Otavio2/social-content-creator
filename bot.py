import logging
import json
import os
import random
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
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
STICKERS = ["CAACAgIAAxkBAAEBYzBfP1W6yZJ8q3fOtmq5yN71-4R8CwACXAADwZxgDk3yP4X3AxxXiHgQ"]
VOTEBAN = {}

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        json.dump({"users": USUARIOS, "reputation": REPUTACAO}, f, indent=2, ensure_ascii=False)

def backup():
    save_data()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_users_{timestamp}.json"
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump({"users":USUARIOS,"reputation":REPUTACAO}, f, indent=2, ensure_ascii=False)
    logger.info(f"Backup salvo em {backup_file}")

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot ativo!")

async def regras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(MENSAGEM_REGRAS)

async def boas_vindas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        msg = MENSAGEM_BOAS_VINDAS.format(user=user.mention_html())
        keyboard = [[InlineKeyboardButton("✅ Aceitar regras", callback_data=f"aceitar_{user.id}")]]
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        await update.effective_chat.restrict_member(user.id, ChatPermissions(can_send_messages=False))

async def aceitar_regras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = int(query.data.split("_")[1])
    await query.bot.restrict_chat_member(query.message.chat.id, user_id, ChatPermissions(can_send_messages=True, can_send_media_messages=True))
    await query.answer("Regras aceitas ✅")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await update.effective_chat.ban_member(user.id)
        await update.message.reply_text(f"🚫 {user.mention_html()} banido!", parse_mode="HTML")

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await update.effective_chat.ban_member(user.id)
        await update.effective_chat.unban_member(user.id)
        await update.message.reply_text(f"👢 {user.mention_html()} expulso!", parse_mode="HTML")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        until = datetime.now() + timedelta(minutes=10)
        await update.effective_chat.restrict_member(user.id, ChatPermissions(), until_date=until)
        await update.message.reply_text(f"🔇 {user.mention_html()} silenciado!", parse_mode="HTML")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await update.effective_chat.restrict_member(user.id, ChatPermissions(can_send_messages=True, can_send_media_messages=True))
        await update.message.reply_text(f"🔊 {user.mention_html()} liberado!", parse_mode="HTML")

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        uid = str(user.id)
        USUARIOS.setdefault(uid, {"warns":0,"msgs":[]})
        USUARIOS[uid]["warns"] += 1
        save_data()
        warns = USUARIOS[uid]["warns"]
        if warns >= MAX_WARNINGS:
            await update.effective_chat.ban_member(user.id)
            await update.message.reply_text(f"🚫 {user.mention_html()} banido (3/3 warns)!", parse_mode="HTML")
        else:
            await update.message.reply_text(f"⚠️ {user.mention_html()} recebeu warn ({warns}/{MAX_WARNINGS}).", parse_mode="HTML")

async def antiflood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = str(user.id)
    now = datetime.now()
    USUARIOS.setdefault(uid, {"warns":0,"msgs":[]})
    USUARIOS[uid]["msgs"] = [m for m in USUARIOS[uid]["msgs"] if (now - datetime.fromisoformat(m)).seconds < 10]
    USUARIOS[uid]["msgs"].append(now.isoformat())
    save_data()
    if len(USUARIOS[uid]["msgs"]) > FLOOD_LIMIT:
        await update.effective_chat.restrict_member(user.id, ChatPermissions(can_send_messages=False), until_date=now+timedelta(minutes=TEMPO_MUTE_FLOOD))
        await update.message.reply_text(f"🤐 {user.mention_html()} silenciado por flood!", parse_mode="HTML")

async def filtro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if any(p in text for p in PROIBIDO) or any(f in text for f in FILTROS):
        await update.message.delete()
        await update.effective_chat.restrict_member(update.message.from_user.id, ChatPermissions(can_send_messages=False), until_date=datetime.now()+timedelta(minutes=TEMPO_MUTE_FILTRO))
        await context.bot.send_message(ADMIN_LOG_CHAT_ID,f"🚨 Mensagem apagada de {update.message.from_user.mention_html()}",parse_mode="HTML")

async def rep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Responda a mensagem do usuário para dar reputação (+rep ou -rep).")
        return
    user = update.message.reply_to_message.from_user
    uid = str(user.id)
    REPUTACAO.setdefault(uid,0)
    if update.message.text.startswith("+rep"):
        REPUTACAO[uid] +=1
    elif update.message.text.startswith("-rep"):
        REPUTACAO[uid] -=1
    save_data()
    await update.message.reply_text(f"{user.mention_html()} agora tem {REPUTACAO[uid]} pontos de reputação",parse_mode="HTML")

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not REPUTACAO:
        await update.message.reply_text("Nenhum ponto de reputação registrado.")
        return
    rank = sorted(REPUTACAO.items(), key=lambda x:x[1], reverse=True)
    msg = "🏆 Ranking de reputação:\n"
    for i,(uid,pontos) in enumerate(rank[:10],1):
        msg+=f"{i}. [{uid}](tg://user?id={uid}) — {pontos} pts\n"
    await update.message.reply_text(msg,parse_mode="Markdown")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users = len(USUARIOS)
    total_warns = sum(u["warns"] for u in USUARIOS.values())
    await update.message.reply_text(f"📊 Estatísticas:\nUsuários monitorados: {total_users}\nWarns totais: {total_warns}")

async def sticker_dia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if STICKERS:
        sticker = random.choice(STICKERS)
        await update.message.reply_sticker(sticker)

# ===== VOTEBAN =====
async def voteban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Responda a mensagem do usuário que deseja votar banir")
        return
    user = update.message.reply_to_message.from_user
    uid = str(user.id)
    chat_id = update.effective_chat.id
    VOTEBAN.setdefault(chat_id,{})
    VOTEBAN[chat_id].setdefault(uid,set())
    VOTEBAN[chat_id][uid].add(update.message.from_user.id)
    votos = len(VOTEBAN[chat_id][uid])
    if votos >= 3:  # 3 votos = ban automático
        await update.effective_chat.ban_member(user.id)
        await update.message.reply_text(f"🚫 {user.mention_html()} banido por votação!",parse_mode="HTML")
        del VOTEBAN[chat_id][uid]
    else:
        await update.message.reply_text(f"🗳️ Voto registrado ({votos}/3). Mais {3-votos} votos para banir.")

# ===== INICIALIZAÇÃO DO BOT =====
def main():
    load_data()
    app = Application.builder().token(TOKEN).build()

    # Comandos básicos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("regras", regras))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, boas_vindas))
    app.add_handler(CallbackQueryHandler(aceitar_regras, pattern="^aceitar_"))

    # Admin
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("warn", warn))

    # Anti-flood e filtro
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, antiflood))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filtro))

    # Reputação e ranking
    app.add_handler(MessageHandler(filters.Regex(r"^\+rep$|^\-rep$"), rep))
    app.add_handler(CommandHandler("ranking", ranking))

    # Estatísticas e sticker
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("sticker", sticker_dia))

    # Voteban
    app.add_handler(MessageHandler(filters.Regex(r"^/voteban$"), voteban))

    # Scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(backup, 'interval', minutes=BACKUP_INTERVAL_MIN)
    scheduler.start()

    # Webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        url_path=TOKEN,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
