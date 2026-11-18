import os, threading, asyncio, re, json, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")
PHONE = "+2348076446822"
HOSPITAL_GROUP_ID = os.environ.get("HOSPITAL_GROUP_ID")
DOCTOR_CHAT_ID = os.environ.get("DOCTOR_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

NAME, TITLE, PHONE_STATE = range(3)

MALE_NAMES = {"samuel","john","michael","david","daniel","joseph","emmanuel","chinedu","chidi","emeka","obinna","oluwaseun","tunde","segun","ade","adebayo","kunle","femi","bayo","ifeanyi","chukwu","eze","uchenna","olamide","temitope","ayodele","ibrahim","musa","usman","abdul","ahmed","yusuf","peter","paul","james","andrew","matthew","mark","luke","joshua","caleb","isaac","jacob","moses","elijah","gabriel","victor","frank","charles","henry","george","thomas","william","richard","robert","anthony","kevin","chris","christopher","nicholas","stephen","philip","timothy","benjamin","austin","kenneth"}
FEMALE_NAMES = {"ada","adaeze","adaobi","ngozi","nkechi","chioma","amara","chiamaka","funke","folake","tola","toluwani","adeola","bisi","yetunde","omolara","kemi","simisola","temilade","oluwatoyin","aisha","fatima","maryam","zainab","halima","amina","mary","grace","faith","hope","joy","peace","blessing","mercy","esther","ruth","sarah","hannah","rebecca","rachel","deborah","elizabeth","victoria","janet","susan","linda","karen","nancy","betty","doris","patricia","barbara","jessica","amanda","emily","sophia","olivia","isabella","mia","ella","ava","chidinma","uchechi"}

class MyBaseHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Bot is alive")
    def log_message(self, *args): pass

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), MyBaseHTTPRequestHandler).serve_forever()

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Book Appointment", callback_data="book")],
        [InlineKeyboardButton("👨‍⚕️ Talk to Doctor", callback_data="doctor")],
        [InlineKeyboardButton("🕒 Opening Hours", callback_data="hours")],
        [InlineKeyboardButton("📍 Location", callback_data="location")],
        [InlineKeyboardButton("🚨 Emergency", callback_data="emergency")],
    ])

def title_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Mr", callback_data="title_Mr"), InlineKeyboardButton("Mrs", callback_data="title_Mrs")],
        [InlineKeyboardButton("Miss", callback_data="title_Miss")],
    ])

def clean_name(text):
    t = text.strip()
    t = re.sub(r"(?i)^(my name is|my name's|my name|i'm|i am|call me|it is|it's)\s+", "", t)
    t = t.strip().strip(".").strip()
    parts = t.split()
    name = " ".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else t)
    return " ".join([w.capitalize() for w in name.split()])

def guess_title(name):
    first = name.split()[0].lower() if name else ""
    if first in MALE_NAMES: return "Mr"
    if first in FEMALE_NAMES: return "Mrs"
    return None

def get_patient_info(update, context):
    full = context.user_data.get("full", "Patient")
    phone = context.user_data.get("phone", "Not provided")
    username = update.effective_user.username
    username_text = f"@{username}" if username else "No username"
    return full, phone, username_text, update.effective_user.id

def build_patient_chat(update):
    username = update.effective_user.username
    user_id = update.effective_user.id
    if username:
        return f"@{username}\nChat Link: https://t.me/{username}", f"https://t.me/{username}"
    return f"No username - User ID: {user_id} (Ask patient to set username)", None

def build_patient_keyboard(chat_url, phone):
    buttons = []
    if chat_url: buttons.append([InlineKeyboardButton("💬 CHAT PATIENT NOW", url=chat_url)])
    if phone and phone not in ["Not provided","Not saved yet"]:
        clean_phone = re.sub(r"[^\d+]", "", str(phone))
        if clean_phone: buttons.append([InlineKeyboardButton("📞 CALL PATIENT", url=f"tel:{clean_phone}")])
    return InlineKeyboardMarkup(buttons) if buttons else None

async def send_to_hospital(context, text, reply_markup=None):
    if HOSPITAL_GROUP_ID:
        try: await context.bot.send_message(chat_id=HOSPITAL_GROUP_ID, text=text, reply_markup=reply_markup)
        except Exception as e: print(f"Group send failed: {e}", flush=True)
    if DOCTOR_CHAT_ID:
        try: await context.bot.send_message(chat_id=DOCTOR_CHAT_ID, text=text, reply_markup=reply_markup)
        except Exception as e: print(f"Doctor send failed: {e}", flush=True)

def ask_ai(user_text, history, patient_name):
    if not GEMINI_API_KEY:
        return None
    try:
        if GEMINI_API_KEY.startswith("sk-"):
            return None
        prompt = f"""You are a warm, caring Nigerian nurse receptionist for H&S Health Care in Lagos. Patient name is {patient_name}. Speak like a kind human nurse, short replies, 2-3 sentences max, simple English, some Naija warmth. Ask ONE follow-up question at a time. If patient says hello/hi, greet warmly and ask how they are feeling and what is wrong. If they describe symptoms, show empathy, ask when it started, if fever/pain/vomiting, reassure doctor will see it. Never diagnose definitively or prescribe dosage. If emergency symptoms (difficulty breathing, heavy bleeding, unconscious, severe chest pain), tell them to call +2348076446822 NOW and go to hospital immediately. Always encourage them to tell more.
Conversation so far:
"""
        for h in history[-6:]:
            role = "Patient" if h["role"]=="user" else "Nurse"
            prompt += f"{role}: {h['content']}\n"
        prompt += f"Patient: {user_text}\nNurse:"
        data = json.dumps({"contents":[{"parts":[{"text": prompt}]}]}).encode()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.loads(r.read().decode())
            return res["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"AI failed: {e}", flush=True)
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("phone"):
        full = context.user_data.get("full", "there")
        await update.message.reply_text(f"Welcome back, {full} 😊\n\nHow are you feeling today? How can we help you?", reply_markup=main_menu())
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
    query = update.callback_query; await query.answer()
    title = query.data.replace("title_", "")
    name = context.user_data.get("name", "")
    context.user_data["title"] = title; context.user_data["full"] = f"{title} {name}"
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
    await update.message.reply_text(f"Thank you, {full}! I have saved your phone number: {digits} ✅\n\nNow tell me, how are you feeling today? What is wrong? You can type, send a voice note, or send a picture. I'm listening.", reply_markup=main_menu())
    return ConversationHandler.END

async def book_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"{context.user_data.get('full','there')}, to book an appointment, please send:\n\nWhat are you sick with?\n\nExample:\nFever and headache\n\nYou can also send a voice note or picture.")

async def doctor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"{context.user_data.get('full','there')}, to talk to a doctor, just send a voice note or type your problem here. We will forward it to the doctor.\n\nOr call us directly: {PHONE}")

async def emergency_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🚨 EMERGENCY:\n\nCall us NOW: {PHONE}\n\nIf it is serious, go to nearest hospital immediately.")

async def hours_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🕒 Opening Hours:\n\nMon - Fri: 8am - 8pm\nSaturday: 9am - 5pm\nSunday: Closed\n\nEmergency is open 24/7")

async def location_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📍 Our Location:\n\nH&S Health Care, Lagos, Nigeria.\n\nSend us your area and we will send directions.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ How to use this bot:\n\n1. Type /start to start\n2. Type your name and phone number once\n3. After that, you can:\n   - Type your problem\n   - Send a VOICE NOTE in any language\n   - Send a PICTURE of your wound\n\nCommands:\n/book - Book appointment\n/doctor - Talk to doctor\n/emergency - Emergency\n/hours - Opening hours\n/location - Location", reply_markup=main_menu())

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    choice = query.data; full = context.user_data.get("full", "there")
    msgs = {"book": f"{full}, to book an appointment, please send:\n\nWhat are you sick with?\n\nExample:\nFever and headache\n\nYou can also send a voice note or picture.",
            "doctor": f"{full}, to talk to a doctor, just send a voice note or type your problem here. We will forward it to the doctor.\n\nOr call us directly: {PHONE}",
            "hours": "🕒 Opening Hours:\n\nMon - Fri: 8am - 8pm\nSaturday: 9am - 5pm\nSunday: Closed\n\nEmergency is open 24/7",
            "location": "📍 Our Location:\n\nH&S Health Care, Lagos, Nigeria.\n\nSend us your area and we will send directions.",
            "emergency": f"🚨 EMERGENCY:\n\nCall us NOW: {PHONE}\n\nIf it is serious, go to nearest hospital immediately."}
    await query.message.reply_text(msgs.get(choice, ""))

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full, phone, username_text, user_id = get_patient_info(update, context)
    if not context.user_data.get("phone"):
        await update.message.reply_text("Welcome! Before we continue, what is your name please?")
        return NAME
    await update.message.reply_text(f"Thank you, {full}, I heard your voice note 🙏 I have sent it to the doctor now.\n\nHow are you feeling now? Are you in pain? Can you tell me more about what you are feeling? I'm listening, you can send another voice note.")
    link_text, chat_url = build_patient_chat(update)
    keyboard = build_patient_keyboard(chat_url, phone)
    caption = f"🎤 NEW VOICE NOTE FROM PATIENT\n\nName: {full}\nUsername: {username_text}\nPatient: {link_text}\nPhone: {phone}\nUser ID: {user_id}\n\nTap CHAT PATIENT NOW below to reply directly"
    voice = update.message.voice
    if HOSPITAL_GROUP_ID:
        try: await context.bot.send_voice(chat_id=HOSPITAL_GROUP_ID, voice=voice.file_id, caption=caption, reply_markup=keyboard)
        except Exception as e: print(f"Group voice failed: {e}", flush=True)
    if DOCTOR_CHAT_ID:
        try: await context.bot.send_voice(chat_id=DOCTOR_CHAT_ID, voice=voice.file_id, caption=caption, reply_markup=keyboard)
        except Exception as e: print(f"Doctor voice failed: {e}", flush=True)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full, phone, username_text, user_id = get_patient_info(update, context)
    if not context.user_data.get("phone"):
        await update.message.reply_text("Welcome! Before we continue, what is your name please?")
        return NAME
    await update.message.reply_text(f"Thank you, {full}, I have seen your picture 📸 I have sent it to the doctor now.\n\nHow are you feeling now? Is the pain getting worse? When did it start? Please tell me more, I'm here to help you.")
    caption_text = update.message.caption or "No description"
    link_text, chat_url = build_patient_chat(update)
    keyboard = build_patient_keyboard(chat_url, phone)
    caption = f"🚨 NEW PATIENT PICTURE\n\nName: {full}\nUsername: {username_text}\nPatient: {link_text}\nPhone: {phone}\nUser ID: {user_id}\nMessage: {caption_text}\n\nTap CHAT PATIENT NOW below to reply directly"
    photo = update.message.photo[-1]
    if HOSPITAL_GROUP_ID:
        try: await context.bot.send_photo(chat_id=HOSPITAL_GROUP_ID, photo=photo.file_id, caption=caption, reply_markup=keyboard)
        except Exception as e: print(f"Group photo failed: {e}", flush=True)
    if DOCTOR_CHAT_ID:
        try: await context.bot.send_photo(chat_id=DOCTOR_CHAT_ID, photo=photo.file_id, caption=caption, reply_markup=keyboard)
        except Exception as e: print(f"Doctor photo failed: {e}", flush=True)

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not context.user_data.get("phone"):
        if text.strip().lower() in ["hello","hi","hey","good morning","good afternoon","good evening","hello o","hi o"]:
            await update.message.reply_text("Hello! Welcome to H&S Health Care 🏥😊\n\nHow are you feeling today? What is your name please?")
            return NAME
        await update.message.reply_text("Welcome to H&S Health Care 🏥\n\nWhat is your name please?")
        return NAME
    full = context.user_data.get("full", "there")
    full2, phone2, username_text, user_id = get_patient_info(update, context)
    link_text, chat_url = build_patient_chat(update)
    keyboard = build_patient_keyboard(chat_url, phone2)
    msg = f"💬 NEW MESSAGE FROM PATIENT\n\nName: {full2}\nUsername: {username_text}\nPatient: {link_text}\nPhone: {phone2}\nUser ID: {user_id}\nMessage: {text}\n\nTap CHAT PATIENT NOW below to reply directly"
    await send_to_hospital(context, msg, reply_markup=keyboard)
    history = context.user_data.get("history", [])
    ai_reply = await asyncio.to_thread(ask_ai, text, history, full)
    history.append({"role":"user","content":text})
    if ai_reply:
        history.append({"role":"assistant","content":ai_reply})
        context.user_data["history"] = history[-10:]
        await update.message.reply_text(ai_reply, reply_markup=main_menu())
    else:
        await update.message.reply_text(f"Thank you for telling me, {full} 🙏\n\nI have sent your message to the doctor already.\n\nHow are you feeling now? Is it getting better or worse?\n\nPlease tell me more - when did it start? Do you have fever, pain, or any other symptom? You can type, send a voice note, or send a picture. I'm here with you.", reply_markup=main_menu())

async def set_bot_commands(app):
    commands = [BotCommand("start","Start bot and get help"),BotCommand("book","Book appointment"),BotCommand("doctor","Talk to doctor"),BotCommand("emergency","Emergency number"),BotCommand("hours","Opening hours"),BotCommand("location","Hospital location"),BotCommand("help","How to use bot")]
    await app.bot.set_my_commands(commands)

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.post_init = set_bot_commands
    conv = ConversationHandler(entry_points=[CommandHandler("start", start)], states={NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)], TITLE:[CallbackQueryHandler(get_title, pattern="^title_")], PHONE_STATE:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)]}, fallbacks=[])
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
    print("Bot started...", flush=True)
    asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling()

if __name__ == "__main__":
    main()
