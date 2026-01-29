import sqlite3
from datetime import datetime, timedelta

DB_PATH = "slots.db"

# Настройки
WORK_HOURS_START = 9  # 9:00
WORK_HOURS_END = 16   # 16:00
SLOT_DURATION = 30     # минут
DAYS_AHEAD = 14        # генерируем на 2 недели вперед

async def create_db():
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

async def generate_slots():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    today = datetime.now().date()

    for day_offset in range(DAYS_AHEAD):
        date = today + timedelta(days=day_offset)
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

# Запуск генерации
import asyncio
async def main():
    await create_db()
    await generate_slots()

if __name__ == "__main__":
    asyncio.run(main())
