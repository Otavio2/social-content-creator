import os
import random
import requests
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, PollAnswerHandler, ContextTypes

# =====================
# Config
# =====================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ BOT_TOKEN não definido! Configure no Render em Environment Variables.")

# URL base do Render (ajuste se mudar o nome do serviço!)
BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "https://social-content-creator.onrender.com")

bot = Bot(token=TOKEN)
app = Flask(__name__)

# Importante: desabilita o Updater (usamos só webhook no Render)
application = Application.builder().token(TOKEN).updater(None).build()

# =====================
# Traduções
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
# Funções auxiliares
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
# Estado do jogo
# =====================
user_scores = {}     # {user_id: pontos}
active_quizzes = {}  # {poll_id: {"resposta": str, "user_id": int, "lang": str, "correct_index": int}}

# =====================
# Handlers
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = update.effective_user.language_code or "pt"
    await update.message.reply_text(t(lang, "welcome"))

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = update.effective_user.language_code or "pt"
    score = user_scores.get(user_id, 0)
    difficulty = get_difficulty(score)

    category = context.args[0] if context.args else None

    if category == "jservice":
        pergunta, opcoes, resposta, categoria = get_question_jservice()
        opcoes = [resposta, "Não sei", "Talvez", "Outra opção"]  # simula múltipla escolha
        correct_index = 0
        categoria = t(lang, "jservice_label")
    else:
        pergunta, opcoes, resposta, categoria = get_question_otdb(category, difficulty)
        correct_index = opcoes.index(resposta)

    poll = await update.message.reply_poll(
        question=f"❓ ({categoria}, {difficulty})\n\n{pergunta}",
        options=opcoes,
        type="quiz",
        correct_option_id=correct_index,
        is_anonymous=False
    )

    active_quizzes[poll.poll.id] = {
        "resposta": resposta,
        "user_id": user_id,
        "lang": lang,
        "correct_index": correct_index
    }

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll_id = answer.poll_id
    user_id = answer.user.id
    data = active_quizzes.get(poll_id)

    if not data or data["user_id"] != user_id:
        return

    lang = data["lang"]
    resposta_correta = data["resposta"]
    correct_index = data["correct_index"]

    score = user_scores.get(user_id, 0)

    if answer.option_ids and answer.option_ids[0] == correct_index:
        score += 10
        await bot.send_message(user_id, t(lang, "correct", score=score))
    else:
        score = max(score - 5, 0)
        await bot.send_message(user_id, t(lang, "wrong", resposta=resposta_correta, score=score))

    user_scores[user_id] = score
    del active_quizzes[poll_id]

async def score_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = update.effective_user.language_code or "pt"
    score = user_scores.get(user_id, 0)
    difficulty = get_difficulty(score)
    await update.message.reply_text(t(lang, "score", score=score, nivel=difficulty))

# =====================
# Registra handlers
# =====================
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("quiz", quiz))
application.add_handler(CommandHandler("score", score_cmd))
application.add_handler(PollAnswerHandler(handle_poll_answer))

# =====================
# Flask Webhook
# =====================
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    application.update_queue.put_nowait(update)
    return "ok", 200

@app.route("/")
def home():
    return "Bot de Quiz com votação real rodando! 🚀"

# Endpoint opcional para forçar webhook manualmente
@app.route("/setwebhook")
def set_webhook():
    url = f"{BASE_URL}/{TOKEN}"
    success = bot.set_webhook(url)
    return f"Webhook {'OK' if success else 'FAIL'} → {url}"

# =====================
# Inicialização
# =====================
if __name__ == "__main__":
    # Seta webhook automaticamente no startup
    webhook_url = f"{BASE_URL}/{TOKEN}"
    print(f"📡 Registrando webhook em: {webhook_url}")
    bot.set_webhook(webhook_url)

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
