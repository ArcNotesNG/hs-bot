import os, threading, asyncio, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")
PHONE = "+2348076446822"
HOSPITAL_GROUP_ID = os.environ.get("HOSPITAL_GROUP_ID")  # e.g. -1001234567890
DOCTOR_CHAT_ID = os.environ.get("DOCTOR_CHAT_ID")  # e.g. 123456789
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")  # optional, for voice transcription

NAME, TITLE, PHONE_STATE = range(3)

# --- NAME LISTS ---
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
    # Send to group and doctor
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
    # If already registered, skip to menu
    if context.user_data.get("phone"):
        full = context.user_data.get("full", "there")
        await update.message.reply_text(f"Welcome back, {full} 😊\n\nHow can we help you today? Choose one:", reply_markup=main_menu())
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
    # Extract phone number - allow 080..., +234..., 234...
    digits = re.sub(r"[^\d+]", "", text)
    if len(digits) < 10:
        await update.message.reply_text("Sorry, that phone number looks too short. Please type it again, e.g. 08012345678")
        return PHONE_STATE
    context.user_data["phone"] = digits
    full = context.user_data.get("full", "")
    await update.message.reply_text(
        f"Thank you, {full}! I have saved your phone number: {digits} ✅\n\nYou will not need to type it again.\n\nNow, how can we help you today? You can type, send a voice note, or send a picture of your wound.",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    full = context.user_data.get("full", "there")
    if choice == "book":
        await query.message.reply_text(f"{full}, to book an appointment, please send:\n\nWhat are you sick with?\n\nExample:\nFever and headache\n\nYou can also send a voice note or picture.")
    elif choice == "doctor":
        await query.message.reply_text(f"{full}, to talk to a doctor, just send a voice note or type your problem here. We will forward it to the doctor.\n\nOr call us directly: {PHONE}")
    elif choice == "hours":
        await query.message.reply_text("🕒 Opening Hours:\n\nMon - Fri: 8am - 8pm\nSaturday: 9am - 5pm\nSunday: Closed\n\nEmergency is open 24/7")
    elif choice == "location":
        await query.message.reply_text("📍 Our Location:\n\nH&S Health Care, Lagos, Nigeria.\n\nSend us your area and we will send directions.")
    elif choice == "emergency":
        await query.message.reply_text(f"🚨 EMERGENCY:\n\nCall us NOW: {PHONE}\n\nIf it is serious, go to nearest hospital immediately.")

# --- NEW: VOICE NOTE HANDLER ---
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full, phone, username_text, user_id = get_patient_info(update, context)
    # If no phone yet, ask for it first
    if not context.user_data.get("phone"):
        await update.message.reply_text("Welcome! Before we continue, what is your name please?")
        return NAME

    await update.message.reply_text(f"Thank you, {full}. I have received your voice note. I am sending it to the doctor now. Please wait a little 🙏\n\nIf your voice was not clear, please send it again slowly.")

    caption = (
        f"🎤 NEW VOICE NOTE FROM PATIENT\n\n"
        f"Name: {full}\n"
        f"Telegram Username: {username_text}\n"
        f"Phone Number: {phone}\n"
        f"User ID: {user_id}\n\n"
        f"Please listen and reply. Patient speaks any language - English, Pidgin, Yoruba, Igbo, Hausa."
    )

    # Forward voice to hospital group + doctor
    voice = update.message.voice
    if HOSPITAL_GROUP_ID:
        try:
            await context.bot.send_voice(chat_id=HOSPITAL_GROUP_ID, voice=voice.file_id, caption=caption)
        except Exception as e:
            print(f"Group voice failed: {e}")
            await context.bot.send_message(chat_id=HOSPITAL_GROUP_ID, text=caption)
            await context.bot.forward_message(chat_id=HOSPITAL_GROUP_ID, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
    if DOCTOR_CHAT_ID:
        try:
            await context.bot.send_voice(chat_id=DOCTOR_CHAT_ID, voice=voice.file_id, caption=caption)
        except Exception as e:
            print(f"Doctor voice failed: {e}")
            await context.bot.send_message(chat_id=DOCTOR_CHAT_ID, text=caption)
            await context.bot.forward_message(chat_id=DOCTOR_CHAT_ID, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)

    # Try transcription if OpenAI key exists (understands many languages, even weak voice)
    if OPENAI_API_KEY:
        try:
            import tempfile, requests
            file = await context.bot.get_file(voice.file_id)
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
                await file.download_to_drive(tf.name)
                audio_path = tf.name
            with open(audio_path, "rb") as f:
                r = requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    files={"file": f},
                    data={"model": "whisper-1"},
                    timeout=60
                )
            if r.status_code == 200:
                text_transcribed = r.json().get("text", "")
                if text_transcribed:
                    trans_msg = f"📝 Transcription (auto-detected language):\n{text_transcribed}\n\nPatient: {full} | Phone: {phone}"
                    await send_to_hospital(context, trans_msg)
                    await update.message.reply_text(f"I heard you say: \"{text_transcribed}\"\n\nIs that correct? If not, please send again slowly.")
                else:
                    await update.message.reply_text("Sorry, I could not hear you well. Can you please speak again slowly and a little louder?")
            else:
                await update.message.reply_text("Sorry mama/papa, I did not hear you well. Can you please speak again slowly?")
        except Exception as e:
            print(f"Transcription failed: {e}")
            await update.message.reply_text("I have sent your voice to the doctor. If it was not clear, please send again slowly.")

# --- NEW: PHOTO HANDLER ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full, phone, username_text, user_id = get_patient_info(update, context)
    if not context.user_data.get("phone"):
        await update.message.reply_text("Welcome! Before we continue, what is your name please?")
        return NAME

    await update.message.reply_text(f"Thank you, {full}. I have received your picture. I am sending it to the hospital and doctor now. 📸")

    caption_text = update.message.caption or "No description"
    caption = (
        f"🚨 NEW PATIENT PICTURE\n\n"
        f"Name: {full}\n"
        f"Telegram Username: {username_text}\n"
        f"Phone Number: {phone}\n"
        f"User ID: {user_id}\n"
        f"Patient Message: {caption_text}\n\n"
        f"Please check and call patient."
    )
    photo = update.message.photo[-1]  # highest quality
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
    # Forward text message to hospital too
    if context.user_data.get("phone"):
        full2, phone2, username_text, user_id = get_patient_info(update, context)
        msg = f"💬 NEW MESSAGE FROM PATIENT\n\nName: {full2}\nUsername: {username_text}\nPhone: {phone2}\nMessage: {update.message.text}"
        await send_to_hospital(context, msg)
    await update.message.reply_text(
        f"Thank you, {full}! We have received your message. Our team will contact you soon on {phone}.\n\nSend /start to see the menu again.",
        reply_markup=main_menu()
    )

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
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
    app.add_handler(CallbackQueryHandler(button_click))
    # Voice and Photo must come BEFORE text handler
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    print("Bot started...")
    asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling()

if __name__ == "__main__":
    main()
