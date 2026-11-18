import os, threading, re, asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes, PicklePersistence

TOKEN = os.environ.get("BOT_TOKEN")
PHONE = "+2348076446822"
HOSPITAL_GROUP_ID = os.environ.get("HOSPITAL_GROUP_ID") or os.environ.get("GROUP_ID")
DOCTOR_CHAT_ID = os.environ.get("DOCTOR_CHAT_ID")

NAME, PHONE_STATE, BOOK_SYMPTOM, BOOK_DAY, BOOK_TIME = range(5)

EMERGENCY_WORDS = ["bleed", "bleeding", "blood", "chest pain", "can't breathe", "cannot breathe", "cant breathe", "difficulty breathing", "breathing problem", "unconscious", "fainted", "faint", "collapsed", "collapse", "accident", "stab", "stabbed", "broken", "fracture", "seizure", "convulsion", "choking", "choke", "poison", "suicide", "overdose", "burn", "electrocut", "drowning"]

def is_emergency(text):
    t = text.lower()
    return any(w in t for w in EMERGENCY_WORDS)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Bot is alive")
    def log_message(self,*a): pass

def keep_alive():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT",10000))), H).serve_forever()

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Book Appointment", callback_data="book")],
        [InlineKeyboardButton("👨‍⚕️ Talk to Doctor", callback_data="doctor")],
        [InlineKeyboardButton("🕒 Opening Hours", callback_data="hours")],
        [InlineKeyboardButton("📍 Location", callback_data="location")],
        [InlineKeyboardButton("🚨 Emergency", callback_data="emergency")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("phone"):
        await update.message.reply_text(f"Welcome back, {context.user_data.get('name','')} 😊", reply_markup=menu())
        return ConversationHandler.END
    await update.message.reply_text("Welcome to H&S Health Care 🏥\n\nWhat is your name please?")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip().title()
    name = re.sub(r"(?i)^(my name is|my name|i am|i'm|call me)\s+", "", name)
    context.user_data["name"] = name
    await update.message.reply_text(f"Nice to meet you, {name} 😊\n\nWhat is your phone number? Example: 08012345678")
    return PHONE_STATE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    digits = re.sub(r"[^\d+]", "", update.message.text.strip())
    if len(digits) < 10:
        await update.message.reply_text("That number looks too short. Please type again, e.g. 08012345678")
        return PHONE_STATE
    context.user_data["phone"] = digits
    await update.message.reply_text(f"Thank you, {context.user_data.get('name')}! ✅ Saved.\n\nWhat would you like to do?", reply_markup=menu())
    return ConversationHandler.END

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("What would you like to do?", reply_markup=menu())

async def book_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Let's book your appointment.\n\nWhat is wrong? Example: Fever and headache.")
    return BOOK_SYMPTOM

async def book_symptom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["book_symptom"] = update.message.text
    await update.message.reply_text("Which day do you want to come? Example: Tomorrow, Monday, 25 Nov")
    return BOOK_DAY

async def book_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["book_day"] = update.message.text
    await update.message.reply_text("What time? Example: 10am, 2pm")
    return BOOK_TIME

async def book_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["book_time"] = update.message.text
    name = context.user_data.get("name","Patient")
    phone = context.user_data.get("phone","")
    user = update.effective_user
    msg = f"📅 NEW BOOKING\n\nName: {name}\nPhone: {phone}\nUsername: @{user.username if user.username else 'No username'}\nUser ID: {user.id}\nProblem: {context.user_data.get('book_symptom')}\nDay: {context.user_data.get('book_day')}\nTime: {update.message.text}"
    if HOSPITAL_GROUP_ID:
        try: await context.bot.send_message(chat_id=int(HOSPITAL_GROUP_ID), text=msg)
        except Exception as e: print(e)
    if DOCTOR_CHAT_ID:
        try: await context.bot.send_message(chat_id=int(DOCTOR_CHAT_ID), text=msg)
        except Exception as e: print(e)
    await update.message.reply_text(f"✅ Done, {name}!\n\nYour appointment is booked for {context.user_data.get('book_day')} at {update.message.text}.\nProblem: {context.user_data.get('book_symptom')}\n\nHospital will confirm you soon. Type /menu to see options.")
    return ConversationHandler.END

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    name = context.user_data.get("name","there")
    if q.data == "book":
        await q.message.reply_text("📅 Let's book.\n\nWhat is wrong? Example: Fever and headache.")
        context.user_data["booking"] = True
        return
    if q.data == "doctor":
        await q.message.reply_text(f"{name}, please tell me what is wrong. You can type, send voice note, or picture. I will send it to the doctor now.")
        return
    m = {
        "hours": "🕒 Mon-Fri: 8am-8pm\nSat: 9am-5pm\nSun: Closed\nEmergency 24/7",
        "location": "📍 H&S Health Care, Lagos, Nigeria.",
        "emergency": f"🚨 EMERGENCY: Call NOW {PHONE}\nIf serious, go to nearest hospital immediately. Do not wait for chat."
    }
    await q.message.reply_text(m.get(q.data,""))

async def forward_to_hospital(context, update, text, kind="MESSAGE"):
    name = context.user_data.get("name","Patient")
    phone = context.user_data.get("phone","Not provided")
    user = update.effective_user
    username = f"@{user.username}" if user.username else "No username"
    link = f"https://t.me/{user.username}" if user.username else None
    btns = []
    if link: btns.append([InlineKeyboardButton("💬 CHAT PATIENT NOW", url=link)])
    kb = InlineKeyboardMarkup(btns) if btns else None
    emergency = is_emergency(text)
    title = "🚨 EMERGENCY - URGENT" if emergency else f"🆕 NEW PATIENT - {kind}"
    msg = f"{title}\n\nName: {name}\nPhone: {phone}\nUsername: {username}\nUser ID: {user.id}\nMessage: {text}\n\n--- To reply, type: /reply {user.id} your message"
    if HOSPITAL_GROUP_ID:
        try: await context.bot.send_message(chat_id=int(HOSPITAL_GROUP_ID), text=msg, reply_markup=kb)
        except Exception as e: print(f"Group failed: {e}")
    if DOCTOR_CHAT_ID:
        try: await context.bot.send_message(chat_id=int(DOCTOR_CHAT_ID), text=msg, reply_markup=kb)
        except Exception as e: print(f"Doctor failed: {e}")
    return emergency

async def reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only works in Hospital Group / Doctor chat
    if str(update.effective_chat.id) not in [str(HOSPITAL_GROUP_ID), str(DOCTOR_CHAT_ID)]:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Use: /reply USER_ID your message")
        return
    try:
        target = int(context.args[0])
        msg = " ".join(context.args[1:])
        await context.bot.send_message(chat_id=target, text=f"👨‍⚕️ Doctor reply:\n\n{msg}\n\nType /menu for options.")
        await update.message.reply_text("✅ Reply sent to patient.")
    except Exception as e:
        await update.message.reply_text(f"Failed: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # Booking flow check
    if context.user_data.get("booking"):
        if "book_symptom" not in context.user_data:
            context.user_data["book_symptom"] = text
            await update.message.reply_text("Which day do you want to come? Example: Tomorrow, Monday")
            return
        if "book_day" not in context.user_data:
            context.user_data["book_day"] = text
            await update.message.reply_text("What time? Example: 10am, 2pm")
            return
        # finish booking
        day = context.user_data.pop("book_day")
        symptom = context.user_data.pop("book_symptom")
        context.user_data.pop("booking", None)
        name = context.user_data.get("name","Patient"); phone = context.user_data.get("phone","")
        user = update.effective_user
        msg = f"📅 NEW BOOKING\n\nName: {name}\nPhone: {phone}\nUser ID: {user.id}\nProblem: {symptom}\nDay: {day}\nTime: {text}"
        if HOSPITAL_GROUP_ID:
            try: await context.bot.send_message(chat_id=int(HOSPITAL_GROUP_ID), text=msg)
            except: pass
        await update.message.reply_text(f"✅ Done, {name}! Booked for {day} at {text}. Hospital will confirm you soon. Type /menu")
        return
    if not context.user_data.get("name"):
        if text.strip().lower() in ["hi","hello","hey","good morning","good afternoon"]:
            await update.message.reply_text("Hello! Welcome to H&S Health Care 🏥\n\nWhat is your name please?")
            return
        return await get_name(update, context)
    if not context.user_data.get("phone"):
        return await get_phone(update, context)
    emergency = await forward_to_hospital(context, update, text, "MESSAGE")
    name = context.user_data.get("name")
    if emergency:
        await update.message.reply_text(f"🚨 {name}, this sounds like an EMERGENCY.\n\nI have sent it to the doctor as URGENT.\n\nPlease CALL NOW: {PHONE}\nIf serious, go to the nearest hospital immediately. Do not wait for a chat reply.")
    else:
        await update.message.reply_text(f"Thank you, {name} 🙏\n\nI have sent your message to the doctor. A doctor will reply you here soon.\n\nIf it gets worse, call {PHONE}. Type /menu for options.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("phone"):
        await update.message.reply_text("Welcome! What is your name please?"); return
    name = context.user_data.get("name"); phone = context.user_data.get("phone"); user = update.effective_user
    caption = f"🎤 NEW VOICE NOTE\n\nName: {name}\nPhone: {phone}\nUsername: @{user.username if user.username else 'No username'}\nUser ID: {user.id}\n\nTo reply: /reply {user.id} your message"
    if HOSPITAL_GROUP_ID:
        try: await context.bot.send_voice(chat_id=int(HOSPITAL_GROUP_ID), voice=update.message.voice.file_id, caption=caption)
        except: pass
    if DOCTOR_CHAT_ID:
        try: await context.bot.send_voice(chat_id=int(DOCTOR_CHAT_ID), voice=update.message.voice.file_id, caption=caption)
        except: pass
    await update.message.reply_text(f"Thank you, {name} 🙏 Voice note sent to doctor. Doctor will reply you here soon.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("phone"):
        await update.message.reply_text("Welcome! What is your name please?"); return
    name = context.user_data.get("name"); phone = context.user_data.get("phone"); user = update.effective_user
    caption = f"📸 NEW PICTURE\n\nName: {name}\nPhone: {phone}\nUsername: @{user.username if user.username else 'No username'}\nUser ID: {user.id}\nMessage: {update.message.caption or ''}\n\nTo reply: /reply {user.id} your message"
    if HOSPITAL_GROUP_ID:
        try: await context.bot.send_photo(chat_id=int(HOSPITAL_GROUP_ID), photo=update.message.photo[-1].file_id, caption=caption)
        except: pass
    if DOCTOR_CHAT_ID:
        try: await context.bot.send_photo(chat_id=int(DOCTOR_CHAT_ID), photo=update.message.photo[-1].file_id, caption=caption)
        except: pass
    await update.message.reply_text(f"Thank you, {name} 🙏 Picture sent to doctor. Doctor will reply you here soon.")

async def set_cmd(app):
    await app.bot.set_my_commands([BotCommand("start","Start"),BotCommand("menu","Show menu"),BotCommand("book","Book appointment"),BotCommand("doctor","Talk to doctor"),BotCommand("emergency","Emergency"),BotCommand("hours","Opening hours"),BotCommand("location","Location"),BotCommand("reply","Doctor reply")])

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    app = Application.builder().token(TOKEN).persistence(PicklePersistence(filepath="bot_data.pkl")).build()
    app.post_init = set_cmd
    conv = ConversationHandler(entry_points=[CommandHandler("start", start)], states={NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)], PHONE_STATE:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)]}, fallbacks=[], persistent=True, name="hs")
    app.add_handler(conv)
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CommandHandler("reply", reply_cmd))
    app.add_handler(CommandHandler("book", book_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot started...", flush=True)
    asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling()

if __name__ == "__main__":
    main()
