import os
import json
import logging
from datetime import datetime, timedelta
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Админ
ADMIN_ID = 617492

# Чтение сервисного аккаунта из переменной окружения
SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
if not SERVICE_ACCOUNT_JSON:
    raise ValueError("Переменная окружения GOOGLE_SERVICE_ACCOUNT_JSON не найдена!")

SERVICE_ACCOUNT_INFO = json.loads(SERVICE_ACCOUNT_JSON)
SERVICE_ACCOUNT_INFO["private_key"] = SERVICE_ACCOUNT_INFO["private_key"].replace("\\n", "\n")

# Настройка Google Calendar API
credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=["https://www.googleapis.com/auth/calendar"]
)
calendar_service = build("calendar", "v3", credentials=credentials)
CALENDAR_ID = "primary"  # Или свой календарь

# Временная зона Москва
MOSCOW = pytz.timezone("Europe/Moscow")

def get_working_days(n=5):
    days = []
    current = datetime.now(MOSCOW)
    while len(days) < n:
        if current.weekday() < 5:  # Пн-Пт
            days.append(current)
        current += timedelta(days=1)
    return days

def generate_slots():
    slots = []
    for day in get_working_days(5):
        for hour in range(9, 16):
            slots.append(day.replace(hour=hour, minute=0, second=0, microsecond=0))
            slots.append(day.replace(hour=hour, minute=30, second=0, microsecond=0))
    return slots

def format_datetime(dt):
    return dt.strftime("%d.%m %H:%M")

def create_buttons(slots):
    buttons = []
    for slot in slots:
        buttons.append([InlineKeyboardButton(format_datetime(slot), callback_data=slot.isoformat())])
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    slots = generate_slots()
    keyboard = create_buttons(slots)
    await update.message.reply_text("Выберите дату и время:", reply_markup=keyboard)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot_time = datetime.fromisoformat(query.data)
    # Создание события в Google Calendar
    event = {
        'summary': f'Запись от {query.from_user.first_name}',
        'start': {'dateTime': slot_time.isoformat(), 'timeZone': 'Europe/Moscow'},
        'end': {'dateTime': (slot_time + timedelta(minutes=30)).isoformat(), 'timeZone': 'Europe/Moscow'},
    }
    calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    await query.edit_message_text(text=f"Вы записаны на {format_datetime(slot_time)}")
    # Уведомление админа
    await context.bot.send_message(ADMIN_ID, f"Новая запись: {query.from_user.full_name} на {format_datetime(slot_time)}")

def main():
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        raise ValueError("Переменная окружения TELEGRAM_TOKEN не найдена!")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()

if __name__ == "__main__":
    main()
