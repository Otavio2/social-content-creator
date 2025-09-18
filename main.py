import os
import telebot
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.reply_to(message, "👾 GeniaNode activado. Estoy listo para generar valor por ti.")

@bot.message_handler(func=lambda m: True)
def echo_all(message):
    bot.reply_to(message, f"Recibido: {message.text}")

print("🔥 GeniaNode está en línea")
bot.infinity_polling()
