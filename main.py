import os, threading, asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to H&S Health Care Su... 🏥\n\nHow can we help you today? Choose one:",
        reply_markup=main_menu()
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "book":
        await query.message.reply_text("To book an appointment, please send:\n\n1. Your Full Name\n2. Your Phone Number\n3. What are you sick with?\n\nExample:\nJohn Doe\n08012345678\nFever and headache")
    elif choice == "doctor":
        await query.message.reply_text("To talk to a doctor, please send your phone number and we will call you back.\n\nOr call us directly: +234 800 000 0000")
    elif choice == "hours":
        await query.message.reply_text("🕒 Opening Hours:\n\nMon - Fri: 8am - 8pm\nSaturday: 9am - 5pm\nSunday: Closed\n\nEmergency is open 24/7")
    elif choice == "location":
        await query.message.reply_text("📍 Our Location:\n\nH&S Health Care, Lagos, Nigeria.\n\nSend us your area and we will send directions.")
    elif choice == "emergency":
        await query.message.reply_text("🚨 EMERGENCY:\n\nCall us NOW: +234 800 000 0000\n\nIf it is serious, go to nearest hospital immediately.")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Thank you! We received your message:\n\n\"{update.message.text}\"\n\nOur team will reply to you soon. For menu, send /start",
    )

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    print("Bot started...")
    asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling()

if __name__ == "__main__":
    main()
