import logging
import json
import os
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackContext, CallbackQueryHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ===== CONFIGURAÇÃO =====
TOKEN = "SEU_TOKEN_AQUI"
ADMIN_LOG_CHAT_ID = -1001234567890  # Grupo ou canal de logs
MAX_WARNINGS = 3
FLOOD_LIMIT = 5  # mensagens por 10 segundos
PROIBIDO = ["palavrão1", "palavrão2"]  # palavras proibidas
FILTROS = ["http://", "https://", "t.me/"]  # links bloqueados
MENSAGEM_BOAS_VINDAS = "👋 Bem-vindo {user}! Leia as regras e clique em aceitar."
MENSAGEM_REGRAS = "📜 Regras do grupo:\n1. Sem spam\n2. Sem links\n3. Respeite todos"
TEMPO_MUTE_FLOOD = 1  # minutos
TEMPO_MUTE_FILTRO = 1  # minutos
BACKUP_INTERVAL_MIN = 30  # minutos

DATA_FILE = "users.json"
USUARIOS = {}

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== FUNÇÕES DE ARQUIVO =====
def load_data():
    global USUARIOS
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            USUARIOS = json.load(f)
    else:
        USUARIOS = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(USUARIOS, f, indent=2, ensure_ascii=False)

# ===== COMANDOS BÁSICOS =====
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("🤖 Bot admin ativo!")

async def regras(update: Update, context: CallbackContext):
    await update.message.reply_text(MENSAGEM_REGRAS)

# ===== BOAS-VINDAS + CAPTCHA =====
async def boas_vindas(update: Update, context: CallbackContext):
    for user in update.message.new_chat_members:
        msg = MENSAGEM_BOAS_VINDAS.format(user=user.mention_html())
        keyboard = [[InlineKeyboardButton("✅ Aceitar regras", callback_data=f"aceitar_{user.id}")]]
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        await update.effective_chat.restrict_member(user.id, ChatPermissions(can_send_messages=False))

async def aceitar_regras(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = int(query.data.split("_")[1])
    await context.bot.restrict_chat_member(query.message.chat.id, user_id, ChatPermissions(can_send_messages=True, can_send_media_messages=True))
    await query.answer("Regras aceitas ✅")

# ===== COMANDOS ADMIN =====
async def ban(update: Update, context: CallbackContext):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await update.effective_chat.ban_member(user.id)
        await update.message.reply_text(f"🚫 {user.mention_html()} banido!", parse_mode="HTML")

async def kick(update: Update, context: CallbackContext):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await update.effective_chat.ban_member(user.id)
        await update.effective_chat.unban_member(user.id)
        await update.message.reply_text(f"👢 {user.mention_html()} expulso!", parse_mode="HTML")

async def mute(update: Update, context: CallbackContext):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        until = datetime.now() + timedelta(minutes=10)
        await update.effective_chat.restrict_member(user.id, ChatPermissions(), until_date=until)
        await update.message.reply_text(f"🔇 {user.mention_html()} silenciado!", parse_mode="HTML")

async def unmute(update: Update, context: CallbackContext):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        await update.effective_chat.restrict_member(user.id, ChatPermissions(can_send_messages=True, can_send_media_messages=True))
        await update.message.reply_text(f"🔊 {user.mention_html()} liberado!", parse_mode="HTML")

# ===== SYSTEMA DE WARNS =====
async def warn(update: Update, context: CallbackContext):
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

# ===== ANTI-FLOOD =====
async def antiflood(update: Update, context: CallbackContext):
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

# ===== FILTRO DE PALAVRAS/LINKS =====
async def filtro(update: Update, context: CallbackContext):
    text = update.message.text.lower()
    if any(p in text for p in PROIBIDO) or any(f in text for f in FILTROS):
        await update.message.delete()
        await update.effective_chat.restrict_member(update.message.from_user.id, ChatPermissions(can_send_messages=False), until_date=datetime.now()+timedelta(minutes=TEMPO_MUTE_FILTRO))
        await context.bot.send_message(ADMIN_LOG_CHAT_ID,f"🚨 Mensagem apagada de {update.message.from_user.mention_html()}",parse_mode="HTML")

# ===== BACKUP =====
def backup():
    save_data()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_users_{timestamp}.json"
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(USUARIOS, f, indent=2, ensure_ascii=False)
    logger.info(f"Backup salvo em {backup_file}")

# ===== SCHEDULER =====
scheduler = AsyncIOScheduler()
async def mensagem_agendada(context: CallbackContext):
    await context.bot.send_message(context.job.chat_id,"⏰ Mensagem programada do bot!")

# ===== MAIN =====
def main():
    load_data()
    app = Application.builder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("regras", regras))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, boas_vindas))
    app.add_handler(CallbackQueryHandler(aceitar_regras, pattern="^aceitar_"))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, antiflood))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, filtro))

    # Scheduler
    scheduler.add_job(backup,"interval",minutes=BACKUP_INTERVAL_MIN)
    scheduler.start()

    app.run_polling()

if __name__ == "__main__":
    main()
