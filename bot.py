import os
import json
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --------- Настройки ---------
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ADMIN_ID = int(os.environ.get("TELEGRAM_ADMIN_ID", 0))  # твой Telegram ID
# JSON сервисного аккаунта
service_account_info_raw = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
service_account_info = json.loads(service_account_info_raw)
service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")

# --------- Google Calendar ---------
credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=["https://www.googleapis.com/auth/calendar"]
)
calendar_service = build("calendar", "v3", credentials=credentials)
CALENDAR_ID = service_account_info["client_email"]  # используем сервисный email

def add_event_to_calendar(summary, start_datetime, end_datetime):
    event = {
        "summary": summary,
        "start": {"dateTime": start_datetime.isoformat(), "timeZone": "Europe/Moscow"},
        "end": {"dateTime": end_datetime.isoformat(), "timeZone": "Europe/Moscow"},
    }
    calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

# --------- Генерация слотов ---------
def generate_slots():
    slots = []
    now = datetime.now()
    start_hour, end_hour = 9, 16
    for day in range(0, 7):  # на неделю вперед
        date = now + timedelta(days=day)
        if date.weekday() < 5:  # только рабочие дни
            for hour in range(start_hour, end_hour):
                start = datetime(date.year, date.month, date.day, hour, 0)
                end = start + timedelta(minutes=30)
                slots.append((start, end))
    return slots

SLOTS = generate_slots()

# --------- Telegram Bot Handlers ---------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"{s[0].strftime('%d.%m %H:%M')}", callback_data=str(i))]
        for i, s in enumerate(SLOTS)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите слот для консультации:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot_index = int(query.data)
    start, end = SLOTS[slot_index]
    add_event_to_calendar("Консультация", start, end)
    await query.edit_message_text(text=f"Вы записаны на {start.strftime('%d.%m %H:%M')}")

# --------- Основная часть ---------
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

if __name__ == "__main__":
    print("Слоты сгенерированы!")
    app.run_polling()
