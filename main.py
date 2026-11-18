import os, threading, asyncio, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")
PHONE = "+2348076446822"
HOSPITAL_GROUP_ID = os.environ.get("HOSPITAL_GROUP_ID")
DOCTOR_CHAT_ID = os.environ.get("DOCTOR_CHAT_ID")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

NAME, TITLE, PHONE_STATE = range(3)

MALE_NAMES = {
    "samuel", "john", "michael", "david", "daniel", "joseph", "emmanuel", "chinedu", "chidi",
    "emeka", "obinna", "oluwaseun", "tunde", "segun", "ade", "adebayo", "kunle", "femi", "bayo",
    "ifeanyi", "chukwu", "eze", "uchenna", "olamide", "temitope", "ayodele", "ibrahim", "musa",
    "usman", "abdul", "ahmed", "yusuf", "peter", "paul", "james", "andrew", "matthew", "mark",
    "luke", "joshua", "caleb", "isaac", "jacob", "moses", "elijah", "gabriel", "victor", "frank",
    "charles", "henry", "george", "thomas", "william", "richard", "robert", "anthony", "kevin",
    "chris", "christopher", "nicholas", "stephen", "philip", "timothy", "benjamin", "austin", "kenneth"
}

FEMALE_NAMES = {
    "ada", "adaeze", "adaobi", "ngozi", "nkechi", "chioma", "amara", "chiamaka", "funke",
    "folake", "tola", "toluwani", "adeola", "bisi", "yetunde", "omolara", "kemi", "simisola",
    "temilade", "oluwatoyin", "aisha", "fatima", "maryam", "zainab", "halima", "amina",
    "mary", "grace", "faith", "hope", "joy", "peace", "blessing", "mercy", "esther",
    "ruth", "sarah", "hannah", "rebecca", "rachel", "deborah", "elizabeth", "victoria", "janet",
    "susan", "linda", "karen", "nancy", "betty", "doris", "patricia", "barbara", "jessica",
    "amanda", "emily", "sophia", "olivia", "isabella", "mia", "ella", "ava", "chidinma", "uchechi"
}

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

def title_menu():
    keyboard = [
        [InlineKeyboardButton("Mr", callback_data="title_Mr"),
         InlineKeyboardButton("Mrs", callback_data="title_Mrs")],
        [InlineKeyboardButton("Miss", callback_data="title_Miss")],
    ]
    return InlineKeyboardMarkup(keyboard)

def clean_name(text):
    t = text.strip()
    t = re.sub(r"(?i)^(my name is|my name's|my name|i'm|i am|call me|it is|it's)\s+", "", t)
    t = t.strip().strip(".").strip()
    parts = t.split()
    if len(parts) >= 2:
        name = " ".join(parts[:2])
    elif parts:
        name = parts[0]
    else:
        name = t
    return " ".join([w.capitalize() for w in name.split()])

def guess_title(name):
    first = name.split()[0].lower() if name else ""
    if first in MALE_NAMES:
        return "Mr"
    if first in FEMALE_NAMES:
        return "Mrs"
    return None

def get_patient_info(update, context):
    full = context.user_data.get("full", "Patient")
    phone = context.user_data.get("phone", "Not provided")
    username = update.effective_user.username
    username_text = f"@{username}" if username else "No username"
    user_id = update.effective_user.id
    return full, phone, username_text, user_id

async def send_to_hospital(context, text):
    if HOSPITAL_GROUP_ID:
        try:
            await context.bot.send_message(chat_id=HOSPITAL_GROUP_ID, text=text)
        except Exception as e:
            print(f"Group send failed: {e}")
    if DOCTOR_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=DOCTOR_CHAT_ID, text=text)
        except Exception as e:
            print(f"Doctor send failed: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("phone"):
        full = context.user_data.get("full", "there")
        text = f"Welcome back, {full} 😊\n\nHow can we help you today? Choose one:"
        await update.message.reply_text(text, reply_markup=main_menu())
        return ConversationHandler.END
    await update.message.reply_text("Welcome to H&S Health Care 🏥\n\nWhat is your name please?")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = clean_name(update.message.text)
    context.user_data["name"] = name
    title = guess_title(name)
    if title:
        context.user_data["title"] = title
        context.user_data["full"] = f"{title} {name}"
        await update.message.reply_text(f"Nice to meet you, {title} {name} 😊\n\nWhat is your phone number so the doctor can call you back? Example: 08012345678")
        return PHONE_STATE
    await update.message.reply_text(f"Nice to meet you, {name} 😊\n\nHow should I address you?", reply_markup=title_menu())
    return TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    title = query.data.replace("title_", "")
    name = context.user_data.get("name", "")
    context.user_data["title"] = title
    context.user_data["full"] = f"{title} {name}"
    await query.edit_message_text(f"Thank you, {title} {name}!")
    await query.message.reply_text("What is your phone number so the doctor can call you back? Example: 08012345678")
    return PHONE_STATE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    digits = re.sub(r"[^\d+]", "", text)
    if len(digits) < 10:
        await update.message.reply_text("Sorry, that phone number looks too short. Please type it again, e.g. 08012345678")
        return PHONE_STATE
    context.user_data["phone"] = digits
    full = context.user_data.get("full", "")
    msg = f"Thank you, {full}! I have saved your phone number: {digits} ✅\n\nYou will not need to type it again.\n\nNow, how can we help you today? You can type, send a voice note, or send a picture of your wound."
    await update.message.reply_text(msg, reply_markup=main_menu())
    return ConversationHandler.END

async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full = context.user_data.get("full", "there")
    msg = f"{full}, to book an appointment, please send:\n\nWhat are you sick with?\n\nExample:\nFever and headache\n\nYou can also send a voice note or picture."
    await update.message.reply_text(msg)

async def doctor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full = context.user_data.get("full", "there")
    msg = f"{full}, to talk to a doctor, just send a voice note or type your problem here. We will forward it to the doctor.\n\nOr call us directly: {PHONE}"
    await update.message.reply_text(msg)

async def emergency_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"🚨 EMERGENCY:\n\nCall us NOW: {PHONE}\n\nIf it is serious, go to nearest hospital immediately."
    await update.message.reply_text(msg)

async def hours_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """🕒 Opening Hours:

Mon - Fri: 8am - 8pm
Saturday: 9am - 5pm
Sunday: Closed

Emergency is open 24/7"""
    await update.message.reply_text(msg)

async def location_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """📍 Our Location:

H&S Health Care, Lagos, Nigeria.

Send us your area and we will send directions."""
    await update.message.reply_text(msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """❓ How to use this bot:

1. Type /start to start
2. Type your name and phone number once
3. After that, you can:
   - Type your problem
   - Send a VOICE NOTE in any language
   - Send a PICTURE of your wound

Commands:
/book - Book appointment
/doctor - Talk to doctor
/emergency - Emergency
/hours - Opening hours
/location - Location

Just type / and choose from the menu!"""
    await update.message.reply_text(msg, reply_markup=main_menu())

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    full = context.user_data.get("full", "there")
    if choice == "book":
        msg = f"{full}, to book an appointment, please send:\n\nWhat are you sick with?\n\nExample:\nFever and headache\n\nYou can also send a voice note or picture."
        await query.message.reply_text(msg)
    elif choice == "doctor":
        msg = f"{full}, to talk to a doctor, just send a voice note or type your problem here. We will forward it to the doctor.\n\nOr call us directly: {PHONE}"
        await query.message.reply_text(msg)
    elif choice == "hours":
        msg = """🕒 Opening Hours:

Mon - Fri: 8am - 8pm
Saturday: 9am - 5pm
Sunday: Closed

Emergency is open 24/7"""
        await query.message.reply_text(msg)
    elif choice == "location":
        msg = """📍 Our Location:

H&S Health Care, Lagos, Nigeria.

Send us your area and we will send directions."""
        await query.message.reply_text(msg)
    elif choice == "emergency":
        msg = f"🚨 EMERGENCY:\n\nCall us NOW: {PHONE}\n\nIf it is serious, go to nearest hospital immediately."
        await query.message.reply_text(msg)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full, phone, username_text, user_id = get_patient_info(update, context)
    if not context.user_data.get("phone"):
        await update.message.reply_text("Welcome! Before we continue, what is your name please?")
        return NAME
    await update.message.reply_text(f"Thank you, {full}. I have received your voice note. I am sending it to the doctor now. Please wait a little 🙏")
    caption = f"🎤 NEW VOICE NOTE FROM PATIENT\n\nName: {full}\nUsername: {username_text}\nPhone: {phone}\nUser ID: {user_id}"
    voice = update.message.voice
    if HOSPITAL_GROUP_ID:
        try:
            await context.bot.send_voice(chat_id=HOSPITAL_GROUP_ID, voice=voice.file_id, caption=caption)
        except Exception as e:
            print(f"Group voice failed: {e}")
    if DOCTOR_CHAT_ID:
        try:
            await context.bot.send_voice(chat_id=DOCTOR_CHAT_ID, voice=voice.file_id, caption=caption)
        except Exception as e:
            print(f"Doctor voice failed: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full, phone, username_text, user_id = get_patient_info(update, context)
    if not context.user_data.get("phone"):
        await update.message.reply_text("Welcome! Before we continue, what is your name please?")
        return NAME
    await update.message.reply_text(f"Thank you, {full}. I have received your picture. I am sending it to the hospital and doctor now. 📸")
    caption_text = update.message.caption or "No description"
    caption = f"🚨 NEW PATIENT PICTURE\n\nName: {full}\nUsername: {username_text}\nPhone: {phone}\nUser ID: {user_id}\nMessage: {caption_text}"
    photo = update.message.photo[-1]
    if HOSPITAL_GROUP_ID:
        try:
            await context.bot.send_photo(chat_id=HOSPITAL_GROUP_ID, photo=photo.file_id, caption=caption)
        except Exception as e:
            print(f"Group photo failed: {e}")
    if DOCTOR_CHAT_ID:
        try:
            await context.bot.send_photo(chat_id=DOCTOR_CHAT_ID, photo=photo.file_id, caption=caption)
        except Exception as e:
            print(f"Doctor photo failed: {e}")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full = context.user_data.get("full", "there")
    phone = context.user_data.get("phone", "Not saved yet")
    if context.user_data.get("phone"):
        full2, phone2, username_text, user_id = get_patient_info(update, context)
        msg = f"💬 NEW MESSAGE FROM PATIENT\n\nName: {full2}\nUsername: {username_text}\nPhone: {phone2}\nMessage: {update.message.text}"
        await send_to_hospital(context, msg)
    msg2 = f"Thank you, {full}! We have received your message. Our team will contact you soon on {phone}.\n\nSend /start to see the menu again."
    await update.message.reply_text(msg2, reply_markup=main_menu())

async def set_bot_commands(app):
    commands = [
        BotCommand("start", "Start bot and get help"),
        BotCommand("book", "Book appointment"),
        BotCommand("doctor", "Talk to doctor"),
        BotCommand("emergency", "Emergency number"),
        BotCommand("hours", "Opening hours"),
        BotCommand("location", "Hospital location"),
        BotCommand("help", "How to use bot"),
    ]
    await app.bot.set_my_commands(commands)

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.post_init = set_bot_commands
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            TITLE: [CallbackQueryHandler(get_title, pattern="^title_")],
            PHONE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[],
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("book", book_command))
    app.add_handler(CommandHandler("doctor", doctor_command))
    app.add_handler(CommandHandler("emergency", emergency_command))
    app.add_handler(CommandHandler("hours", hours_command))
    app.add_handler(CommandHandler("location", location_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    print("Bot started...")
    asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling()

if __name__ == "__main__":
    main()
