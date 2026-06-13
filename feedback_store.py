"""
feedback_store.py — SQLite хранилище для Telegram feedback + persistent dedup v2.

Таблицы:
  sent_ads — что отправлено (dedup, цена, send_count)
  feedback — реакции пользователя (buy/watch/skip + comment)

Dedup v2:
  - stable_car_key: card_id → haraba_id из URL → fallback
  - same_price → skip
  - price_drop → send с пометкой "🔻 Цена снизилась"
  - price_increased → skip, update last_seen
  - Никогда не очищать автоматически
"""

import sqlite3
import re
from pathlib import Path
from datetime import datetime

from base import RESULTS_DIR, log

DB_PATH = RESULTS_DIR / "feedback.db"


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _extract_haraba_id(url):
    """Извлечь ID из URL типа https://haraba.ru/common/click?id=173295809&source=1"""
    if not url:
        return ""
    m = re.search(r'[?&]id=(\d+)', url)
    return m.group(1) if m else ""


def _build_stable_key(card):
    """Построить stable_car_key.

    Приоритет:
    1. card_id
    2. haraba_id из URL/mobile_url
    3. Fallback: title+year+price+mileage+region
    """
    card_id = card.get("card_id", "")
    if card_id:
        return "id:" + card_id

    url = card.get("mobile_url", "") or card.get("url", "")
    haraba_id = _extract_haraba_id(url)
    if haraba_id:
        return "haraba:" + haraba_id

    # Fallback
    title = (card.get("title", "") or "").strip()
    year = card.get("year", 0)
    price = card.get("price", 0)
    mileage = card.get("mileage", 0)
    region = (card.get("region", "") or "").strip()
    return "fallback:" + f"{title}_{year}_{price}_{mileage}_{region}"


def init_db():
    """Создать/мигрировать таблицы."""
    conn = get_conn()
    c = conn.cursor()

    # telegram_recipients — multi-recipient support
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='telegram_recipients'")
    if not c.fetchone():
        c.execute("""
            CREATE TABLE telegram_recipients (
                chat_id TEXT PRIMARY KEY,
                user_id TEXT,
                username TEXT,
                first_name TEXT,
                role TEXT,
                enabled INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
    else:
        # Migration: add missing columns
        new_cols = [
            ("user_id", "TEXT"),
            ("username", "TEXT"),
            ("first_name", "TEXT"),
            ("role", "TEXT"),
            ("enabled", "INTEGER"),
        ]
        c.execute("PRAGMA table_info(telegram_recipients)")
        existing = {row[1] for row in c.fetchall()}
        for col_name, col_type in new_cols:
            if col_name not in existing:
                try:
                    c.execute(f"ALTER TABLE telegram_recipients ADD COLUMN {col_name} {col_type}")
                except:
                    pass

    # sent_ads v2
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sent_ads'")
    exists = c.fetchone()

    if not exists:
        c.execute("""
            CREATE TABLE sent_ads (
                stable_car_key TEXT PRIMARY KEY,
                card_id TEXT,
                url TEXT,
                mobile_url TEXT,
                haraba_id TEXT,
                title TEXT,
                model_id TEXT,
                year INTEGER,
                price INTEGER,
                mileage INTEGER,
                region TEXT,
                first_sent_at TEXT,
                last_seen_at TEXT,
                last_sent_at TEXT,
                send_count INTEGER
            )
        """)
    else:
        c.execute("PRAGMA table_info(sent_ads)")
        cols = {row[1] for row in c.fetchall()}

    # Migration: fix PK for multi-recipient
    c.execute("PRAGMA table_info(sent_ads)")
    cols_info = c.fetchall()
    pk_cols = [row[1] for row in cols_info if row[5] > 0] # pk index

    # If PK is just stable_car_key, we need to migrate to composite PK
    if pk_cols == ['stable_car_key']:
        print("Migrating sent_ads to composite PK (stable_car_key + chat_id)")
        c.execute("ALTER TABLE sent_ads RENAME TO sent_ads_v3_old")
        c.execute("""
            CREATE TABLE sent_ads (
                stable_car_key TEXT,
                chat_id TEXT,
                card_id TEXT,
                url TEXT,
                mobile_url TEXT,
                haraba_id TEXT,
                title TEXT,
                model_id TEXT,
                year INTEGER,
                price INTEGER,
                mileage INTEGER,
                region TEXT,
                first_sent_at TEXT,
                last_seen_at TEXT,
                last_sent_at TEXT,
                send_count INTEGER,
                PRIMARY KEY (stable_car_key, chat_id)
            )
        """)
        # Copy data, default chat_id to 'legacy' if NULL
        c.execute("""
            INSERT INTO sent_ads (
                stable_car_key, chat_id, card_id, url, mobile_url, haraba_id,
                title, model_id, year, price, mileage, region,
                first_sent_at, last_seen_at, last_sent_at, send_count
            )
            SELECT
                stable_car_key, COALESCE(chat_id, 'legacy'), card_id, url, mobile_url, haraba_id,
                title, model_id, year, price, mileage, region,
                first_sent_at, last_seen_at, last_sent_at, send_count
            FROM sent_ads_v3_old
        """)
        c.execute("DROP TABLE IF EXISTS sent_ads_v3_old")
        conn.commit()

        # Re-read columns after migration
        c.execute("PRAGMA table_info(sent_ads)")
        cols = {row[1] for row in c.fetchall()}

        if "stable_car_key" not in cols:
            # Миграция v1 -> v2
            c.execute("ALTER TABLE sent_ads RENAME TO sent_ads_v1_old")
            c.execute("""
                CREATE TABLE sent_ads (
                    stable_car_key TEXT PRIMARY KEY,
                    card_id TEXT,
                    url TEXT,
                    mobile_url TEXT,
                    haraba_id TEXT,
                    title TEXT,
                    model_id TEXT,
                    year INTEGER,
                    price INTEGER,
                    mileage INTEGER,
                    region TEXT,
                    first_sent_at TEXT,
                    last_seen_at TEXT,
                    last_sent_at TEXT,
                    send_count INTEGER,
                    chat_id TEXT
                )
            """)
            c.execute("PRAGMA table_info(sent_ads_v1_old)")
            old_cols = {row[1] for row in c.fetchall()}
            if "card_id" in old_cols and "url" in old_cols:
                c.execute("""
                    INSERT OR IGNORE INTO sent_ads (
                        stable_car_key, card_id, url, model_id,
                        title, price, mileage, region,
                        first_sent_at, last_seen_at, last_sent_at, send_count
                    )
                    SELECT COALESCE(card_id, url), card_id, url, COALESCE(model_id, ''),
                        '', 0, 0, '',
                        sent_at, sent_at, sent_at, 1
                    FROM sent_ads_v1_old
                """)
            c.execute("DROP TABLE IF EXISTS sent_ads_v1_old")

    # Блок 2: Миграция — добавить config_name в sent_ads
    c.execute("PRAGMA table_info(sent_ads)")
    sent_ads_cols = {row[1] for row in c.fetchall()}
    if "config_name" not in sent_ads_cols:
        log.info("Migrating sent_ads: adding config_name column")
        c.execute("ALTER TABLE sent_ads ADD COLUMN config_name TEXT")

    # FIX 7A: Миграция — добавить config_name в feedback
    c.execute("PRAGMA table_info(feedback)")
    fb_cols = {row[1] for row in c.fetchall()}
    if "config_name" not in fb_cols:
        log.info("Migrating feedback: adding config_name column")
        c.execute("ALTER TABLE feedback ADD COLUMN config_name TEXT")

    # FIX 7A: Миграция — добавить config_name в reaction_details
    c.execute("PRAGMA table_info(reaction_details)")
    rd_cols = {row[1] for row in c.fetchall()}
    if "config_name" not in rd_cols:
        log.info("Migrating reaction_details: adding config_name column")
        c.execute("ALTER TABLE reaction_details ADD COLUMN config_name TEXT")

    # feedback
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feedback'")
    fb_exists = c.fetchone()
    if not fb_exists:
        c.execute("""
            CREATE TABLE feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT,
                url TEXT,
                model_id TEXT,
                title TEXT,
                price INTEGER,
                mileage INTEGER,
                engine TEXT,
                transmission TEXT,
                drive TEXT,
                region TEXT,
                owners TEXT,
                legal_restrictions TEXT,
                autoteka_status TEXT,
                score INTEGER,
                telegram_status TEXT,
                action TEXT,
                comment TEXT,
                price_status TEXT,
                price_score INTEGER,
                mileage_score INTEGER,
                engine_score INTEGER,
                transmission_score INTEGER,
                equipment_score INTEGER,
                photo_url TEXT,
                photo_count INTEGER,
                full_location TEXT,
                created_at TEXT
            )
        """)
    else:
        # Migration: add missing columns
        new_cols = [
            ("legal_restrictions", "TEXT"),
            ("autoteka_status", "TEXT"),
            ("price_status", "TEXT"),
            ("price_score", "INTEGER"),
            ("mileage_score", "INTEGER"),
            ("engine_score", "INTEGER"),
            ("transmission_score", "INTEGER"),
            ("equipment_score", "INTEGER"),
            ("photo_url", "TEXT"),
            ("photo_count", "INTEGER"),
            ("full_location", "TEXT"),
            ("telegram_chat_id", "TEXT"),
            ("telegram_user_id", "TEXT"),
            ("telegram_username", "TEXT"),
            ("reviewer_role", "TEXT"),
        ]
        c.execute("PRAGMA table_info(feedback)")
        existing = {row[1] for row in c.fetchall()}
        for col_name, col_type in new_cols:
            if col_name not in existing:
                try:
                    c.execute(f"ALTER TABLE feedback ADD COLUMN {col_name} {col_type}")
                except:
                    pass  # Column might already exist

    conn.commit()
    conn.close()


def check_dedup(card):
    """Проверить dedup статус.

    Returns: "new", "same_price", "price_drop", "price_increased"
    """
    init_db()
    conn = get_conn()
    c = conn.cursor()

    stable_key = _build_stable_key(card)
    card_price = card.get("price", 0)

    c.execute(
        "SELECT stable_car_key, price, send_count FROM sent_ads WHERE stable_car_key = ?",
        (stable_key,),
    )
    row = c.fetchone()
    conn.close()

    if not row:
        return "new"

    old_price = row["price"]
    if old_price == card_price:
        return "same_price"
    elif card_price < old_price:
        return "price_drop"
    else:
        return "price_increased"


def mark_sent(card, status="new"):
    """Отметить карточку как отправленную."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()

    stable_key = _build_stable_key(card)
    url = card.get("url", "")
    mobile_url = card.get("mobile_url", "")
    haraba_id = _extract_haraba_id(url) or _extract_haraba_id(mobile_url)
    card_id = card.get("card_id", "") or haraba_id

    if status == "new":
        c.execute("""
            INSERT OR IGNORE INTO sent_ads (
                stable_car_key, card_id, url, mobile_url, haraba_id,
                title, model_id, year, price, mileage, region,
                first_sent_at, last_seen_at, last_sent_at, send_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            stable_key, card_id, url, mobile_url, haraba_id,
            card.get("title", ""), card.get("model_id", ""),
            card.get("year", 0), card.get("price", 0),
            card.get("mileage", 0), card.get("region", ""),
            now, now, now,
        ))
    elif status == "price_drop":
        c.execute("""
            UPDATE sent_ads
            SET price = ?, last_sent_at = ?, last_seen_at = ?,
                send_count = send_count + 1
            WHERE stable_car_key = ?
        """, (
            card.get("price", 0), now, now, stable_key,
        ))

    conn.commit()
    conn.close()


def update_last_seen(card):
    """Обновить last_seen_at без отправки."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    stable_key = _build_stable_key(card)

    c.execute(
        "UPDATE sent_ads SET last_seen_at = ? WHERE stable_car_key = ?",
        (now, stable_key),
    )
    conn.commit()
    conn.close()


def was_sent(url):
    """Обратная совместимость: проверить отправлялось ли по url."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    haraba_id = _extract_haraba_id(url)
    if haraba_id:
        c.execute("SELECT 1 FROM sent_ads WHERE haraba_id = ? OR url = ?",
                  (haraba_id, url))
    else:
        c.execute("SELECT 1 FROM sent_ads WHERE url = ?", (url,))
    result = c.fetchone()
    conn.close()
    return result is not None


def save_feedback(card, action, comment=""):
    """Сохранить реакцию пользователя с полным контекстом."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()

    # FIX 7A: определить config_name
    config_name = card.get("config_name", "") or ""
    if not config_name or config_name.lower() == "unknown":
        # Lookup из sent_ads по card_id + chat_id
        row = c.execute(
            "SELECT config_name FROM sent_ads WHERE card_id = ? AND chat_id = ? ORDER BY first_sent_at DESC LIMIT 1",
            (card.get("card_id", ""), card.get("telegram_chat_id", ""))
        ).fetchone()
        config_name = row[0] if row and row[0] else "unknown"

    c.execute("""
        INSERT INTO feedback (
            card_id, url, model_id, title, price, mileage,
            engine, transmission, drive, region, owners,
            legal_restrictions, autoteka_status,
            score, telegram_status, action, comment,
            price_status, price_score, mileage_score, engine_score,
            transmission_score, equipment_score,
            photo_url, photo_count, full_location,
            telegram_chat_id, telegram_user_id, telegram_username, reviewer_role,
            config_name, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        card.get("card_id", ""),
        card.get("url", ""),
        card.get("model_id", ""),
        card.get("title", ""),
        card.get("price", 0),
        card.get("mileage", 0),
        card.get("engine", "unknown"),
        card.get("transmission", "unknown"),
        card.get("drive", "unknown"),
        card.get("region", "unknown"),
        card.get("owners", "unknown"),
        card.get("legal_restrictions", "unknown"),
        card.get("autoteka_status", "unknown"),
        card.get("score", 0),
        card.get("telegram_status", card.get("decision", "")),
        action,
        comment,
        card.get("price_status", ""),
        card.get("price_score", 0),
        card.get("mileage_score", 0),
        card.get("engine_score", 0),
        card.get("transmission_score", 0),
        card.get("equipment_score", 0),
        card.get("photo_url", ""),
        card.get("photo_count", 0),
        card.get("full_location", ""),
        card.get("telegram_chat_id", ""),
        card.get("telegram_user_id", ""),
        card.get("telegram_username", ""),
        card.get("reviewer_role", ""),
        config_name,
        now,
    ))
    conn.commit()
    conn.close()


def get_feedback_stats(days=7):
    """Статистика feedback за N дней."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT action, COUNT(*) as cnt
        FROM feedback
        WHERE created_at >= datetime('now', '-{} days')
        GROUP BY action
    """.format(days))
    stats = {}
    for row in c.fetchall():
        stats[row["action"]] = row["cnt"]
    conn.close()
    return stats


def get_feedback_all(days=7):
    """Все feedback записи за N дней."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM feedback
        WHERE created_at >= datetime('now', '-{} days')
        ORDER BY created_at DESC
    """.format(days))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_sent_stats():
    """Статистика отправленных карточек."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM sent_ads")
    total = c.fetchone()["cnt"]
    c.execute("""
        SELECT model_id, COUNT(*) as cnt
        FROM sent_ads
        GROUP BY model_id
        ORDER BY cnt DESC
    """)
    by_model = {}
    for row in c.fetchall():
        by_model[row["model_id"]] = row["cnt"]
    conn.close()
    return {"total": total, "by_model": by_model}


def reset_sent_ads():
    """ОЧИСТИТЬ sent_ads — только по явной команде."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM sent_ads")
    conn.commit()
    conn.close()
    print("Sent ads cleared")


# ──────────────────────────────────────────────────────────────
# Telegram Users — single source of truth (telegram_users table)
# ──────────────────────────────────────────────────────────────

OWNER_ID = 8992376203


def upsert_telegram_user(telegram_id, username="", first_name="", role="manager", status="active"):
    """Upsert into telegram_users. If exists, only update username/first_name (never status)."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()

    c.execute("SELECT telegram_id FROM telegram_users WHERE telegram_id = ?", (int(telegram_id),))
    existing = c.fetchone()

    if not existing:
        c.execute(
            """INSERT INTO telegram_users (telegram_id, username, first_name, role, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (int(telegram_id), username, first_name, role, status, now, now),
        )
    else:
        c.execute(
            """UPDATE telegram_users
               SET username = COALESCE(NULLIF(?, ''), username),
                   first_name = COALESCE(NULLIF(?, ''), first_name),
                   updated_at = ?
               WHERE telegram_id = ?""",
            (username, first_name, now, int(telegram_id)),
        )

    conn.commit()
    conn.close()


def register_recipient(chat_id, user_id="", username="", first_name="", role="manager"):
    """Зарегистрировать получателя в telegram_users.

    Если пользователя нет — INSERT с status='active' (backward compat для owner из .env).
    Если уже есть — UPDATE только username/first_name (статус НЕ менять).
    telegram_recipients — legacy, не используется.
    """
    init_db()
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()
    telegram_id = int(chat_id)

    existing = c.execute(
        "SELECT id FROM telegram_users WHERE telegram_id = ?",
        (telegram_id,)
    ).fetchone()

    if not existing:
        c.execute("""
            INSERT INTO telegram_users (telegram_id, username, first_name, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', ?, ?)
        """, (telegram_id, username, first_name, role, now, now))
    else:
        c.execute("""
            UPDATE telegram_users
            SET username = COALESCE(NULLIF(?,''), username),
                first_name = COALESCE(NULLIF(?,''), first_name),
                updated_at = ?
            WHERE telegram_id = ?
        """, (username, first_name, now, telegram_id))

    conn.commit()
    conn.close()


def get_enabled_recipients():
    """Получить всех активных получателей из telegram_users.

    telegram_users — единственный источник правды.
    telegram_recipients — legacy, не используется.
    """
    init_db()
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT telegram_id as chat_id, username, first_name, role
        FROM telegram_users
        WHERE status = 'active'
        ORDER BY role
    """)
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def disable_recipient(chat_id):
    """Отключить получателя — set status='disabled' in telegram_users."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    telegram_id = int(chat_id)
    now = datetime.now().isoformat()
    c.execute(
        "UPDATE telegram_users SET status='disabled', updated_at=? WHERE telegram_id=?",
        (now, telegram_id)
    )
    conn.commit()
    conn.close()


def get_all_recipients():
    """Получить всех получателей из telegram_users."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT telegram_id as chat_id, username, first_name, role, status,
               CASE WHEN status != 'disabled' THEN 1 ELSE 0 END as enabled
        FROM telegram_users
        ORDER BY role, telegram_id
    """)
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def check_dedup_with_chat_id(card, chat_id):
    """Проверить dedup с учётом chat_id.

    Returns: "new", "same_price", "price_drop", "price_increased"
    """
    init_db()
    conn = get_conn()
    c = conn.cursor()

    stable_key = _build_stable_key(card)
    card_price = card.get("price", 0)

    c.execute("""
        SELECT stable_car_key, price, send_count FROM sent_ads
        WHERE stable_car_key = ? AND chat_id = ?
    """, (stable_key, str(chat_id)))

    row = c.fetchone()
    conn.close()

    if not row:
        return "new"

    old_price = row["price"]
    if old_price == card_price:
        return "same_price"
    elif card_price < old_price:
        return "price_drop"
    else:
        return "price_increased"


def mark_sent_with_chat_id(card, chat_id, status="new"):
    """Отметить карточку как отправленную для конкретного chat_id."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().isoformat()

    stable_key = _build_stable_key(card)
    url = card.get("url", "")
    mobile_url = card.get("mobile_url", "")
    haraba_id = _extract_haraba_id(url) or _extract_haraba_id(mobile_url)
    card_id = card.get("card_id", "") or haraba_id
    config_name = card.get("config_name", "unknown")

    if status == "new":
        c.execute("""
            INSERT OR IGNORE INTO sent_ads (
                stable_car_key, card_id, url, mobile_url, haraba_id,
                title, model_id, year, price, mileage, region, chat_id, config_name,
                first_sent_at, last_seen_at, last_sent_at, send_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            stable_key, card_id, url, mobile_url, haraba_id,
            card.get("title", ""), card.get("model_id", ""),
            card.get("year", 0), card.get("price", 0),
            card.get("mileage", 0), card.get("region", ""), str(chat_id), config_name,
            now, now, now,
        ))
    elif status == "price_drop":
        c.execute("""
            UPDATE sent_ads
            SET price = ?, last_sent_at = ?, last_seen_at = ?,
                send_count = send_count + 1
            WHERE stable_car_key = ? AND chat_id = ?
        """, (
            card.get("price", 0), now, now,
            stable_key, str(chat_id),
        ))

    conn.commit()
    conn.close()


# Init on import
init_db()
