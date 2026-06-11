"""Конфиг админ-бота — загрузка переменных окружения."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "8992376203"))

# ADMIN_IDS может быть "123" или "123,456,789"
_ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = []
if _ADMIN_IDS_STR.strip():
    try:
        ADMIN_IDS = [int(x.strip()) for x in _ADMIN_IDS_STR.split(",") if x.strip()]
    except ValueError:
        print(f"WARNING: ADMIN_IDS contains non-integer values: {_ADMIN_IDS_STR}")
        ADMIN_IDS = []

# Owner всегда считается admin
if OWNER_ID not in ADMIN_IDS:
    ADMIN_IDS.append(OWNER_ID)

DB_PATH = Path(os.getenv("DB_PATH", "results/feedback.db"))
LOG_PATH = Path(os.getenv("LOG_PATH", "logs/"))
BACKUP_PATH = Path(os.getenv("BACKUP_PATH", "backups/"))
EXPORT_PATH = Path(os.getenv("EXPORT_PATH", "exports/"))


def validate() -> bool:
    """Проверить, что обязательные поля заполнены."""
    errors = []
    if not ADMIN_BOT_TOKEN or ADMIN_BOT_TOKEN == "PLACEHOLDER_CREATE_BOT_VIA_BOTFATHER":
        errors.append("ADMIN_BOT_TOKEN не настроен — создай бота через @BotFather")
    if not DB_PATH.exists():
        errors.append(f"DB_PATH не существует: {DB_PATH}")
    if errors:
        for e in errors:
            print(f"CONFIG ERROR: {e}")
        return False
    return True


if __name__ == "__main__":
    print("Config loaded OK")
    print(f"OWNER_ID: {OWNER_ID}")
    print(f"ADMIN_IDS: {ADMIN_IDS}")
    print(f"DB_PATH: {DB_PATH}")
    ok = validate()
    if ok:
        print("All checks passed")
    else:
        print("Some checks failed (see above)")
