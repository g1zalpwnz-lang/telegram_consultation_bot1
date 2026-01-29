import os
import json
import logging
from datetime import datetime, timedelta
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

from google.oauth2 import service_account
from googleapiclient.discovery import build

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Задаём переменные окружения в Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "617492"))
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

# Загружаем сервисный аккаунт
SERVICE_ACCOUNT_INFO = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=["https://www.googleapis.com/auth/calendar"]
)

CALENDAR_ID = os.getenv("CALENDAR_ID")  # сюда нужно вставить id календаря

service = build("calendar", "v3", credentials=credentials)

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# --- Вспомогательные функции ---
def get_next_working_days(n=5):
    today = datetime.now(MOSCOW_TZ)
    days = []
    delta = 0
    while len(days) < n:
        day = today + timedelta(days=delta)
        if day.weekday() < 5:  # 0-4 = понедельник-пятница
            days.append(day)
        delta += 1
    return days

def generate_time_slots():
    """Слоты каждые 30 минут с 9:00 до 16:00"""
    slots = []
    for hour in range(9, 17):
        slots.append(f"{hour:02d}:00")
        slots.append(f"{hour:02d}:30")
    return slots

def build_days_keyboard():
    buttons = []
    for day in get_next_working_days():
        day_str = day.strftime("%d.%m")
        buttons.append([InlineKeyboardButton(day_str, callback_data=day_str)])
    return InlineKeyboardMarkup(buttons)

def build_slots_keyboard(day_str):
    buttons = []
    for slot in generate_time_slots():
        buttons.append([InlineKeyboardButton(slot, callback_data=f"{day_str} {slot}")])
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите дату для консультации:",
        reply_markup=build_days_keyboard()
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Если выбрана дата
    if len(data) == 5 and data[2] == '.':  # формат дд.мм
        day_str = data
        await query.edit_message_text(
            text=f"Выберите время для {day_str}:",
            reply_markup=build_slots_keyboard(day_str)
        )
    else:  # выбрано время
        day_str, time_str = data.split()
        user_name = query.from_user.full_name
        event_start = datetime.strptime(f"{day_str}.{datetime.now().year} {time_str}", "%d.%m.%Y %H:%M")
        event_start = MOSCOW_TZ.localize(event_start)
        event_end = event_start + timedelta(minutes=30)

        event = {
            "summary": f"Консультация с {user_name}",
            "start": {"dateTime": event_start.isoformat(), "timeZone": "Europe/Moscow"},
            "end": {"dateTime": event_end.isoformat(), "timeZone": "Europe/Moscow"},
        }

        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

        await query.edit_message_text(
            text=f"Запись подтверждена: {day_str} {time_str}"
        )

        # Отправляем уведомление админу
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"Новая запись: {user_name}, {day_str} {time_str}"
        )

# --- Запуск бота ---
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

print("Бот запущен...")
app.run_polling()
