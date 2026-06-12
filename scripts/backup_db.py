"""
backup_db.py — Копирует results/feedback.db в results/feedback_backup_<timestamp>.db

Использование:
  python scripts/backup_db.py
"""

import shutil
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "results" / "feedback.db"


def main():
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} does not exist")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.parent / f"feedback_backup_{timestamp}.db"

    shutil.copy2(DB_PATH, backup_path)
    size_kb = backup_path.stat().st_size / 1024
    print(f"Backup created: {backup_path}")
    print(f"Size: {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
