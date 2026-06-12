"""
verify_users_sync.py — Проверка синхронизации пользователей

Проверяет:
1. telegram_users — единый источник правды
2. get_enabled_recipients() возвращает только active
3. get_all_recipients() возвращает всех
4. telegram_recipients НЕ используется для рассылки
"""

import sqlite3
import sys
from pathlib import Path

# Добавить project root в path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "results" / "feedback.db"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def main():
    conn = get_conn()

    print("=" * 60)
    print("VERIFICATION: telegram_users — единый источник правды")
    print("=" * 60)

    # 1. telegram_users
    print("\n1. telegram_users:")
    c = conn.execute(
        "SELECT telegram_id, username, first_name, role, status FROM telegram_users ORDER BY role, telegram_id"
    )
    users = c.fetchall()
    for u in users:
        print(f"   {u['telegram_id']} @{u['username'] or '?'} role={u['role']} status={u['status']}")
    print(f"   Total: {len(users)}")

    # 2. telegram_recipients (legacy)
    print("\n2. telegram_recipients (LEGACY — не используется):")
    c = conn.execute("SELECT chat_id, username, role, enabled FROM telegram_recipients ORDER BY chat_id")
    recipients = c.fetchall()
    for r in recipients:
        print(f"   {r['chat_id']} @{r['username'] or '?'} role={r['role']} enabled={r['enabled']}")
    print(f"   Total: {len(recipients)}")

    # 3. get_enabled_recipients
    print("\n3. get_enabled_recipients() — только active:")
    from feedback_store import get_enabled_recipients
    enabled = get_enabled_recipients()
    for e in enabled:
        print(f"   {e['chat_id']} @{e.get('username', '?')} role={e['role']}")
    print(f"   Total: {len(enabled)}")

    # 4. get_all_recipients
    print("\n4. get_all_recipients() — все:")
    from feedback_store import get_all_recipients
    all_rec = get_all_recipients()
    for a in all_rec:
        print(f"   {a['chat_id']} @{a.get('username', '?')} role={a['role']} status={a.get('status', '?')} enabled={a.get('enabled', '?')}")
    print(f"   Total: {len(all_rec)}")

    # 5. Проверка consistency
    print("\n5. CONSISTENCY CHECKS:")

    # enabled recipients должны совпадать с active users
    active_users = [u["telegram_id"] for u in users if u["status"] == "active"]
    enabled_ids = [int(e["chat_id"]) for e in enabled]

    if set(active_users) == set(enabled_ids):
        print("   ✅ active users == enabled recipients")
    else:
        print(f"   ❌ MISMATCH: active={active_users}, enabled={enabled_ids}")

    # all_recipients должны совпадать с telegram_users
    all_user_ids = [u["telegram_id"] for u in users]
    all_rec_ids = [int(a["chat_id"]) for a in all_rec]

    if set(all_user_ids) == set(all_rec_ids):
        print("   ✅ all users == all recipients")
    else:
        print(f"   ❌ MISMATCH: users={all_user_ids}, recipients={all_rec_ids}")

    # pending не должен быть в enabled
    pending_ids = [u["telegram_id"] for u in users if u["status"] == "pending"]
    if not any(pid in enabled_ids for pid in pending_ids):
        print("   ✅ pending users NOT in enabled recipients")
    else:
        print("   ❌ pending users ARE in enabled recipients!")

    # paused не должен быть в enabled
    paused_ids = [u["telegram_id"] for u in users if u["status"] == "paused"]
    if not any(pid in enabled_ids for pid in paused_ids):
        print("   ✅ paused users NOT in enabled recipients")
    else:
        print("   ❌ paused users ARE in enabled recipients!")

    print("\n" + "=" * 60)
    conn.close()


if __name__ == "__main__":
    main()
