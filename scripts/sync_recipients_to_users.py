"""
sync_recipients_to_users.py — Синхронизация telegram_recipients -> telegram_users

Логика:
1. Читает ВСЕ строки из telegram_recipients
2. Для каждой строки:
   - Извлекает telegram_id = chat_id (конвертирует в int)
   - Проверяет наличие в telegram_users
   - Если НЕТ → INSERT с role из recipients, status='active', username, first_name
   - Если ЕСТЬ → DO NOTHING (никогда не перезаписывает status)
3. Owner (8992376203) — не трогать, если уже существует
4. Выводит summary: что добавлено, что пропущено
5. НЕ удаляет telegram_recipients

Использование:
  python scripts/sync_recipients_to_users.py
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "results" / "feedback.db"
OWNER_ID = 8992376203


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def main():
    conn = get_conn()
    c = conn.cursor()

    # Проверить наличие таблиц
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='telegram_recipients'")
    if not c.fetchone():
        print("ERROR: table telegram_recipients does not exist")
        conn.close()
        return

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='telegram_users'")
    if not c.fetchone():
        print("ERROR: table telegram_users does not exist")
        conn.close()
        return

    # Прочитать все строки из telegram_recipients
    c.execute("SELECT chat_id, user_id, username, first_name, role, enabled FROM telegram_recipients")
    recipients = c.fetchall()

    print(f"Found {len(recipients)} row(s) in telegram_recipients")
    print("-" * 60)

    added = []
    skipped_exists = []
    skipped_owner = []

    for r in recipients:
        chat_id_str = r["chat_id"]
        telegram_id = int(chat_id_str)
        username = r["username"] or ""
        first_name = r["first_name"] or ""
        role = r["role"] or "manager"

        # Проверить наличие в telegram_users
        c.execute("SELECT telegram_id, role, status FROM telegram_users WHERE telegram_id = ?", (telegram_id,))
        existing = c.fetchone()

        if existing:
            # Owner — никогда не трогать
            if telegram_id == OWNER_ID:
                skipped_owner.append(f"  Owner {telegram_id} (role={existing['role']}, status={existing['status']})")
                continue
            # Уже существует — НЕ перезаписывать status
            skipped_exists.append(
                f"  {telegram_id} @{username} (exists: role={existing['role']}, status={existing['status']})"
            )
        else:
            # Вставить нового пользователя
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute(
                """INSERT INTO telegram_users (telegram_id, username, first_name, role, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?)""",
                (telegram_id, username, first_name, role, now, now),
            )
            added.append(f"  + {telegram_id} @{username} '{first_name}' role={role} status=active")

    conn.commit()

    # Summary
    print("\nSUMMARY:")
    print(f"  Added:    {len(added)}")
    for line in added:
        print(line)

    print(f"\n  Skipped (exists): {len(skipped_exists)}")
    for line in skipped_exists:
        print(line)

    print(f"\n  Skipped (owner):  {len(skipped_owner)}")
    for line in skipped_owner:
        print(line)

    # Показать финальное состояние telegram_users
    print("\n" + "-" * 60)
    print("Current telegram_users:")
    c.execute("SELECT telegram_id, username, first_name, role, status FROM telegram_users ORDER BY role, telegram_id")
    for row in c.fetchall():
        tid = row["telegram_id"]
        uname = row["username"] or "?"
        fname = row["first_name"] or "?"
        role = row["role"]
        status = row["status"]
        print(f"  {tid} @{uname} '{fname}' role={role} status={status}")

    print(f"\ntelegram_recipients NOT deleted ({len(recipients)} rows still there)")

    conn.close()


if __name__ == "__main__":
    main()
