import os
import json
from datetime import datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build

# -------- Настройки --------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")  # токен бота
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))      # id администратора
CALENDAR_ID = os.environ.get("CALENDAR_ID")       # id календаря Google
TIMEZONE = "Europe/Moscow"

# -------- Google Calendar API --------
SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
SERVICE_ACCOUNT_INFO = json.loads(SERVICE_ACCOUNT_JSON)

credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=["https://www.googleapis.com/auth/calendar"]
)

service = build("calendar", "v3", credentials=credentials)

# -------- Слоты --------
def generate_slots():
    slots = []
    start_hour = 9
    end_hour = 16
    for hour in range(start_hour, end_hour + 1):
        slots.append(f"{hour:02d}:00")
        slots.append(f"{hour:02d}:30")
    return slots

SLOTS = generate_slots()

# -------- Вспомогательные функции --------
def get_next_working_days(n=5):
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz)
    days = []
    current = today
    while len(days) < n:
        if current.weekday() < 5:  # Пн-Пт
            days.append(current)
        current += timedelta(days=1)
    return days

def format_day(dt):
    return dt.strftime("%d.%m")

# -------- Хендлеры --------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    days = get_next_working_days()
    keyboard = [
        [InlineKeyboardButton(format_day(day), callback_data=f"date:{day.strftime('%Y-%m-%d')}")]
        for day in days
    ]
    await update.message.reply_text("Выберите дату:", reply_markup=InlineKeyboardMarkup(keyboard))

async def select_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("date:"):
        date_str = data.split(":")[1]
        context.user_data["selected_date"] = date_str

        keyboard = [
            [InlineKeyboardButton(slot, callback_data=f"slot:{slot}")] for slot in SLOTS
        ]
        await query.message.reply_text("Выберите время:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("slot:"):
        slot = data.split(":")[1]
        date_str = context.user_data.get("selected_date")
        if not date_str:
            await query.message.reply_text("Сначала выберите дату!")
            return

        datetime_str = f"{date_str} {slot}"
        tz = pytz.timezone(TIMEZONE)
        start_dt = tz.localize(datetime.strptime(datetime_str, "%Y-%m-%d %H:%M"))
        end_dt = start_dt + timedelta(minutes=30)

        # Добавляем событие в календарь
        event = {
            "summary": f"Запись с {update.effective_user.full_name}",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
        }
        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

        # Отправляем уведомление админу
        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"Новая запись: {update.effective_user.full_name}\nДата: {date_str}\nВремя: {slot}"
            )

        await query.message.reply_text(f"Запись подтверждена на {date_str} в {slot}")

# -------- Основная логика --------
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(select_slot))

print("Бот запущен...")
app.run_polling()
