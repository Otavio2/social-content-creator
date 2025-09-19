import os
import random
import requests
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, PollAnswerHandler

TOKEN = os.getenv("BOT_TOKEN")  # defina no Render
bot = Bot(token=TOKEN)

app = Flask(__name__)

# =====================
# Sistema multilíngue
# =====================
TRANSLATIONS = {
    "pt": {
        "welcome": "🎮 Bem-vindo ao Quiz Bot!\n\nUse /quiz para começar.\nUse /score para ver sua pontuação.\n\nCategorias comuns:\n- 9 = Conhecimentos Gerais\n- 17 = Ciência & Natureza\n- 23 = História\n- 21 = Esportes\n\nExemplo: /quiz 17\n\nUse /quiz jservice para perguntas abertas.",
        "correct": "✅ Correto! (+10 pontos)\nPontuação: {score}",
        "wrong": "❌ Errado! Resposta: {resposta}\n(-5 pontos)\nPontuação: {score}",
        "score": "📊 Sua pontuação: {score}\n🎯 Nível atual: {nivel}",
        "jservice_label": "Pergunta aberta (Jeopardy!)"
    },
    "en": {
        "welcome": "🎮 Welcome to Quiz Bot!\n\nUse /quiz to start.\nUse /score to check your points.\n\nCommon categories:\n- 9 = General Knowledge\n- 17 = Science & Nature\n- 23 = History\n- 21 = Sports\n\nExample: /quiz 17\n\nUse /quiz jservice for open questions.",
        "correct": "✅ Correct! (+10 points)\nScore: {score}",
        "wrong": "❌ Wrong! Correct answer: {resposta}\n(-5 points)\nScore: {score}",
        "score": "📊 Your score: {score}\n🎯 Current level: {nivel}",
        "jservice_label": "Open question (Jeopardy!)"
    }
}

def t(user_lang, key, **kwargs):
    lang = user_lang if user_lang in TRANSLATIONS else "pt"
    return TRANSLATIONS[lang][key].format(**kwargs)

# =====================
# Perguntas APIs
# =====================
def get_question_otdb(category=None, difficulty="easy"):
    url = f"https://opentdb.com/api.php?amount=1&type=multiple&difficulty={difficulty}"
    if category:
        url += f"&category={category}"
    res = requests.get(url).json()
    q = res["results"][0]
    options = q["incorrect_answers"] + [q["correct_answer"]]
    random.shuffle(options)
    return q["question"], options, q["correct_answer"], q["category"]

def get_question_jservice():
    url = "https://jservice.io/api/random?count=1"
    res = requests.get(url).json()[0]
    pergunta = res["question"]
    resposta = res["answer"]
    categoria = res.get("category", {}).get("title", "Unknown")
    return pergunta, [resposta], resposta, categoria

def get_difficulty(score):
    if score <= 30:
        return "easy"
    elif score <= 60:
        return "medium"
    return "hard"

# =====================
# Handlers
# =====================
user_scores = {}     # {user_id: pontos}
active_quizzes = {}  # {poll_id: {"resposta": str, "user_id": int}}

def start(update: Update, context: CallbackContext):
    lang = update.effective_user.language_code or "pt"
    update.message.reply_text(t(lang, "welcome"))

def quiz(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    lang = update.effective_user.language_code or "pt"
    score = user_scores.get(user_id, 0)
    difficulty = get_difficulty(score)

    category = context.args[0] if context.args else None

    if category == "jservice":
        pergunta, opcoes, resposta, categoria = get_question_jservice()
        # Como jService é resposta aberta, tratamos como enquete fake de múltipla escolha
        opcoes = [resposta, "Não sei"]
        correct_index = 0
        categoria = t(lang, "jservice_label")
    else:
        pergunta, opcoes, resposta, categoria = get_question_otdb(category, difficulty)
        correct_index = opcoes.index(resposta)

    # Enviar quiz oficial
    msg = f"❓ ({categoria}, {difficulty})"
    poll = update.message.reply_poll(
        question=pergunta,
        options=opcoes,
        type="quiz",
        correct_option_id=correct_index,
        is_anonymous=False
    )

    active_quizzes[poll.poll.id] = {
        "resposta": resposta,
        "user_id": user_id,
        "lang": lang
    }

def handle_poll_answer(update: Update, context: CallbackContext):
    answer = update.poll_answer
    poll_id = answer.poll_id
    user_id = answer.user.id
    data = active_quizzes.get(poll_id)

    if not data or data["user_id"] != user_id:
        return

    lang = data["lang"]
    resposta_correta = data["resposta"]

    score = user_scores.get(user_id, 0)

    if answer.option_ids and answer.option_ids[0] == 0 and resposta_correta.lower() in [resposta_correta.lower()]:
        score += 10
        bot.send_message(user_id, t(lang, "correct", score=score))
    elif resposta_correta:
        score = max(score - 5, 0)
        bot.send_message(user_id, t(lang, "wrong", resposta=resposta_correta, score=score))

    user_scores[user_id] = score
    del active_quizzes[poll_id]

def score(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    lang = update.effective_user.language_code or "pt"
    score = user_scores.get(user_id, 0)
    difficulty = get_difficulty(score)
    update.message.reply_text(t(lang, "score", score=score, nivel=difficulty))

# =====================
# Flask Webhook
# =====================
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dp = Dispatcher(bot, None, workers=0)
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("quiz", quiz))
    dp.add_handler(CommandHandler("score", score))
    dp.add_handler(PollAnswerHandler(handle_poll_answer))
    dp.process_update(update)
    return "ok"

@app.route("/")
def home():
    return "Bot de Quiz com votação real rodando! 🚀"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
