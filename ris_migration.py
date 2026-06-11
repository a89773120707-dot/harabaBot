"""Миграция RIS — создание таблиц для Reaction Intelligence System.

Новые таблицы:
- reaction_reasons (справочник причин)
- reaction_details (привязка причин к реакциям)
- learning_rules (предложенные правила)

Все CREATE TABLE IF NOT EXISTS — безопасно для существующей БД.
"""

import sqlite3
from datetime import datetime
import sys
import os

# Поддержка запуска как из корня проекта, так и из admin_bot
DB_PATH = os.environ.get("DB_PATH", "results/feedback.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def migrate():
    conn = get_conn()
    cursor = conn.cursor()

    # ──────────────────────────────────────────────────────────────
    # 1. reaction_reasons — справочник причин реакций
    # ──────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reaction_reasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reaction_type TEXT NOT NULL,
            reason_code TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL
        )
    """)

    # Проверить — уже заполнены?
    existing = cursor.execute("SELECT COUNT(*) as cnt FROM reaction_reasons").fetchone()["cnt"]
    if existing == 0:
        reasons = [
            # LIKE
            ("like", "good_price", "Хорошая цена"),
            ("like", "good_mileage", "Низкий пробег"),
            ("like", "good_equipment", "Хорошая комплектация"),
            ("like", "good_region", "Удобный регион"),
            ("like", "good_model", "Хорошая модель"),
            ("like", "call_now", "Звонить сейчас"),
            # DISLIKE
            ("dislike", "expensive", "Дорого"),
            ("dislike", "high_mileage", "Большой пробег"),
            ("dislike", "bad_equipment", "Плохая комплектация"),
            ("dislike", "bad_region", "Неудобный регион"),
            ("dislike", "bad_model", "Плохая модель"),
            ("dislike", "legal_risk", "Юр. риски"),
            ("dislike", "low_liquidity", "Низкая ликвидность"),
            # FIRE
            ("fire", "rare_offer", "Редкое предложение"),
            ("fire", "below_market", "Ниже рынка"),
            ("fire", "high_margin", "Высокая маржа"),
            ("fire", "urgent_call", "Срочно звонить"),
        ]
        cursor.executemany(
            "INSERT INTO reaction_reasons (reaction_type, reason_code, title) VALUES (?, ?, ?)",
            reasons
        )
        print(f"  reaction_reasons: заполнено {len(reasons)} причин")
    else:
        print(f"  reaction_reasons: уже есть ({existing} записей)")

    # ──────────────────────────────────────────────────────────────
    # 2. reaction_details — привязка reason_code к feedback
    # ──────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reaction_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER NOT NULL,
            reason_code TEXT,
            created_at TEXT,
            FOREIGN KEY (feedback_id) REFERENCES feedback(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reaction_details_feedback ON reaction_details(feedback_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reaction_details_reason ON reaction_details(reason_code)")
    print("  reaction_details: создана")

    # ──────────────────────────────────────────────────────────────
    # 3. learning_rules — предложенные правила
    # ──────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_type TEXT NOT NULL,
            target TEXT NOT NULL,
            condition_json TEXT,
            effect_value INTEGER,
            status TEXT DEFAULT 'pending',
            source_reactions INTEGER,
            created_at TEXT,
            approved_at TEXT,
            approved_by TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_rules_status ON learning_rules(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_rules_target ON learning_rules(target)")
    print("  learning_rules: создана")

    # ──────────────────────────────────────────────────────────────
    # Статистика
    # ──────────────────────────────────────────────────────────────
    total = cursor.execute("SELECT COUNT(*) as cnt FROM feedback").fetchone()["cnt"]
    reactions = cursor.execute("SELECT action, COUNT(*) as cnt FROM feedback GROUP BY action").fetchall()
    print(f"\n  Всего реакций: {total}")
    for r in reactions:
        print(f"    {r['action']}: {r['cnt']}")

    conn.commit()
    conn.close()
    print("\n✅ RIS migration complete")


if __name__ == "__main__":
    migrate()
