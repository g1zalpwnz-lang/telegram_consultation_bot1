import os
import json
from datetime import datetime, timedelta
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- Настройки ---
ADMIN_ID = 617492  # ID администратора
TIMEZONE = pytz.timezone("Europe/Moscow")

# Получаем JSON сервис-аккаунта из переменной окружения Railway
SERVICE_ACCOUNT_JSON = os.environ.get("SERVICE_ACCOUNT_JSON")
if not SERVICE_ACCOUNT_JSON:
    raise ValueError("SERVICE_ACCOUNT_JSON не найдено в переменных окружения!")

SERVICE_ACCOUNT_INFO = json.loads(SERVICE_ACCOUNT_JSON)

credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=["https://www.googleapis.com/auth/calendar"]
)

calendar_service = build('calendar', 'v3', credentials=credentials)
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID")  # ID календаря в GSuite

# --- Утилиты ---
def get_working_days(n=5):
    days = []
    current = datetime.now(TIMEZONE)
    while len(days) < n:
        if current.weekday() < 5:  # Пн-Пт
            days.append(current)
        current += timedelta(days=1)
    return days

def generate_time_slots():
    # Слоты каждые 30 минут с 09:00 до 16:30
    slots = []
    for hour in range(9, 17):
        slots.append(f"{hour:02d}:00")
        slots.append(f"{hour:02d}:30")
    return slots

# --- Хэндлеры ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for day in get_working_days():
        text = day.strftime("%d.%m")
        callback_data = f"day:{text}"
        keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите день:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("day:"):
        day_str = data.split(":")[1]
        slots = generate_time_slots()
        keyboard = [[InlineKeyboardButton(s, callback_data=f"time:{day_str}|{s}")] for s in slots]
        await query.edit_message_text(text=f"Выберите время для {day_str}:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("time:"):
        day_str, time_str = data.split(":")[1].split("|")
        dt = datetime.strptime(f"{day_str} {time_str}", "%d.%m %H:%M")
        dt = TIMEZONE.localize(dt)
        end_dt = dt + timedelta(minutes=30)

        # Добавляем событие в Google Calendar
        event = {
            "summary": f"Запись от {query.from_user.full_name}",
            "start": {"dateTime": dt.isoformat()},
            "end": {"dateTime": end_dt.isoformat()},
        }
        calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

        await query.edit_message_text(f"✅ Записано на {day_str} {time_str}")

        # Отправка уведомления админу
        try:
            await context.bot.send_message(ADMIN_ID, f"Новая запись от {query.from_user.full_name} на {day_str} {time_str}")
        except Exception as e:
            print("Ошибка отправки админу:", e)

# --- Запуск ---
def main():
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден!")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
