import os
import json
from datetime import datetime, timedelta
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from google.oauth2 import service_account
from googleapiclient.discovery import build

# ===== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ =====
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])  # Telegram ID администратора
SERVICE_ACCOUNT_JSON = os.environ["SERVICE_ACCOUNT_JSON"]
CALENDAR_ID = os.environ["CALENDAR_ID"]  # id календаря Google

SERVICE_ACCOUNT_INFO = json.loads(SERVICE_ACCOUNT_JSON)

# ===== Google Calendar API =====
credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=["https://www.googleapis.com/auth/calendar"]
)
calendar_service = build("calendar", "v3", credentials=credentials)

# ===== ВРЕМЕННАЯ ЗОНА =====
moscow_tz = pytz.timezone("Europe/Moscow")

# ===== ФУНКЦИИ =====
def get_next_workdays(n=5):
    days = []
    dt = datetime.now(moscow_tz)
    while len(days) < n:
        if dt.weekday() < 5:  # Пн-Пт
            days.append(dt)
        dt += timedelta(days=1)
    return days

def generate_time_slots():
    slots = []
    for hour in range(9, 17):  # 9:00 - 16:30
        slots.append(f"{hour}:00")
        slots.append(f"{hour}:30")
    return slots

def generate_calendar_buttons():
    keyboard = []
    for day in get_next_workdays():
        text = day.strftime("%d.%m")
        keyboard.append([InlineKeyboardButton(text, callback_data=text)])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите дату для консультации:",
        reply_markup=generate_calendar_buttons()
    )

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data
    context.user_data["selected_date"] = date_str

    keyboard = [[InlineKeyboardButton(slot, callback_data=slot)] for slot in generate_time_slots()]
    await query.edit_message_text(
        text=f"Выберите время для {date_str}:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = context.user_data["selected_date"]
    time_str = query.data

    dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m %H:%M")
    dt = moscow_tz.localize(dt)

    # Создаём событие в Google Calendar
    event = {
        "summary": "Консультация",
        "start": {"dateTime": dt.isoformat(), "timeZone": "Europe/Moscow"},
        "end": {"dateTime": (dt + timedelta(minutes=30)).isoformat(), "timeZone": "Europe/Moscow"},
    }
    calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

    # Уведомление админу
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"Новая консультация: {date_str} {time_str}")

    await query.edit_message_text(text=f"Консультация записана на {date_str} {time_str}")

# ===== Основной запуск =====
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(select_date, pattern=r"\d{2}\.\d{2}"))
app.add_handler(CallbackQueryHandler(select_time, pattern=r"\d{1,2}:\d{2}"))

app.run_polling()
