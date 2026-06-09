"""
test_feedback_integrity.py — Блок 16.14: проверка целостности feedback данных.

Проверяет:
1. feedback_store.py — все поля сохраняются
2. telegram_feedback_bot.py — передаёт все поля из card_data
3. load_card_data — загружает engine/transmission/drive/region из sample

Запуск:
  python test_feedback_integrity.py
"""

import json
import sys
import os
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from base import RESULTS_DIR
from feedback_store import save_feedback, init_db, get_conn
from card_data_loader import load_card_data

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        print(f"  ✅ PASS: {name}")
        passed += 1
    else:
        print(f"  ❌ FAIL: {name}")
        failed += 1


print("=" * 60)
print("BLOCK 16.14 — FEEDBACK DATA INTEGRITY")
print("=" * 60)

# ── Тест 1: load_card_data загружает все поля ──
print("\n[1] load_card_data — загрузка всех полей...")
card_data = load_card_data()
check(f"Загружено {len(card_data)} карточек", len(card_data) > 0)

first_cid = list(card_data.keys())[0]
first_card = card_data[first_cid]

required_fields = [
    "card_id", "title", "url", "model_id", "price", "mileage", "year",
    "score", "decision", "engine", "transmission", "drive", "region",
    "owners", "legal_restrictions", "autoteka_status",
]

for field in required_fields:
    val = first_card.get(field)
    check(f"  {field} = {val}", field in first_card and val is not None)

# Проверить что engine/transmission/drive не все unknown
engine_known = sum(1 for c in card_data.values() if c.get("engine", "unknown") != "unknown")
trans_known = sum(1 for c in card_data.values() if c.get("transmission", "unknown") != "unknown")
drive_known = sum(1 for c in card_data.values() if c.get("drive", "unknown") != "unknown")
region_known = sum(1 for c in card_data.values() if c.get("region", "unknown") != "unknown")

check(f"  engine known: {engine_known}/{len(card_data)}", engine_known > 0)
check(f"  transmission known: {trans_known}/{len(card_data)}", trans_known > 0)
check(f"  drive known: {drive_known}/{len(card_data)}", drive_known > 0)
check(f"  region known: {region_known}/{len(card_data)}", region_known > 0)

# ── Тест 2: save_feedback сохраняет все поля ──
print("\n[2] save_feedback — сохранение всех полей...")

test_card = {
    "card_id": "test_001",
    "url": "https://test.url/123",
    "model_id": "test_model",
    "title": "Test Car",
    "price": 1500000,
    "mileage": 100000,
    "engine": "2.0 TDI (150 л.с.)",
    "transmission": "automatic",
    "drive": "awd",
    "region": "Москва",
    "owners": "2",
    "score": 85,
    "telegram_status": "good_candidate",
}

save_feedback(test_card, "buy", "Тестовый комментарий")

conn = get_conn()
c = conn.cursor()
c.execute("SELECT * FROM feedback WHERE card_id = 'test_001'")
row = c.fetchone()
conn.close()

check("  Запись найдена в DB", row is not None)
if row:
    row_dict = dict(row)
    check(f"  engine = '{row_dict.get('engine')}'", row_dict.get("engine") == "2.0 TDI (150 л.с.)")
    check(f"  transmission = '{row_dict.get('transmission')}'", row_dict.get("transmission") == "automatic")
    check(f"  drive = '{row_dict.get('drive')}'", row_dict.get("drive") == "awd")
    check(f"  region = '{row_dict.get('region')}'", row_dict.get("region") == "Москва")
    check(f"  owners = '{row_dict.get('owners')}'", row_dict.get("owners") == "2" or row_dict.get("owners") == 2)
    check(f"  price = {row_dict.get('price')}", row_dict.get("price") == 1500000)
    check(f"  mileage = {row_dict.get('mileage')}", row_dict.get("mileage") == 100000)
    check(f"  score = {row_dict.get('score')}", row_dict.get("score") == 85)
    check(f"  action = '{row_dict.get('action')}'", row_dict.get("action") == "buy")
    check(f"  comment = '{row_dict.get('comment')}'", row_dict.get("comment") == "Тестовый комментарий")

# ── Тест 3: telegram_sender.py передаёт все поля ──
print("\n[3] telegram_sender.py — enrichment при загрузке...")

from telegram_sender import load_audited_candidates
audited_path = RESULTS_DIR / "telegram_candidates_audited.json"
candidates = load_audited_candidates(str(audited_path))

check(f"Загружено {len(candidates)} кандидатов", len(candidates) == 16)

first = candidates[0]
for field in ["engine", "transmission", "drive", "region", "owners", "price", "mileage", "year", "title", "url"]:
    val = first.get(field)
    check(f"  {field} = {val}", field in first and val is not None and val != 0 if isinstance(val, (int, str)) else True)

# ── Тест 4: Telegram config audit ──
print("\n[4] Telegram Config Audit...")

try:
    from telegram_sender import load_telegram_config as load_sender_config
    from telegram_feedback_bot import load_telegram_config as load_bot_config

    sender_token, sender_chat = load_sender_config()
    bot_token, bot_chat = load_bot_config()

    # Не показывать значения, только наличие
    check("  sender: токен найден", sender_token is not None and len(sender_token) > 10)
    check("  sender: chat_id найден", sender_chat is not None)
    check("  bot: токен найден", bot_token is not None and len(bot_token) > 10)
    check("  bot: chat_id найден", bot_chat is not None)
    check("  sender и bot используют один токен", sender_token == bot_token)
    check("  sender и bot используют один chat_id", sender_chat == bot_chat)

    # Показать маскированные значения
    if sender_token:
        masked_token = sender_token[:10] + "..." + sender_token[-5:]
        print(f"  TELEGRAM_BOT_TOKEN = {masked_token}")
    if sender_chat:
        masked_chat = sender_chat[:5] + "..." + sender_chat[-3:] if len(sender_chat) > 8 else "***"
        print(f"  TELEGRAM_CHAT_ID = {masked_chat}")
except ImportError:
    print("  ⚠️ python-telegram-bot не установлен — пропуск теста config")
    print("  Установить: pip install python-telegram-bot")
    # Проверить хотя бы .env файл
    env_path = Path(__file__).parent / ".env"
    check("  .env файл существует", env_path.exists())
    if env_path.exists():
        with open(env_path, "r") as f:
            content = f.read()
        check("  TELEGRAM_BOT_TOKEN в .env", "TELEGRAM_BOT_TOKEN" in content)
        check("  TELEGRAM_CHAT_ID в .env", "TELEGRAM_CHAT_ID" in content)

# ── Итог ──
print(f"\n{'='*60}")
print(f"ИТОГО: {passed} passed, {failed} failed")
print(f"{'='*60}")

if failed == 0:
    print("\n✅ FEEDBACK DATA INTEGRITY — ALL CHECKS PASSED")
    print("   Можно безопасно запускать telegram_sender.py")
else:
    print(f"\n❌ {failed} CHECKS FAILED — исправить перед запуском")
    sys.exit(1)
