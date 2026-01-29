import os
import json
import pytz
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ==== Google Service Account ====
SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
SERVICE_ACCOUNT_INFO = json.loads(SERVICE_ACCOUNT_JSON)
# заменяем \\n на реальные переносы
SERVICE_ACCOUNT_INFO["private_key"] = SERVICE_ACCOUNT_INFO["private_key"].replace("\\n", "\n")

credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=["https://www.googleapis.com/auth/calendar"]
)

calendar_service = build("calendar", "v3", credentials=credentials)
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID")  # например "primary" или id календаря

# ==== Telegram Bot ====
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", 617492))  # Telegram ID администратора

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# ==== Генерация рабочих дней ====
def get_next_workdays(n=5):
    days = []
    today = datetime.now(MOSCOW_TZ)
    i = 0
    while len(days) < n:
        day = today + timedelta(days=i)
        if day.weekday() < 5:  # Пн-Пт
            days.append(day)
        i += 1
    return days

# ==== Генерация слотов ====
def generate_slots(day):
    slots = []
    start_hour, end_hour = 9, 16
    current = datetime(day.year, day.month, day.day, start_hour, 0, tzinfo=MOSCOW_TZ)
    end = datetime(day.year, day.month, day.day, end_hour, 0, tzinfo=MOSCOW_TZ)
    while current <= end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
    return slots

# ==== Обработчики ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    days = get_next_workdays()
    keyboard = [
        [InlineKeyboardButton(day.strftime("%d.%m"), callback_data=day.strftime("%Y-%m-%d"))]
        for day in days
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите дату:", reply_markup=reply_markup)

async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    day = datetime.strptime(query.data, "%Y-%m-%d").date()
    slots = generate_slots(day)
    keyboard = [
        [InlineKeyboardButton(slot, callback_data=f"{day} {slot}")]
        for slot in slots
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(f"Выберите время для {day.strftime('%d.%m.%Y')}:", reply_markup=reply_markup)

async def slot_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dt_str = query.data  # "YYYY-MM-DD HH:MM"
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    dt = MOSCOW_TZ.localize(dt)

    # создаём событие в Google Calendar
    event = {
        "summary": f"Консультация с {query.from_user.full_name}",
        "start": {"dateTime": dt.isoformat(), "timeZone": "Europe/Moscow"},
        "end": {"dateTime": (dt + timedelta(minutes=30)).isoformat(), "timeZone": "Europe/Moscow"},
    }
    calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

    # уведомление администратора
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"Новая запись: {query.from_user.full_name} на {dt.strftime('%d.%m.%Y %H:%M')}"
    )

    await query.message.reply_text(f"Вы записаны на {dt.strftime('%d.%m.%Y %H:%M')}!")

# ==== Основное ====
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(date_selected, pattern=r"\d{4}-\d{2}-\d{2}$"))
    app.add_handler(CallbackQueryHandler(slot_selected, pattern=r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"))
    print("Бот запущен...")
    app.run_polling()
