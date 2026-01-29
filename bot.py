import os
import json
import sqlite3
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
)
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ================= Настройки =================
TOKEN = os.environ["TOKEN"]  # Telegram токен
DB_PATH = "slots.db"
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])  # твой Telegram ID

# Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = os.environ["CALENDAR_ID"]  # email календаря
SERVICE_ACCOUNT_JSON = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])

credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_JSON, scopes=SCOPES
)
calendar_service = build('calendar', 'v3', credentials=credentials)

# ================= Генерация слотов =================
WORK_HOURS_START = 9
WORK_HOURS_END = 16
SLOT_DURATION = 30
DAYS_AHEAD = 14  # на 2 недели вперед

def create_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            time TEXT,
            available INTEGER DEFAULT 1,
            client_name TEXT,
            client_chat_id INTEGER
        )
    """)
    conn.commit()
    conn.close()

def generate_slots():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.date.today()

    for day_offset in range(DAYS_AHEAD):
        date = today + datetime.timedelta(days=day_offset)
        if date.weekday() >= 5:  # пропускаем субботу и воскресенье
            continue
        for hour in range(WORK_HOURS_START, WORK_HOURS_END):
            for minute in [0, 30]:
                time_str = f"{hour:02d}:{minute:02d}"
                c.execute(
                    "INSERT INTO slots (date, time, available) VALUES (?, ?, 1)",
                    (date.isoformat(), time_str)
                )

    conn.commit()
    conn.close()
    print("Слоты сгенерированы!")

# ================= Google Calendar =================
def add_event_to_calendar(client_name, date, time):
    start_dt = datetime.datetime.fromisoformat(f"{date}T{time}:00")
    end_dt = start_dt + datetime.timedelta(minutes=SLOT_DURATION)
    event = {
        'summary': f'Консультация: {client_name}',
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Europe/Moscow'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Europe/Moscow'},
    }
    calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

# ================= Бот =================
async def start(update, context):
    await update.message.reply_text("Привет! Запишитесь на консультацию. Выберите дату:")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT date FROM slots WHERE available=1 ORDER BY date")
    dates = c.fetchall()
    conn.close()

    keyboard = [[InlineKeyboardButton(date[0], callback_data=f"date_{date[0]}")] for date in dates]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите дату:", reply_markup=reply_markup)

async def button(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if data.startswith("date_"):
        date = data.split("_")[1]
        c.execute("SELECT id, time FROM slots WHERE date=? AND available=1 ORDER BY time", (date,))
        slots = c.fetchall()
        keyboard = [[InlineKeyboardButton(slot[1], callback_data=f"slot_{slot[0]}")] for slot in slots]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Доступные слоты на {date}:", reply_markup=reply_markup)

    elif data.startswith("slot_"):
        slot_id = int(data.split("_")[1])
        c.execute("SELECT date, time, available FROM slots WHERE id=?", (slot_id,))
        slot = c.fetchone()
        if slot[2] == 0:
            await query.edit_message_text("Этот слот уже занят, выберите другой.")
            conn.close()
            return

        # Бронируем слот
        c.execute(
            "UPDATE slots SET available=0, client_name=?, client_chat_id=? WHERE id=?",
            (query.from_user.full_name, query.from_user.id, slot_id)
        )
        conn.commit()

        # Добавляем событие в Google Calendar
        add_event_to_calendar(query.from_user.full_name, slot[0], slot[1])

        # Уведомление админа
        if ADMIN_CHAT_ID:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"Новая запись: {query.from_user.full_name}, {slot[0]} {slot[1]}"
            )

        await query.edit_message_text(f"Вы успешно записаны на {slot[0]} в {slot[1]}.\nДо встречи!")

    conn.close()

# ================= Запуск =================
if __name__ == "__main__":
    create_db()
    generate_slots()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    print("Бот запущен!")
    app.run_polling()
