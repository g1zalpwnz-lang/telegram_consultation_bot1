import os
from datetime import datetime, timedelta, time
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ====== НАСТРОЙКИ ======
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID"))  # 617492
CALENDAR_ID = os.environ.get("CALENDAR_ID")  # Например, bot-calendar@exalted-etching-485813-r4.iam.gserviceaccount.com
SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")  # Полный JSON в одну строку
TIMEZONE = "Europe/Moscow"
WORK_START = 9
WORK_END = 16
SLOT_INTERVAL_MINUTES = 30
NUM_DAYS = 5  # ближайшие рабочие дни

# ====== GOOGLE CALENDAR ======
credentials = service_account.Credentials.from_service_account_info(
    eval(SERVICE_ACCOUNT_JSON),  # преобразуем из строки в dict
    scopes=["https://www.googleapis.com/auth/calendar"]
)
service = build("calendar", "v3", credentials=credentials)

# ====== ФУНКЦИИ ======
def get_next_working_days(n):
    days = []
    current = datetime.now(pytz.timezone(TIMEZONE))
    while len(days) < n:
        if current.weekday() < 5:  # 0-4 -> Пн-Пт
            days.append(current)
        current += timedelta(days=1)
    return days

def generate_time_slots():
    slots = []
    current = time(WORK_START, 0)
    while current <= time(WORK_END, 30):
        slots.append(current.strftime("%H:%M"))
        current = (datetime.combine(datetime.today(), current) + timedelta(minutes=SLOT_INTERVAL_MINUTES)).time()
    return slots

def format_date(dt):
    return dt.strftime("%d.%m")

# ====== ХЭНДЛЕРЫ ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(format_date(day), callback_data=f"date|{day.date()}")]
        for day in get_next_working_days(NUM_DAYS)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите дату для консультации:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("date|"):
        selected_date = data.split("|")[1]
        slots = generate_time_slots()
        keyboard = [
            [InlineKeyboardButton(slot, callback_data=f"time|{selected_date}|{slot}")]
            for slot in slots
        ]
        await query.edit_message_text(
            text=f"Вы выбрали дату {selected_date}. Выберите время:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("time|"):
        _, selected_date, selected_time = data.split("|")
        dt = datetime.strptime(f"{selected_date} {selected_time}", "%Y-%m-%d %H:%M")
        dt = pytz.timezone(TIMEZONE).localize(dt)

        # Создание события в календаре
        event = {
            "summary": "Консультация",
            "start": {"dateTime": dt.isoformat(), "timeZone": TIMEZONE},
            "end": {"dateTime": (dt + timedelta(minutes=SLOT_INTERVAL_MINUTES)).isoformat(), "timeZone": TIMEZONE},
        }
        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

        # Уведомление клиента
        await query.edit_message_text(f"Вы записаны на {selected_date} в {selected_time}!")

        # Уведомление админа
        await context.bot.send_message(ADMIN_CHAT_ID, f"Новая запись: {selected_date} в {selected_time}")

# ====== ИНИЦИАЛИЗАЦИЯ БОТА ======
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.run_polling()
