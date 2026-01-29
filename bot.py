import os
import json
from datetime import datetime, timedelta
import sqlite3

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes

from google.oauth2 import service_account
from googleapiclient.discovery import build

# --------------------------
# ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# --------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_ID = int(os.environ.get("TELEGRAM_ADMIN_ID"))
GOOGLE_SERVICE_ACCOUNT_JSON = json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"))
GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID")

# --------------------------
# ИНИЦИАЛИЗАЦИЯ GOOGLE CALENDAR
# --------------------------
credentials = service_account.Credentials.from_service_account_info(
    GOOGLE_SERVICE_ACCOUNT_JSON,
    scopes=["https://www.googleapis.com/auth/calendar"]
)
calendar_service = build('calendar', 'v3', credentials=credentials)

# --------------------------
# ИНИЦИАЛИЗАЦИЯ SQLITE
# --------------------------
conn = sqlite3.connect('slots.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start TEXT,
    end TEXT
)
''')
conn.commit()

# --------------------------
# СЛОТЫ
# --------------------------
SLOTS = []
WORK_HOURS_START = 9
WORK_HOURS_END = 16
SLOT_DURATION = 30  # минут

today = datetime.now()
for hour in range(WORK_HOURS_START, WORK_HOURS_END):
    for minute in [0, 30]:
        start = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start > today:
            end = start + timedelta(minutes=SLOT_DURATION)
            SLOTS.append((start, end))

# --------------------------
# GOOGLE CALENDAR ФУНКЦИЯ
# --------------------------
def add_event_to_calendar(title, start, end):
    event = {
        'summary': title,
        'start': {'dateTime': start.isoformat(), 'timeZone': 'Europe/Moscow'},
        'end': {'dateTime': end.isoformat(), 'timeZone': 'Europe/Moscow'},
    }
    calendar_service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()

# --------------------------
# ФУНКЦИИ TELEGRAM
# --------------------------
def build_keyboard():
    keyboard = []
    for idx, (start, end) in enumerate(SLOTS):
        cursor.execute('SELECT * FROM bookings WHERE start=?', (start.isoformat(),))
        if cursor.fetchone():
            continue  # слот уже занят
        button = InlineKeyboardButton(f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}", callback_data=str(idx))
        keyboard.append([button])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выберите слот:", reply_markup=build_keyboard())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot_index = int(query.data)
    start, end = SLOTS[slot_index]

    # Проверка, свободен ли слот
    cursor.execute('SELECT * FROM bookings WHERE start=?', (start.isoformat(),))
    if cursor.fetchone():
        await query.edit_message_text("Извините, этот слот уже занят.")
        return

    # Добавляем в БД
    cursor.execute('INSERT INTO bookings (start, end) VALUES (?, ?)', (start.isoformat(), end.isoformat()))
    conn.commit()

    # Добавляем событие в Google Calendar
    add_event_to_calendar("Консультация", start, end)

    # Сообщение клиенту
    await query.edit_message_text(f"Вы записаны на {start.strftime('%d.%m %H:%M')}")

    # Уведомление администратору
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Новый клиент записался на {start.strftime('%d.%m %H:%M')}"
    )

# --------------------------
# ЗАПУСК БОТА
# --------------------------
if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(application.command_handler("start", start))
    print("Слоты сгенерированы!")
    application.run_polling()
