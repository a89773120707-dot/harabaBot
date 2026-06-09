"""
telegram_sender.py — Блок 16: отправка карточек в Telegram v1 + inline кнопки + feedback

Команды:
  python telegram_sender.py --dry-run --input results/telegram_candidates_audited.json
  python telegram_sender.py --send --limit 1
  python telegram_sender.py --send --limit 16
"""

import argparse
import json
import logging
import os
import sys
import yaml
from pathlib import Path
from datetime import datetime
from io import BytesIO

import requests

from base import RESULTS_DIR, log
from feedback_store import check_dedup, mark_sent, update_last_seen

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    log.warning("python-telegram-bot не установлен. Dry-run работает, --send требует: pip install python-telegram-bot")

from telegram_card_formatter import format_car_card_v2
from config_loader import load_config, get_model_by_id
from model_matcher import match_card_to_model
from cards_loader import normalize_card
from price_scorer_v2 import score_price
from mileage_scorer import score_mileage

CONFIG_PATH = RESULTS_DIR / "awd_liquid_full_config.yaml"

# ──────────────────────────────────────────────────────────────
# Настройки Telegram из .env
# ──────────────────────────────────────────────────────────────

def load_telegram_config():
    """Загрузить TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID из .env."""
    env_path = Path(__file__).parent / ".env"
    bot_token = None
    chat_id = None

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key == "TELEGRAM_BOT_TOKEN":
                    bot_token = val
                elif key == "TELEGRAM_CHAT_ID":
                    chat_id = val

    # Также проверить переменные окружения
    bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    return bot_token, chat_id


# ──────────────────────────────────────────────────────────────
# Загрузка кандидатов
# ──────────────────────────────────────────────────────────────

def load_audited_candidates(path: str) -> list:
    """Загрузить аудированных кандидатов + обогатить полными данными из sample."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cards = data.get("cards", [])

    # Загрузить полные данные из sample для обогащения
    sample_path = RESULTS_DIR / "mobile_first_page_sample.json"
    sample_lookup = {}
    if sample_path.exists():
        with open(sample_path, "r", encoding="utf-8") as f:
            sample = json.load(f)
        for c in sample.get("cards", []):
            cid = c.get("card_id", "")
            if cid:
                sample_lookup[cid] = c

    # Фильтр: send_ready + hold_manual_review
    to_send = []
    config = None

    for c in cards:
        action = c.get("action", "")
        if action in ("send_ready", "hold_manual_review"):
            # Обогатить из sample
            cid = c.get("card_id", "")
            if cid in sample_lookup:
                s = sample_lookup[cid]
                specs = s.get("specs", {})
                c["engine"] = specs.get("engine", {}).get("value", "unknown")
                c["transmission"] = specs.get("transmission", {}).get("value", "unknown")
                c["drive"] = specs.get("drive", {}).get("value", "unknown")
                if c.get("region", "unknown") == "unknown":
                    c["region"] = specs.get("region", {}).get("value", "unknown")
                c["owners"] = specs.get("owners", {}).get("value", "unknown")
                c["legal_restrictions"] = specs.get("legal_restrictions", {}).get("value", "unknown")
                c["autoteka_status"] = specs.get("autoteka_status", {}).get("value", "unknown")
                c["mobile_url"] = s.get("mobile_url", "")
                c["mobile_detail_raw_text"] = s.get("mobile_detail_raw_text", "")
                # Mileage/year/price из sample
                if not c.get("mileage"):
                    c["mileage"] = s.get("mileage", 0)
                if not c.get("year"):
                    c["year"] = s.get("year", 0)
                if not c.get("price"):
                    c["price"] = s.get("price", 0)
                if not c.get("title"):
                    c["title"] = s.get("title", "")
                if not c.get("url"):
                    c["url"] = s.get("url", "")
                # Блок 19: фото из sample
                c["photos"] = s.get("photos", {})
                c["photo_url"] = s.get("photo_url", "") or c["photos"].get("main_photo_url", "")
                c["photo_count"] = s.get("photo_count", 0) or c["photos"].get("photo_count", 0)

            # Определить model_id
            norm = normalize_card(c)
            if config is None:
                config = load_config(str(CONFIG_PATH))
            model_id = match_card_to_model(norm, config)
            c["model_id"] = model_id

            # Скоринг для price_context
            if model_id:
                model_rules = get_model_by_id(config, model_id)
                if model_rules:
                    price_r = score_price(c.get("price", 0), model_rules.get("price", {}))
                    mileage_r = score_mileage(c.get("mileage", 0), model_rules.get("mileage", {}))
                    from powertrain_scorer import score_engine, score_transmission
                    engine_r = score_engine(c.get("engine", ""), model_rules.get("engines", {}))
                    trans_r = score_transmission(c.get("transmission", ""), model_rules.get("transmissions", {}))
                    c["price_score"] = price_r["score"]
                    c["mileage_score"] = mileage_r["score"]
                    c["engine_score"] = engine_r["score"]
                    c["transmission_score"] = trans_r["score"]
                    c["price_category"] = price_r.get("category", "")
                    c["price_status"] = price_r.get("price_status", "")
                    c["bonus_reasons"] = []
                    c["penalty_reasons"] = []
                    if price_r["score"] > 0:
                        c["bonus_reasons"].append(price_r["explanation"])
                    elif price_r["score"] < 0:
                        c["penalty_reasons"].append(price_r["explanation"])
                    if mileage_r["score"] > 0:
                        c["bonus_reasons"].append(mileage_r["explanation"])
                    elif mileage_r["score"] < 0:
                        c["penalty_reasons"].append(mileage_r["explanation"])
                    if engine_r["score"] > 0:
                        c["bonus_reasons"].append(engine_r["explanation"])
                    if trans_r["score"] > 0:
                        c["bonus_reasons"].append(trans_r["explanation"])

            to_send.append(c)

    log.info(f"Загружено {len(cards)} кандидатов, к отправке: {len(to_send)}")
    return to_send


# ──────────────────────────────────────────────────────────────
# Inline кнопки
# ──────────────────────────────────────────────────────────────

def build_inline_keyboard(card_id: str, photo_count: int = 0, has_description: bool = True):
    """Создать inline клавиатуру: 🟢🟡 сверху, 🔴📖📷 снизу."""
    row1 = [
        InlineKeyboardButton("🟢 Купить", callback_data=f"buy:{card_id}"),
        InlineKeyboardButton("🟡 Посмотреть", callback_data=f"watch:{card_id}"),
    ]
    row2 = [
        InlineKeyboardButton("🔴 Скипнуть", callback_data=f"skip:{card_id}"),
    ]
    if has_description:
        row2.append(InlineKeyboardButton("📖 Описание", callback_data=f"desc:{card_id}"))
    if photo_count > 1:
        row2.append(InlineKeyboardButton("📷 Ещё фото", callback_data=f"photos:{card_id}"))

    return InlineKeyboardMarkup([row1, row2])


# ──────────────────────────────────────────────────────────────
# Подготовка карточки для отправки
# ──────────────────────────────────────────────────────────────

def prepare_card_text(card: dict, config: dict) -> str:
    """Подготовить текст карточки для Telegram."""
    is_hold = card.get("action") == "hold_manual_review"
    hold_reasons = card.get("reasons_hold", [])

    # Нормализовать transmission и drive
    trans_raw = card.get("transmission", "unknown")
    trans_map = {
        "Автомат": "automatic", "Автоматическая": "automatic", "automatic": "automatic",
        "Робот": "dsg", "DSG": "dsg", "dsg": "dsg",
        "Вариатор": "cvt", "CVT": "cvt", "cvt": "cvt",
        "Механика": "manual", "Механическая": "manual", "manual": "manual",
    }
    transmission = trans_map.get(trans_raw, trans_raw)

    drive_raw = card.get("drive", "unknown")
    drive_map = {"Полный": "awd", "awd": "awd", "Передний": "fwd", "Задний": "rwd",
                 "4WD": "awd", "4MATIC": "awd", "quattro": "awd"}
    drive = drive_map.get(drive_raw, drive_raw)

    scored_card = {
        "title": card.get("title", ""),
        "year": card.get("year", 0),
        "price": card.get("price", 0),
        "mileage": card.get("mileage", 0),
        "score": card.get("score", 0),
        "decision": card.get("decision", "watch"),
        "url": card.get("url", ""),
        "mobile_url": card.get("mobile_url", ""),
        "card_id": card.get("card_id", ""),
        "model_id": card.get("model_id", ""),
        "engine": card.get("engine", "unknown"),
        "transmission": transmission,
        "drive": drive,
        "region": card.get("region", "unknown"),
        "owners": card.get("owners", "unknown"),
        "legal_restrictions": card.get("legal_restrictions", "unknown"),
        "autoteka_status": card.get("autoteka_status", "unknown"),
        "features": card.get("features", []),
        "bonus_reasons": card.get("bonus_reasons", []),
        "penalty_reasons": card.get("penalty_reasons", []),
        "price_score": card.get("price_score", 0),
        "mileage_score": card.get("mileage_score", 0),
        "engine_score": card.get("engine_score", 0),
        "transmission_score": card.get("transmission_score", 0),
        "equipment_score": card.get("equipment_score", 0),
        "price_category": card.get("price_category", ""),
        "price_status": card.get("price_status", ""),
        "mobile_detail_raw_text": card.get("mobile_detail_raw_text", ""),
        "seller_description": card.get("seller_description", ""),
        "photo_url": card.get("photo_url", "") or card.get("photos", {}).get("main_photo_url", ""),
        "photo_count": card.get("photo_count", 0) or card.get("photos", {}).get("photo_count", 0),
    }

    return format_car_card_v2(scored_card, config, is_hold=is_hold, hold_reasons=hold_reasons)


# ──────────────────────────────────────────────────────────────
# Отправка одной карточки (синхронная, для простоты v1)
# ──────────────────────────────────────────────────────────────

async def send_car_card_async(bot, chat_id, card, config, price_drop=False):
    """Отправить одну карточку в Telegram."""
    card_id = card.get("card_id", "")

    text = prepare_card_text(card, config)

    # Префикс для price_drop
    if price_drop:
        text = "🔻 Цена снизилась!\n\n" + text

    # Фото
    photo_url = card.get("photo_url", "") or card.get("photos", {}).get("main_photo_url", "")
    photo_count = card.get("photo_count", 0) or card.get("photos", {}).get("photo_count", 0)
    has_desc = bool(card.get("mobile_detail_raw_text", "") or card.get("seller_description", ""))

    keyboard = build_inline_keyboard(card_id, photo_count=photo_count, has_description=has_desc)

    max_caption = 1024  # Telegram limit for photo caption
    try:
        if photo_url:
            # Скачиваем фото как bytes (надёжнее чем URL для Telegram Bot API)
            try:
                resp = requests.get(photo_url, timeout=10, stream=True)
                resp.raise_for_status()
                photo_bytes = BytesIO(resp.content)
                log.info(f"  Downloaded photo: {len(photo_bytes.getvalue())} bytes")
            except Exception as e:
                log.warning(f"  Photo download failed: {e}, falling back to text")
                photo_bytes = None

            if photo_bytes:
                # Отправляем фото с caption
                caption = text if len(text) <= max_caption else text[:1020] + "..."
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_bytes,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode=None,
                )
                # Если текст обрезан — отправляем полный отдельно
                if len(text) > max_caption:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        reply_markup=build_inline_keyboard(card_id, photo_count=0, has_description=False),
                    )
            else:
                # Fallback: текст без фото
                if len(text) > 4000:
                    text = text[:3990] + "...\n\n(обрезано по лимиту Telegram)"
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=None,
                )
        else:
            # Fallback: текст без фото
            if len(text) > 4000:
                text = text[:3990] + "...\n\n(обрезано по лимиту Telegram)"
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=None,
            )
        log.info(f"  [OK] {card_id}: {card.get('title', '')} ({card.get('year', '')})")
        return True
    except Exception as e:
        log.error(f"  [ERROR] {card_id}: {e}")
        # Fallback: отправить текстом
        try:
            if len(text) > 4000:
                text = text[:3990] + "..."
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
            return True
        except Exception as e2:
            log.error(f"  [FALLBACK ERROR] {card_id}: {e2}")
            return False


def send_car_card_sync(bot_token, chat_id, card, config, price_drop=False):
    """Синхронная обёртка для отправки одной карточки."""
    import asyncio
    from telegram import Bot

    bot = Bot(token=bot_token)
    return asyncio.run(send_car_card_async(bot, chat_id, card, config, price_drop=price_drop))


# ──────────────────────────────────────────────────────────────
# Dry-run
# ──────────────────────────────────────────────────────────────

def run_dry_run(input_path: str):
    """Блок 16.8: Dry-run — показать что будет отправлено без реальной отправки."""
    log.info("=" * 60)
    log.info("TELEGRAM SENDER — DRY RUN")
    log.info("=" * 60)

    candidates = load_audited_candidates(input_path)
    config = load_config(str(CONFIG_PATH))

    preview_lines = []
    stats = {
        "send_ready": 0,
        "hold_manual_review": 0,
        "duplicates": 0,
        "total": len(candidates),
    }

    for i, card in enumerate(candidates):
        action = card.get("action", "")
        if action == "send_ready":
            stats["send_ready"] += 1
        elif action == "hold_manual_review":
            stats["hold_manual_review"] += 1

        url = card.get("url", "")
        dedup_status = check_dedup(card)
        if dedup_status == "same_price":
            stats["duplicates"] += 1
            log.info(f"  [{i+1}/{len(candidates)}] [SKIP dedup=same_price] {card.get('card_id', '')}")
            continue
        elif dedup_status == "price_increased":
            log.info(f"  [{i+1}/{len(candidates)}] [SKIP price_increased] {card.get('card_id', '')}")
            update_last_seen(card)
            stats["duplicates"] += 1
            continue

        text = prepare_card_text(card, config)
        preview_lines.append({
            "card_id": card.get("card_id", ""),
            "title": card.get("title", ""),
            "year": card.get("year", 0),
            "action": action,
            "text_length": len(text),
            "preview": text[:200] + "...",
        })

        log.info(f"  [{i+1}/{len(candidates)}] [{action}] {card.get('title', '')} ({card.get('year', '')}) — {len(text)} chars")

    # Сохранить dry-run отчёт
    report = {
        "generated_at": datetime.now().isoformat(),
        "mode": "dry_run",
        "total_candidates": stats["total"],
        "send_ready": stats["send_ready"],
        "hold_manual_review": stats["hold_manual_review"],
        "duplicates": stats["duplicates"],
        "would_send": stats["total"] - stats["duplicates"],
        "previews": preview_lines,
    }

    report_path = RESULTS_DIR / "telegram_send_dry_run_report.yaml"
    # Убрать previews из YAML (слишком длинные), сохранить в md
    report_for_yaml = {k: v for k, v in report.items() if k != "previews"}
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.dump(report_for_yaml, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # Preview в markdown
    preview_path = RESULTS_DIR / "telegram_dry_run_preview.md"
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(f"# Telegram Dry-Run Preview — {len(preview_lines)} карточек\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        for p in preview_lines:
            f.write(f"### [{p['action']}] {p['title']} ({p['year']}) — {p['text_length']} chars\n\n")
            f.write(f"Card ID: {p['card_id']}\n\n")
            f.write(f"{p['preview']}\n\n")
            f.write("---\n\n")

    log.info(f"\n{'='*60}")
    log.info("DRY RUN SUMMARY:")
    log.info(f"  Total candidates: {stats['total']}")
    log.info(f"  Send ready: {stats['send_ready']}")
    log.info(f"  Hold: {stats['hold_manual_review']}")
    log.info(f"  Duplicates: {stats['duplicates']}")
    log.info(f"  Would send: {stats['total'] - stats['duplicates']}")
    log.info(f"  💾 Report: {report_path}")
    log.info(f"  💾 Preview: {preview_path}")
    log.info(f"{'='*60}")


# ──────────────────────────────────────────────────────────────
# Real send
# ──────────────────────────────────────────────────────────────

def run_send(limit: int = None):
    """Реальная отправка — multi-recipient support."""
    bot_token, chat_id_from_env = load_telegram_config()

    if not bot_token:
        log.error("❌ TELEGRAM_BOT_TOKEN не найден!")
        sys.exit(1)

    # Загрузить получателей из БД
    from feedback_store import get_enabled_recipients, check_dedup_with_chat_id, mark_sent_with_chat_id, update_last_seen, _build_stable_key

    recipients = get_enabled_recipients()
    if not recipients:
        # Fallback: использовать chat_id из .env
        log.warning("No recipients in DB, using env chat_id")
        recipients = [{"chat_id": chat_id_from_env, "role": "owner"}]

    log.info(f"Recipients: {len(recipients)}")
    for r in recipients:
        log.info(f"  {r['role']}: chat_id={r['chat_id']}")

    input_path = str(RESULTS_DIR / "telegram_candidates_audited.json")
    candidates = load_audited_candidates(input_path)
    config = load_config(str(CONFIG_PATH))

    if limit:
        candidates = candidates[:limit]
        log.info(f"Лимит: {limit}")

    log.info("=" * 60)
    log.info("TELEGRAM SENDER — REAL SEND")
    log.info("=" * 60)

    sent = 0
    skipped = 0

    for i, card in enumerate(candidates):
        # Send to each recipient with per-recipient dedup
        for recipient in recipients:
            r_chat_id = recipient["chat_id"]
            dedup_status = check_dedup_with_chat_id(card, r_chat_id)
            
            # Debug log
            log.info(f"  [{i+1}] Card {card.get('card_id')} -> {recipient['role']} ({r_chat_id}) | Key: {_build_stable_key(card)} | Status: {dedup_status}")

            if dedup_status == "same_price":
                log.info(f"  [{i+1}] [SKIP {recipient['role']}:same_price] {card.get('card_id', '')}")
                skipped += 1
                continue
            elif dedup_status == "price_increased":
                log.info(f"  [{i+1}] [SKIP {recipient['role']}:price_increased] {card.get('card_id', '')}")
                skipped += 1
                continue

            price_drop = dedup_status == "price_drop"
            log.info(f"  [{i+1}] [SEND {recipient['role']}] {card.get('card_id', '')} (price_drop={price_drop})")
            success = send_car_card_sync(bot_token, r_chat_id, card, config, price_drop=price_drop)
            if success:
                status = "price_drop" if price_drop else "new"
                mark_sent_with_chat_id(card, r_chat_id, status=status)
                sent += 1
            else:
                skipped += 1

    log.info(f"\n{'='*60}")
    log.info("SEND SUMMARY:")
    log.info(f"  Sent: {sent}")
    log.info(f"  Skipped: {skipped}")
    log.info(f"{'='*60}")

    # Финальный отчёт
    report = {
        "block": 16,
        "generated_at": datetime.now().isoformat(),
        "total_candidates": len(candidates),
        "sent": sent,
        "skipped_duplicate": skipped,
        "skipped_do_not_send": 0,
        "feedback_db_ready": True,
        "buttons_ready": True,
        "comments_ready": True,
        "telegram_v1_ready": sent > 0,
    }

    report_path = RESULTS_DIR / "telegram_sender_report.yaml"
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.dump(report, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    log.info(f"  💾 Report: {report_path}")


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Telegram Sender v1")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run без отправки")
    parser.add_argument("--send", action="store_true", help="Реальная отправка")
    parser.add_argument("--limit", type=int, default=None, help="Лимит карточек")
    parser.add_argument("--input", type=str, default=None, help="Путь к audited JSON")
    args = parser.parse_args()

    if args.dry_run:
        input_path = args.input or str(RESULTS_DIR / "telegram_candidates_audited.json")
        run_dry_run(input_path)
    elif args.send:
        run_send(limit=args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
