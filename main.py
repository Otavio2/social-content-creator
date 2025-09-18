import os
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Configurações
TOKEN = os.getenv("TELEGRAM_API")  # Pega o token do Render
PORT = int(os.getenv("PORT", 10000))

# Flask app
app = Flask(__name__)

# Ativa logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cria aplicação do bot
application = Application.builder().token(TOKEN).build()


# === Handlers de comandos ===
async def start(update: Update, context):
    await update.message.reply_text("👋 Bot está ativo e pronto!")


async def piada(update: Update, context):
    await update.message.reply_text("😂 Aqui vai uma piada: Por que o computador foi ao médico? Porque ele pegou um vírus!")


async def fato(update: Update, context):
    await update.message.reply_text("📘 Fato curioso: O mel nunca estraga. Arqueólogos encontraram mel em tumbas egípcias com milhares de anos e ainda estava bom!")


async def quiz(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("2", callback_data="quiz_wrong")],
        [InlineKeyboardButton("4", callback_data="quiz_right")],
        [InlineKeyboardButton("5", callback_data="quiz_wrong")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("❓ Quanto é 2 + 2?", reply_markup=reply_markup)


async def quiz_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "quiz_right":
        await query.edit_message_text("✅ Correto! 2 + 2 = 4")
    else:
        await query.edit_message_text("❌ Errado! Tente novamente.")


async def mensagem(update: Update, context):
    await update.message.reply_text("✉️ Sua mensagem foi recebida!")


# === Registrar handlers ===
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("piada", piada))
application.add_handler(CommandHandler("fato", fato))
application.add_handler(CommandHandler("quiz", quiz))
application.add_handler(CommandHandler("mensagem", mensagem))
application.add_handler(CallbackQueryHandler(quiz_callback))


# === Rotas Flask ===
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    """Recebe updates do Telegram"""
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)  # coloca na fila
    return "OK", 200


@app.route("/", methods=["GET"])
def home():
    return "Bot está rodando!", 200


if __name__ == "__main__":
    # Inicia servidor Flask
    app.run(host="0.0.0.0", port=PORT)
