import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
import smtplib
from email.mime.text import MIMEText
from fastapi import FastAPI
import uvicorn
import threading

# ========== FastAPI per l'endpoint /health ==========
fastapi_app = FastAPI()

@fastapi_app.get("/health")
def health():
    return {"status": "ok"}

# ========== Bot Telegram ==========
CHOOSING_PRODUCT, CHOOSING_QTY, CHOOSING_DETAILS, CONFIRMING = range(4)

products = {
    'cuffie': 'Cuffie Wireless Modello X',
    'maglia': 'Maglia Calcio Retrò',
    'sneakers': 'Sneakers Streetwear Edition'
}
order = {}

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(products[key], callback_data=key)] for key in products]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Benvenuto su FastReseller Bot! Scegli un prodotto:', reply_markup=reply_markup)
    return CHOOSING_PRODUCT

async def choose_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_key = query.data
    order['product'] = products[product_key]
    await query.edit_message_text(f"Hai scelto: {order['product']}\nQuante unità vuoi ordinare?")
    return CHOOSING_QTY

async def choose_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qty_text = update.message.text
    if not qty_text.isdigit():
        await update.message.reply_text("Per favore, inserisci un numero valido.")
        return CHOOSING_QTY
    order['quantity'] = int(qty_text)
    await update.message.reply_text("Inserisci eventuali dettagli o indirizzo di spedizione:")
    return CHOOSING_DETAILS

async def choose_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order['details'] = update.message.text
    summary = (
        f"Riepilogo ordine:\n"
        f"Prodotto: {order['product']}\n"
        f"Quantità: {order['quantity']}\n"
        f"Dettagli: {order['details']}\n\n"
        f"Confermi l'ordine? (si/no)"
    )
    await update.message.reply_text(summary)
    return CONFIRMING

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.lower() == 'si':
        send_order_email(order)
        await update.message.reply_text("Ordine ricevuto! Ti contatteremo presto.")
        order.clear()
        return ConversationHandler.END
    else:
        await update.message.reply_text("Ordine annullato.")
        order.clear()
        return ConversationHandler.END

def send_order_email(order):
    body = (
        f"Nuovo ordine:\n\n"
        f"Prodotto: {order['product']}\n"
        f"Quantità: {order['quantity']}\n"
        f"Dettagli: {order['details']}"
    )
    msg = MIMEText(body)
    msg['Subject'] = 'Nuovo ordine FastReseller'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = RECEIVER_EMAIL

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, RECEIVER_EMAIL, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Errore invio email: {e}")

def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_PRODUCT: [CallbackQueryHandler(choose_product)],
            CHOOSING_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_qty)],
            CHOOSING_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_details)],
            CONFIRMING: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order)]
        },
        fallbacks=[]
    )
    app.add_handler(conv_handler)
    app.run_polling()

# ========== Avvio multiplo: bot + fastapi ==========
if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    uvicorn.run(fastapi_app, host="0.0.0.0", port=10000)
