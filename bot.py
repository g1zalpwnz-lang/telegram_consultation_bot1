import os
import json
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Настройки из environment variables
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
ADMIN_CHAT_ID = int(os.environ['ADMIN_CHAT_ID'])
GOOGLE_CALENDAR_ID = os.environ['GOOGLE_CALENDAR_ID']

# Загружаем сервисный аккаунт
service_account_str = os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']
service_account_json = json.loads(service_account_str)
service_account_json['private_key'] = service_account_json['private_key'].replace('\\n', '\n')

# Создаем credentials и сервис календаря
credentials = service_account.Credentials.from_service_account_info(
    service_account_json,
    scopes=["https://www.googleapis.com/auth/calendar"]
)
calendar_service = build('calendar', 'v3', credentials=credentials)

# Слоты
slots = [f"{h}:00" for h in range(9, 17)]  # 9:00 - 16:00

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(s, callback_data=s)] for s in slots]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите время для консультации:', reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot = query.data
    user = query.from_user
    await query.edit_message_text(text=f"Вы записаны на {slot}")

    # Уведомление администратору
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"{user.full_name} записался на {slot}")

    # Добавление события в Google Calendar
    start_time = datetime.now().replace(hour=int(slot.split(":")[0]), minute=0, second=0)
    event = {
        'summary': f'Консультация с {user.full_name}',
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Europe/Moscow'},
        'end': {'dateTime': (start_time + timedelta(minutes=30)).isoformat(), 'timeZone': 'Europe/Moscow'},
    }
    calendar_service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

print("Бот запущен!")
app.run_polling()
