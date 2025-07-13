import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
import smtplib
from email.mime.text import MIMEText

# Carica variabili da .env
load_dotenv()

# Stati conversazione
CHOOSING_PRODUCT, CHOOSING_QTY, CHOOSING_DETAILS, CONFIRMING = range(4)

# Prodotti con descrizioni e prezzi
products = {
    'cuffie': {'name': 'Cuffie Wireless Modello X', 'price': 45},
    'maglia': {'name': 'Maglia Calcio Retrò', 'price': 50},
    'sneakers': {'name': 'Sneakers Streetwear Edition', 'price': 70},
}

order = {}

BOT_TOKEN = os.getenv('BOT_TOKEN')
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(products[key]['name'], callback_data=key)] for key in products]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Benvenuto su FastReseller Bot! Scegli un prodotto:', reply_markup=reply_markup)
    return CHOOSING_PRODUCT

async def choose_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_key = query.data
    order['product'] = products[product_key]['name']
    await query.edit_message_text(f"Hai scelto: {order['product']}\nQuante unità vuoi ordinare?")
    return CHOOSING_QTY

async def choose_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qty_text = update.message.text
    if not qty_text.isdigit() or int(qty_text) < 1:
        await update.message.reply_text("Per favore, inserisci un numero valido.")
        return CHOOSING_QTY
    order['quantity'] = int(qty_text)
    await update.message.reply_text("Inserisci eventuali dettagli o indirizzo di spedizione:")
    return CHOOSING_DETAILS

async def choose_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order['details'] = update.message.text
    summary = (f"Riepilogo ordine:\nProdotto: {order['product']}\nQuantità: {order['quantity']}\nDettagli: {order['details']}\n\nConfermi l'ordine? (si/no)")
    await update.message.reply_text(summary)
    return CONFIRMING

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text == 'si':
        send_order_email(order)
        await update.message.reply_text("Ordine ricevuto! Ti contatteremo presto.")
        order.clear()
        return ConversationHandler.END
    elif text == 'no':
        await update.message.reply_text("Ordine annullato.")
        order.clear()
        return ConversationHandler.END
    else:
        await update.message.reply_text("Rispondi con 'si' o 'no'.")
        return CONFIRMING

def send_order_email(order):
    body = (f"Nuovo ordine da FastReseller Bot:\n\nProdotto: {order['product']}\nQuantità: {order['quantity']}\nDettagli: {order['details']}")
    msg = MIMEText(body)
    msg['Subject'] = 'Nuovo ordine FastReseller'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = RECEIVER_EMAIL
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("Email inviata con successo!")
    except Exception as e:
        print(f"Errore invio email: {e}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
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

if __name__ == '__main__':
    main()
