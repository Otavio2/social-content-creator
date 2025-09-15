import logging, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ========= CONFIGURAÇÕES =========
TOKEN = "SEU_TOKEN_DO_BOT"  # <- coloque aqui o token do BotFather
LANGS = ["pt", "en", "es"]
DEFAULT_LANG = "en"

MESSAGES = {
    "start": {
        "pt": "👋 Olá! Escolha seu idioma:",
        "en": "👋 Hello! Choose your language:",
        "es": "👋 ¡Hola! Elige tu idioma:"
    },
    "menu": {
        "pt": "📌 Comandos:\n/free - jogos grátis\n/deals - promoções\n/pokemon - pokémon\n/cards - baralho\n/dnd - feitiços D&D\n/board - jogos de tabuleiro",
        "en": "📌 Commands:\n/free - free games\n/deals - deals\n/pokemon - pokémon\n/cards - cards\n/dnd - D&D spells\n/board - boardgames",
        "es": "📌 Comandos:\n/free - juegos gratis\n/deals - ofertas\n/pokemon - pokémon\n/cards - baraja\n/dnd - conjuros D&D\n/board - juegos de mesa"
    },
    "free": {"pt": "🆓 Jogos grátis:", "en": "🆓 Free games:", "es": "🆓 Juegos gratis:"},
    "deals": {"pt": "💸 Promoções:", "en": "💸 Deals:", "es": "💸 Ofertas:"},
    "pokemon": {"pt": "🐱‍👤 Pokémon:", "en": "🐱‍👤 Pokémon:", "es": "🐱‍👤 Pokémon:"},
    "cards": {"pt": "🃏 Baralho:", "en": "🃏 Cards:", "es": "🃏 Baraja:"},
    "dnd": {"pt": "⚔️ Feitiços D&D:", "en": "⚔️ D&D Spells:", "es": "⚔️ Conjuros D&D:"},
    "board": {"pt": "🎲 Jogos de Tabuleiro:", "en": "🎲 Boardgames:", "es": "🎲 Juegos de mesa:"}
}

# Idioma por usuário
user_lang = {}
# Cache em memória
cache = {"free": [], "deals": [], "pokemon": [], "cards": [], "dnd": [], "board": []}

# ========= FUNÇÕES DE API =========
def fetch_freetogame():
    url = "https://www.freetogame.com/api/games"
    r = requests.get(url).json()
    return [f"{g['title']} - {g['genre']}" for g in r[:5]]

def fetch_gamerpower():
    url = "https://www.gamerpower.com/api/giveaways"
    r = requests.get(url).json()
    return [f"{g['title']} - {g['platforms']} ({g['end_date']})" for g in r[:5]]

def fetch_pokemon():
    url = "https://pokeapi.co/api/v2/pokemon?limit=5"
    r = requests.get(url).json()
    return [p['name'].capitalize() for p in r.get("results", [])]

def fetch_cards():
    url = "https://deckofcardsapi.com/api/deck/new/draw/?count=5"
    r = requests.get(url).json()
    return [f"{c['value']} of {c['suit']}" for c in r.get("cards", [])]

def fetch_dnd():
    url = "https://www.dnd5eapi.co/api/spells"
    r = requests.get(url).json()
    return [s['name'] for s in r.get("results", [])[:5]]

def fetch_board():
    url = "https://api.boardgameatlas.com/api/search?client_id=JLBr5npPhV&limit=5"
    r = requests.get(url).json()
    return [g['name'] for g in r.get("games", [])]

# Atualiza cache
def update_cache():
    try:
        cache["free"] = fetch_freetogame()
        cache["deals"] = fetch_gamerpower()
        cache["pokemon"] = fetch_pokemon()
        cache["cards"] = fetch_cards()
        cache["dnd"] = fetch_dnd()
        cache["board"] = fetch_board()
        print("✅ Cache atualizado")
    except Exception as e:
        print("Erro ao atualizar cache:", e)

# ========= HANDLERS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[InlineKeyboardButton(lang.upper(), callback_data=lang)] for lang in LANGS]
    await update.message.reply_text(MESSAGES["start"][DEFAULT_LANG], reply_markup=InlineKeyboardMarkup(buttons))

async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data
    user_lang[query.from_user.id] = lang
    await query.edit_message_text(MESSAGES["menu"][lang])

async def send_list(update: Update, key: str):
    lang = user_lang.get(update.message.from_user.id, DEFAULT_LANG)
    text = MESSAGES[key][lang] + "\n\n" + "\n".join(cache[key] or ["⚠️ Nenhum dado"])
    await update.message.reply_text(text)

async def free(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await send_list(update, "free")
async def deals(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await send_list(update, "deals")
async def pokemon(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await send_list(update, "pokemon")
async def cards(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await send_list(update, "cards")
async def dnd(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await send_list(update, "dnd")
async def board(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await send_list(update, "board")

# ========= MAIN =========
def main():
    app = Application.builder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(set_lang))
    app.add_handler(CommandHandler("free", free))
    app.add_handler(CommandHandler("deals", deals))
    app.add_handler(CommandHandler("pokemon", pokemon))
    app.add_handler(CommandHandler("cards", cards))
    app.add_handler(CommandHandler("dnd", dnd))
    app.add_handler(CommandHandler("board", board))

    # Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_cache, "interval", hours=6)
    scheduler.start()

    # Primeira atualização
    update_cache()

    print("🤖 Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()
