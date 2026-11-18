import os, threading, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes, PicklePersistence

TOKEN = os.environ.get("BOT_TOKEN")
PHONE = "+2348076446822"
HOSPITAL_GROUP_ID = os.environ.get("HOSPITAL_GROUP_ID") or os.environ.get("GROUP_ID")
DOCTOR_CHAT_ID = os.environ.get("DOCTOR_CHAT_ID")

NAME, PHONE_STATE = range(2)

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
    # clean "my name is Samuel" -> "Samuel"
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

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    name = context.user_data.get("name","there")
    m = {
        "book": f"{name}, to book, please tell me what is wrong. Example: Fever and headache.",
        "doctor": f"{name}, please tell me what is wrong. You can type, send voice note, or picture. I will send it to the doctor now.",
        "hours": "🕒 Mon-Fri: 8am-8pm\nSat: 9am-5pm\nSun: Closed\nEmergency 24/7",
        "location": "📍 H&S Health Care, Lagos, Nigeria.",
        "emergency": f"🚨 EMERGENCY: Call NOW {PHONE}\nIf serious, go to nearest hospital immediately."
    }
    await q.message.reply_text(m.get(q.data,""))

async def forward_to_hospital(context, update, text, kind="MESSAGE"):
    name = context.user_data.get("name","Patient")
    phone = context.user_data.get("phone","Not provided")
    user = update.effective_user
    username = f"@{user.username}" if user.username else "No username"
    link = f"https://t.me/{user.username}" if user.username else None
    kb = None
    btns = []
    if link: btns.append([InlineKeyboardButton("💬 CHAT PATIENT NOW", url=link)])
    clean = re.sub(r"[^\d+]", "", str(phone))
    if clean: btns.append([InlineKeyboardButton("📞 CALL PATIENT", url=f"tel:{clean}")])
    if btns: kb = InlineKeyboardMarkup(btns)
    msg = f"🆕 NEW PATIENT - {kind}\n\nName: {name}\nPhone: {phone}\nUsername: {username}\nUser ID: {user.id}\nMessage: {text}"
    print(f"Forwarding to group={HOSPITAL_GROUP_ID} doctor={DOCTOR_CHAT_ID}", flush=True)
    if HOSPITAL_GROUP_ID:
        try: await context.bot.send_message(chat_id=int(HOSPITAL_GROUP_ID), text=msg, reply_markup=kb)
        except Exception as e: print(f"Group failed: {e}", flush=True)
    if DOCTOR_CHAT_ID:
        try: await context.bot.send_message(chat_id=int(DOCTOR_CHAT_ID), text=msg, reply_markup=kb)
        except Exception as e: print(f"Doctor failed: {e}", flush=True)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # 1 - if no name yet, treat as name
    if not context.user_data.get("name"):
        if text.strip().lower() in ["hi","hello","hey","good morning","good afternoon"]:
            await update.message.reply_text("Hello! Welcome to H&S Health Care 🏥\n\nWhat is your name please?")
            return
        return await get_name(update, context)
    # 2 - if no phone yet, treat as phone
    if not context.user_data.get("phone"):
        return await get_phone(update, context)
    # 3 - already registered: FORWARD IMMEDIATELY
    await forward_to_hospital(context, update, text, "MESSAGE")
    await update.message.reply_text(f"Thank you, {context.user_data.get('name')} 🙏\n\nI have sent your message to the doctor. A doctor will reply you here soon.\n\nWhile you wait, rest and drink water. If it gets worse, call {PHONE}.", reply_markup=menu())

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("phone"):
        await update.message.reply_text("Welcome! What is your name please?")
        return
    name = context.user_data.get("name"); phone = context.user_data.get("phone")
    user = update.effective_user
    caption = f"🎤 NEW VOICE NOTE\n\nName: {name}\nPhone: {phone}\nUsername: @{user.username if user.username else 'No username'}\nUser ID: {user.id}"
    if HOSPITAL_GROUP_ID:
        try: await context.bot.send_voice(chat_id=int(HOSPITAL_GROUP_ID), voice=update.message.voice.file_id, caption=caption)
        except Exception as e: print(f"Group voice failed: {e}", flush=True)
    if DOCTOR_CHAT_ID:
        try: await context.bot.send_voice(chat_id=int(DOCTOR_CHAT_ID), voice=update.message.voice.file_id, caption=caption)
        except Exception as e: print(f"Doctor voice failed: {e}", flush=True)
    await update.message.reply_text(f"Thank you, {name} 🙏 Voice note sent to doctor. Doctor will reply you here soon.", reply_markup=menu())

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("phone"):
        await update.message.reply_text("Welcome! What is your name please?")
        return
    name = context.user_data.get("name"); phone = context.user_data.get("phone")
    user = update.effective_user
    caption = f"📸 NEW PICTURE\n\nName: {name}\nPhone: {phone}\nUsername: @{user.username if user.username else 'No username'}\nUser ID: {user.id}\nMessage: {update.message.caption or ''}"
    if HOSPITAL_GROUP_ID:
        try: await context.bot.send_photo(chat_id=int(HOSPITAL_GROUP_ID), photo=update.message.photo[-1].file_id, caption=caption)
        except Exception as e: print(f"Group photo failed: {e}", flush=True)
    if DOCTOR_CHAT_ID:
        try: await context.bot.send_photo(chat_id=int(DOCTOR_CHAT_ID), photo=update.message.photo[-1].file_id, caption=caption)
        except Exception as e: print(f"Doctor photo failed: {e}", flush=True)
    await update.message.reply_text(f"Thank you, {name} 🙏 Picture sent to doctor. Doctor will reply you here soon.", reply_markup=menu())

async def set_cmd(app):
    await app.bot.set_my_commands([BotCommand("start","Start"),BotCommand("book","Book appointment"),BotCommand("doctor","Talk to doctor"),BotCommand("emergency","Emergency"),BotCommand("hours","Opening hours"),BotCommand("location","Location")])

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    app = Application.builder().token(TOKEN).persistence(PicklePersistence(filepath="bot_data.pkl")).build()
    app.post_init = set_cmd
    conv = ConversationHandler(entry_points=[CommandHandler("start", start)], states={NAME:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)], PHONE_STATE:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)]}, fallbacks=[], persistent=True, name="hs")
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bot started...", flush=True)
    app.run_polling()

if __name__ == "__main__":
    main()
