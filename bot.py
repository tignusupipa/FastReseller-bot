import os
import threading
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import smtplib
from email.mime.text import MIMEText
from fastapi import FastAPI
import uvicorn

# Carica .env
load_dotenv()

# Variabili ambiente
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# FastAPI per /health
fastapi_app = FastAPI()

@fastapi_app.get("/health")
def health():
    return {"status": "ok"}

# Prodotti disponibili
products = {
    'cuffie': 'Cuffie Wireless Modello X',
    'maglia': 'Maglia Calcio Retrò',
    'sneakers': 'Sneakers Streetwear Edition'
}

order = {}
CHOOSING_PRODUCT, CHOOSING_QTY, CHOOSING_DETAILS, CONFIRMING = range(4)

# ----- BOT HANDLERS -----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(name, callback_data=key)] for key, name in products.items()]
    await update.message.reply_text("Benvenuto su FastReseller Bot! Scegli un prodotto da ordinare:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING_PRODUCT

async def choose_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order['product'] = products[query.data]
    await query.edit_message_text(f"Hai scelto: {order['product']}\nQuante unità vuoi ordinare?")
    return CHOOSING_QTY

async def choose_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text.isdigit() or int(text) < 1:
        await update.message.reply_text("Inserisci un numero valido.")
        return CHOOSING_QTY
    order['quantity'] = int(text)
    await update.message.reply_text("Inserisci indirizzo o dettagli per la spedizione:")
    return CHOOSING_DETAILS

async def choose_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order['details'] = update.message.text
    await update.message.reply_text(
        f"Riepilogo ordine:\n"
        f"📦 Prodotto: {order['product']}\n"
        f"🔢 Quantità: {order['quantity']}\n"
        f"📍 Dettagli: {order['details']}\n"
        "Confermi l'ordine? (si/no)"
    )
    return CONFIRMING

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() == "si":
        send_email(order)
        await update.message.reply_text("✅ Ordine ricevuto! Ti contatteremo al più presto.")
    else:
        await update.message.reply_text("❌ Ordine annullato.")
    order.clear()
    return ConversationHandler.END

def send_email(order):
    msg = MIMEText(
        f"Nuovo ordine:\n\n"
        f"Prodotto: {order['product']}\n"
        f"Quantità: {order['quantity']}\n"
        f"Dettagli: {order['details']}"
    )
    msg['Subject'] = 'Nuovo Ordine FastReseller'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Email inviata!")
    except Exception as e:
        print("Errore invio email:", e)

# Altri comandi
async def catalogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lista = "\n".join([f"- {v}" for v in products.values()])
    await update.message.reply_text(f"Ecco il catalogo prodotti:\n{lista}")

async def contatti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📧 Email: fastreseller10@gmail.com\n📱 Instagram: @fastreseller\n🌐 Sito: fast-reseller.vercel.app")

async def aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Usa i comandi per esplorare il catalogo e fare ordini:\n/start - Menu\n/catalogo - Tutti i prodotti\n/ordina - Ordina ora")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("FastReseller è il tuo shop di fiducia per prodotti tech, streetwear, profumi e molto altro! 🌟")

def run_web():
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)

def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("ordina", start)],
        states={
            CHOOSING_PRODUCT: [CallbackQueryHandler(choose_product)],
            CHOOSING_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_qty)],
            CHOOSING_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_details)],
            CONFIRMING: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("catalogo", catalogo))
    app.add_handler(CommandHandler("contatti", contatti))
    app.add_handler(CommandHandler("aiuto", aiuto))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    run_bot()
