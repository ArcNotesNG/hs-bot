import os, threading, asyncio, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")
PHONE = "+2348076446822"

NAME, TITLE = range(2)

class MyBaseHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive")
    def log_message(self, *args):
        pass

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), MyBaseHTTPRequestHandler).serve_forever()

def main_menu():
    keyboard = [
        [InlineKeyboardButton("📅 Book Appointment", callback_data="book")],
        [InlineKeyboardButton("👨‍⚕️ Talk to Doctor", callback_data="doctor")],
        [InlineKeyboardButton("🕒 Opening Hours", callback_data="hours")],
        [InlineKeyboardButton("📍 Location", callback_data="location")],
        [InlineKeyboardButton("🚨 Emergency", callback_data="emergency")],
    ]
    return InlineKeyboardMarkup(keyboard)

def clean_name(text):
    t = text.strip()
    # Remove phrases like "my name is", "i'm", "i am", "call me"
    t = re.sub(r"(?i)^(my name is|my name's|my name|i'm|i am|call me|it is|it's)\s+", "", t)
    t = t.strip().strip(".").strip()
    # Take first 2 words only - e.g "Samuel Ade" -> "Samuel Ade"
    parts = t.split()
    if len(parts) >= 2:
        name = " ".join(parts[:2])
    elif parts:
        name = parts[0]
    else:
        name = t
    # Capitalize properly - samuel -> Samuel
    return " ".join([w.capitalize() for w in name.split()])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to H&S Health Care 🏥\n\nWhat is your name please?"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    name = clean_name(raw)
    context.user_data["name"] = name
    # Automatically refer as Mr - user can change later with /start
    context.user_data["title"] = "Mr"
    context.user_data["full"] = f"Mr {name}"
    await update.message.reply_text(
        f"Nice to meet you, Mr {name} 😊\n\nWelcome to H&S Health Care 🏥\n\nHow can we help you today? Choose one:",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    full = context.user_data.get("full", "there")

    if choice == "book":
        await query.message.reply_text(f"{full}, to book an appointment, please send:\n\n1. Your Phone Number\n2. What are you sick with?\n\nExample:\n08012345678\nFever and headache")
    elif choice == "doctor":
        await query.message.reply_text(f"{full}, to talk to a doctor, please send your phone number and we will call you back.\n\nOr call us directly: {PHONE}")
    elif choice == "hours":
        await query.message.reply_text("🕒 Opening Hours:\n\nMon - Fri: 8am - 8pm\nSaturday: 9am - 5pm\nSunday: Closed\n\nEmergency is open 24/7")
    elif choice == "location":
        await query.message.reply_text("📍 Our Location:\n\nH&S Health Care, Lagos, Nigeria.\n\nSend us your area and we will send directions.")
    elif choice == "emergency":
        await query.message.reply_text(f"🚨 EMERGENCY:\n\nCall us NOW: {PHONE}\n\nIf it is serious, go to nearest hospital immediately.")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full = context.user_data.get("full", "there")
    await update.message.reply_text(
        f"Thank you, {full}! We have received your message. Our team will contact you soon.\n\nSend /start to see the menu again.",
        reply_markup=main_menu()
    )

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    print("Bot started...")
    asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling()

if __name__ == "__main__":
    main()
