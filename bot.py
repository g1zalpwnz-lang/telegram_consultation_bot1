import os
import json
import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from google.oauth2 import service_account
from googleapiclient.discovery import build

# ===== Настройка логирования =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== Telegram =====
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# ===== Google Calendar =====
SERVICE_ACCOUNT_JSON = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
CALENDAR_ID = "bot-calendar@exalted-etching-485813-r4.iam.gserviceaccount.com"

credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_JSON,
    scopes=["https://www.googleapis.com/auth/calendar"]
)

calendar_service = build("calendar", "v3", credentials=credentials)

# ===== Генерация слотов =====
def generate_slots():
    slots = []
    start_hour = 9
    end_hour = 16
    duration_minutes = 30

    now = datetime.now()
    for day_offset in range(5):  # ближайшие 5 рабочих дней
        day = now + timedelta(days=day_offset)
        if day.weekday() >= 5:
            continue  # пропускаем выходные
        for hour in range(start_hour, end_hour):
            slots.append(datetime(day.year, day.month, day.day, hour, 0))
            slots.append(datetime(day.year, day.month, day.day, hour, 30))
    return slots

available_slots = generate_slots()

# ===== Добавление события в календарь =====
def add_event_to_calendar(summary, start_time, end_time):
    event = {
        "summary": summary,
        "start": {"dateTime": start_time.isoformat(), "timeZone": "Europe/Moscow"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "Europe/Moscow"},
    }
    calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

# ===== Команды Telegram =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(slot.strftime("%d.%m %H:%M"), callback_data=str(i))]
        for i, slot in enumerate(available_slots[:10])  # показываем 10 ближайших слотов
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите слот для консультации:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot_index = int(query.data)
    slot_time = available_slots.pop(slot_index)

    # Добавляем событие в календарь
    add_event_to_calendar("Консультация", slot_time, slot_time + timedelta(minutes=30))

    # Отправляем уведомление в Telegram
    await context.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"Новая запись на консультацию: {slot_time.strftime('%d.%m %H:%M')}"
    )
    await query.edit_message_text(f"Вы записаны на консультацию: {slot_time.strftime('%d.%m %H:%M')}")

# ===== Запуск бота =====
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    print("Бот запущен!")
    app.run_polling()
