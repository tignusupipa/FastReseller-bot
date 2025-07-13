import os
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)
from email.mime.text import MIMEText
import smtplib
from fastapi import FastAPI
import uvicorn

# Stati conversazione ordine
CHOOSING_PRODUCT, CHOOSING_QTY, CHOOSING_DETAILS, CONFIRMING = range(4)

# Prodotti
products = {
    'cuffie': 'Cuffie Wireless Modello X',
    'maglia': 'Maglia Calcio Retrò',
    'sneakers': 'Sneakers Streetwear Edition'
}

# Config email e token da env
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Ordini temporanei (user_id -> ordine)
active_orders = {}

# Lista ordini recenti (solo per memoria temporanea)
orders_list = []

app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# --- COMANDI BASE ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(products[key], callback_data=key)] for key in products]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Benvenuto su FastReseller Bot! Scegli un prodotto:', reply_markup=reply_markup)
    return CHOOSING_PRODUCT

async def catalogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📦 Catalogo Prodotti:\n\n"
    for val in products.values():
        msg += f"- {val}\n"
    await update.message.reply_text(msg)

async def ordina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)

async def contatti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📞 Contatti FastReseller:\n"
        "Email: fastreseller10@gmail.com\n"
        "Instagram: @fastreseller\n"
        "Telefono: +39 351 915 2147"
    )
    await update.message.reply_text(msg)

async def aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "/start - Avvia il bot e mostra il menu prodotti\n"
        "/catalogo - Mostra il catalogo prodotti\n"
        "/ordina - Inizia l’ordine guidato\n"
        "/contatti - I nostri recapiti\n"
        "/aiuto - Come usare il bot\n"
        "/info - Info sul negozio e sito\n"
        "/ban - Bannare un utente (mod)\n"
        "/kick - Espellere un utente (mod)\n"
        "/mute - Muta un utente per un tempo (mod)\n"
        "/ordini - Lista ordini recenti (admin)"
    )
    await update.message.reply_text(msg)

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "FastReseller è il tuo negozio online di fiducia!\n"
        "Visita il sito: https://fast-reseller.vercel.app\n"
        "Seguici su Instagram @fastreseller"
    )
    await update.message.reply_text(msg)

# --- ORDINE CONVERSAZIONE ---

async def choose_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    product_key = query.data
    active_orders[user_id] = {
        'product': products.get(product_key, "Prodotto sconosciuto"),
        'product_key': product_key
    }
    await query.edit_message_text(f"Hai scelto: {active_orders[user_id]['product']}\nQuante unità vuoi ordinare?")
    return CHOOSING_QTY

async def choose_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    qty_text = update.message.text
    if not qty_text.isdigit() or int(qty_text) < 1:
        await update.message.reply_text("Per favore, inserisci un numero valido.")
        return CHOOSING_QTY
    active_orders[user_id]['quantity'] = int(qty_text)
    await update.message.reply_text("Inserisci eventuali dettagli o indirizzo di spedizione:")
    return CHOOSING_DETAILS

async def choose_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    active_orders[user_id]['details'] = update.message.text
    order = active_orders[user_id]
    summary = (f"Riepilogo ordine:\n"
               f"Prodotto: {order['product']}\n"
               f"Quantità: {order['quantity']}\n"
               f"Dettagli: {order['details']}\n\n"
               f"Confermi l'ordine? (si/no)")
    await update.message.reply_text(summary)
    return CONFIRMING

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.lower()
    if text == 'si':
        order = active_orders.get(user_id)
        if order:
            send_order_email(order)
            orders_list.append(order)  # salva in lista ordini recenti
            await update.message.reply_text("Ordine ricevuto! Ti contatteremo presto.")
            active_orders.pop(user_id)
        else:
            await update.message.reply_text("Nessun ordine in corso.")
        return ConversationHandler.END
    elif text == 'no':
        await update.message.reply_text("Ordine annullato.")
        active_orders.pop(user_id, None)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Rispondi con 'si' o 'no'.")
        return CONFIRMING

def send_order_email(order):
    body = (f"Nuovo ordine da FastReseller Bot:\n\n"
            f"Prodotto: {order['product']}\n"
            f"Quantità: {order['quantity']}\n"
            f"Dettagli: {order['details']}")
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
        print("Email inviata con successo!")
    except Exception as e:
        print(f"Errore invio email: {e}")

# --- HANDLER CONVERSAZIONE ORDINE ---

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start), CommandHandler('ordina', ordina)],
    states={
        CHOOSING_PRODUCT: [CallbackQueryHandler(choose_product)],
        CHOOSING_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_qty)],
        CHOOSING_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_details)],
        CONFIRMING: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order)]
    },
    fallbacks=[]
)

app_bot.add_handler(conv_handler)

# --- ALTRI COMANDI SEMPLICI ---

app_bot.add_handler(CommandHandler('catalogo', catalogo))
app_bot.add_handler(CommandHandler('contatti', contatti))
app_bot.add_handler(CommandHandler('aiuto', aiuto))
app_bot.add_handler(CommandHandler('info', info))

# --- FASTAPI WEB SERVER PER UPTIME ROBOT ---

fastapi_app = FastAPI()

@fastapi_app.get("/health")
async def health_check():
    return {"status": "ok"}

def run_bot():
    app_bot.run_polling()

def run_web():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    threading.Thread(target=run_web).start()
