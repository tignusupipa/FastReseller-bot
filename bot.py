import os
import logging
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# Carica variabili ambiente
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))  # metti admin telegram id separati da virgola

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

# Stati conversazione ordine
CHOOSING_PRODUCT, CHOOSING_QTY, CHOOSING_DETAILS, CONFIRMING = range(4)

# Prodotti e prezzi (modifica come vuoi)
products = {
    "cuffie": {"name": "Cuffie Wireless Modello X", "price": 45},
    "maglia": {"name": "Maglia Calcio Retrò", "price": 50},
    "maniche_lunghe": {"name": "Maglia Maniche Lunghe", "price": 55},
    "sneakers": {"name": "Sneakers Streetwear Edition", "price": 70},
}

# Ordini in memoria
orders = {}

# Funzioni helper
def is_admin(user_id):
    return user_id in ADMIN_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(prod["name"], callback_data=key)] for key, prod in products.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Benvenuto su FastReseller Bot! Usa /catalogo per vedere i prodotti o /ordina per iniziare un ordine.",
        reply_markup=reply_markup,
    )


async def catalogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📦 *Catalogo Prodotti Fast Reseller:*\n\n"
    for key, prod in products.items():
        text += f"- {prod['name']} — €{prod['price']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def ordina_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(prod["name"], callback_data=key)] for key, prod in products.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Scegli un prodotto da ordinare:", reply_markup=reply_markup)
    return CHOOSING_PRODUCT


async def choose_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_key = query.data
    user_id = update.effective_user.id
    orders[user_id] = {
        "product_key": product_key,
        "product": products[product_key]["name"],
        "price": products[product_key]["price"],
    }
    await query.edit_message_text(
        f"Hai scelto: {orders[user_id]['product']} — Prezzo unitario: €{orders[user_id]['price']}\nQuante unità vuoi ordinare?"
    )
    return CHOOSING_QTY


async def choose_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    qty_text = update.message.text
    if not qty_text.isdigit() or int(qty_text) < 1:
        await update.message.reply_text("Inserisci un numero valido (1 o più).")
        return CHOOSING_QTY
    orders[user_id]["quantity"] = int(qty_text)
    await update.message.reply_text("Inserisci eventuali dettagli o indirizzo di spedizione:")
    return CHOOSING_DETAILS


async def choose_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    orders[user_id]["details"] = update.message.text
    total_price = orders[user_id]["price"] * orders[user_id]["quantity"]
    summary = (
        f"📝 *Riepilogo ordine:*\n"
        f"Prodotto: {orders[user_id]['product']}\n"
        f"Quantità: {orders[user_id]['quantity']}\n"
        f"Dettagli: {orders[user_id]['details']}\n"
        f"Prezzo totale: €{total_price}\n\n"
        "Confermi l'ordine? (si/no)"
    )
    await update.message.reply_text(summary, parse_mode="Markdown")
    return CONFIRMING


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.lower()
    if text == "si":
        if send_order_email(orders[user_id]):
            await update.message.reply_text(
                "✅ Ordine ricevuto! Ti contatteremo presto. Grazie per aver scelto Fast Reseller."
            )
            save_order_log(user_id, orders[user_id])
        else:
            await update.message.reply_text(
                "❌ Errore nell'invio dell'ordine via email. Riprova più tardi."
            )
        del orders[user_id]
        return ConversationHandler.END
    elif text == "no":
        await update.message.reply_text("Ordine annullato.")
        del orders[user_id]
        return ConversationHandler.END
    else:
        await update.message.reply_text("Rispondi con 'si' o 'no'.")
        return CONFIRMING


def send_order_email(order):
    try:
        body = (
            f"Nuovo ordine da FastReseller Bot:\n\n"
            f"Prodotto: {order['product']}\n"
            f"Quantità: {order['quantity']}\n"
            f"Dettagli: {order['details']}\n"
            f"Prezzo totale: €{order['price']*order['quantity']}\n"
        )
        msg = MIMEText(body)
        msg["Subject"] = "Nuovo ordine FastReseller"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = RECEIVER_EMAIL

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        logger.info("Email ordine inviata con successo.")
        return True
    except Exception as e:
        logger.error(f"Errore invio email: {e}")
        return False


def save_order_log(user_id, order):
    with open("orders.log", "a", encoding="utf-8") as f:
        f.write(
            f"{datetime.now()} - User {user_id} - {order['product']} x{order['quantity']} - {order['details']}\n"
        )


# Moderation commands (ban, kick, mute)
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Non sei autorizzato a usare questo comando.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Usa questo comando in risposta al messaggio dell'utente da bannare.")
        return
    user_to_ban = update.message.reply_to_message.from_user.id
    chat = update.effective_chat
    try:
        await chat.ban_member(user_to_ban)
        await update.message.reply_text(f"Utente bannato con successo.")
    except Exception as e:
        await update.message.reply_text(f"Errore: {e}")


async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Non sei autorizzato a usare questo comando.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Usa questo comando in risposta al messaggio dell'utente da espellere.")
        return
    user_to_kick = update.message.reply_to_message.from_user.id
    chat = update.effective_chat
    try:
        await chat.unban_member(user_to_kick)  # per poterlo riaggiungere dopo
        await chat.kick_member(user_to_kick)
        await update.message.reply_text(f"Utente espulso con successo.")
    except Exception as e:
        await update.message.reply_text(f"Errore: {e}")


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Non sei autorizzato a usare questo comando.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Usa questo comando in risposta al messaggio dell'utente da mutare.")
        return
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Specifica il tempo di mute in minuti. Es: /mute 10")
        return
    mute_minutes = int(args[0])
    user_to_mute = update.message.reply_to_message.from_user.id
    chat = update.effective_chat
    until_date = datetime.utcnow() + timedelta(minutes=mute_minutes)
    permissions = ChatPermissions(can_send_messages=False)
    try:
        await chat.restrict_member(user_to_mute, permissions=permissions, until_date=until_date)
        await update.message.reply_text(f"Utente mutato per {mute_minutes} minuti.")
    except Exception as e:
        await update.message.reply_text(f"Errore: {e}")


async def ordini(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Non sei autorizzato a usare questo comando.")
        return
    try:
        with open("orders.log", "r", encoding="utf-8") as f:
            lines = f.readlines()[-20:]  # ultimi 20 ordini
        if not lines:
            await update.message.reply_text("Nessun ordine trovato.")
            return
        await update.message.reply_text("Ultimi ordini:\n" + "".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Errore nel leggere gli ordini: {e}")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("ordina", ordina_start)],
        states={
            CHOOSING_PRODUCT: [CallbackQueryHandler(choose_product)],
            CHOOSING_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_qty)],
            CHOOSING_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_details)],
            CONFIRMING: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order)],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("catalogo", catalogo))
    app.add_handler(CommandHandler("contatti", contatti))
    app.add_handler(CommandHandler("aiuto", aiuto))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("ordini", ordini))

    app.add_handler(conv_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
