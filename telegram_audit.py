"""
telegram_audit.py — Блок 15: аудит Telegram-кандидатов перед реальной отправкой.

Выполняет:
  15.1  Загрузка входных файлов
  15.2  Вытащить 16 Telegram-кандидатов
  15.3  Аудит региона
  15.4  Аудит юридических ограничений
  15.5  Аудит коробки
  15.6  Аудит привода
  15.7  Аудит completeness (engine/transmission/owners)
  15.8  Проверить score explanation
  15.9  Проверить завышенные оценки
  15.10 Сформировать финальный список (send_ready / hold / do_not_send)
  15.11 Обновить Telegram preview после аудита
  15.12 Финальный QA отчёт
  15.13 Решение о запуске Telegram sender
"""

import json
import yaml
import re
import sys
import logging
from pathlib import Path
from datetime import datetime

from config_loader import load_config, get_models, get_model_by_id
from cards_loader import normalize_card
from model_matcher import match_card_to_model
from reject_engine import check_reject
from price_scorer_v2 import score_price
from mileage_scorer import score_mileage
from powertrain_scorer import score_engine, score_transmission
from equipment_scorer import score_equipment
from region_filter import check_region, extract_region_from_card
from region_parser import parse_region as parse_region_v2
from legal_parser import parse_legal as parse_legal_v2
from telegram_card_formatter import format_car_card

from base import BASE_DIR, RESULTS_DIR, log

CONFIG_PATH = RESULTS_DIR / "awd_liquid_full_config.yaml"
SAMPLE_PATH = RESULTS_DIR / "mobile_first_page_sample.json"
DRY_RUN_REPORT = RESULTS_DIR / "mobile_telegram_dry_run_report.yaml"
PREVIEW_PATH = RESULTS_DIR / "mobile_telegram_preview.md"
FINAL_REPORT = RESULTS_DIR / "mobile_sampler_final_report.yaml"

# ──────────────────────────────────────────────────────────────
# Блок 15.3 — Разрешённые регионы
# ──────────────────────────────────────────────────────────────

ALLOWED_REGIONS = [
    "Москва", "Московская область", "Москва и МО",
    "Ярославль", "Ярославская область", "Ярославская обл.",
    "Тверь", "Тверская область", "Тверская обл.",
    "Владимир", "Владимирская область", "Владимирская обл.",
    "Калуга", "Калужская область", "Калужская обл.",
    "Рязань", "Рязанская область", "Рязанская обл.",
    "Тула", "Тульская область", "Тульская обл.",
]

LEGAL_REJECT_KEYWORDS = [
    "Есть ограничение", "Ограничения", "Запрет регистрационных действий",
    "Залог", "Арест", "огранич", "запрет",
]

# ──────────────────────────────────────────────────────────────
# Утилиты
# ──────────────────────────────────────────────────────────────

def load_input_files():
    """Блок 15.1 — Загрузить все входные файлы."""
    log.info("[15.1] Загрузка входных файлов...")

    files = {
        "mobile_first_page_sample.json": SAMPLE_PATH,
        "mobile_telegram_dry_run_report.yaml": DRY_RUN_REPORT,
        "mobile_telegram_preview.md": PREVIEW_PATH,
        "mobile_sampler_final_report.yaml": FINAL_REPORT,
        "awd_liquid_full_config.yaml": CONFIG_PATH,
    }

    for name, path in files.items():
        if not path.exists():
            log.error(f"  ❌ Файл не найден: {path}")
            sys.exit(1)
        log.info(f"  ✅ {name}")

    with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
        sample = json.load(f)

    with open(DRY_RUN_REPORT, "r", encoding="utf-8") as f:
        dry_run = yaml.safe_load(f)

    config = load_config(str(CONFIG_PATH))
    log.info(f"  Конфиг: {len(get_models(config))} моделей")
    log.info(f"  Sample: {sample.get('cards_total', 0)} карточек")

    return sample, dry_run, config


def score_card(card: dict, config: dict) -> dict:
    """Скорит одну карточку (v4) — копия из run_telegram_pipeline.py."""
    global_rules = config.get("global_rules", {})
    model_id = match_card_to_model(card, config)

    if not model_id:
        card["model_id"] = None
        card["decision"] = "skipped_unknown_model"
        card["score"] = 0
        return card

    card["model_id"] = model_id
    model_rules = get_model_by_id(config, model_id)

    if not model_rules:
        card["decision"] = "error"
        card["score"] = 0
        return card

    # Reject
    reject_result = check_reject(card, model_rules, global_rules)
    if reject_result["rejected"]:
        card["decision"] = "reject"
        card["score"] = 0
        card["reject_reasons"] = reject_result["reasons"]
        return card

    # Scoring
    price_r = score_price(card.get("price"), model_rules.get("price", {}))
    mileage_r = score_mileage(card.get("mileage"), model_rules.get("mileage", {}))
    engine_r = score_engine(card.get("engine", ""), model_rules.get("engines", {}))
    trans_r = score_transmission(card.get("transmission", ""), model_rules.get("transmissions", {}))
    equip_r = score_equipment(card, model_rules)

    base_score = 50
    total = base_score + price_r["score"] + mileage_r["score"] + \
            engine_r["score"] + trans_r["score"] + equip_r["score"]
    total = max(0, min(100, total))

    # Decision
    price_cat = price_r["category"]
    mileage_cat = mileage_r["category"]
    bonus_count = len(card.get("features", []))
    warnings = card.get("missing_fields", [])

    if (total >= 80 and price_cat in ("excellent", "good")
            and mileage_cat in ("excellent", "good")
            and bonus_count >= 2 and not warnings):
        decision = "excellent_candidate"
    elif total >= 80:
        decision = "good_candidate"
    elif total >= 55:
        decision = "watch"
    elif total >= 40:
        decision = "weak"
    else:
        decision = "reject"

    card["score"] = total
    card["decision"] = decision
    card["price_score"] = price_r["score"]
    card["mileage_score"] = mileage_r["score"]
    card["engine_score"] = engine_r["score"]
    card["transmission_score"] = trans_r["score"]
    card["equipment_score"] = equip_r["score"]
    card["price_category"] = price_r.get("category", "")
    card["price_status"] = price_r.get("price_status", "")
    card["engine_category"] = engine_r.get("category", "")
    card["transmission_category"] = trans_r.get("category", "")
    card["bonus_reasons"] = []
    card["penalty_reasons"] = []

    if price_r["score"] > 0:
        card["bonus_reasons"].append(price_r["explanation"])
    elif price_r["score"] < 0:
        card["penalty_reasons"].append(price_r["explanation"])
    if mileage_r["score"] > 0:
        card["bonus_reasons"].append(mileage_r["explanation"])
    elif mileage_r["score"] < 0:
        card["penalty_reasons"].append(mileage_r["explanation"])
    if engine_r["score"] > 0:
        card["bonus_reasons"].append(engine_r["explanation"])
    if trans_r["score"] > 0:
        card["bonus_reasons"].append(trans_r["explanation"])
    if equip_r["score"] > 0:
        card["bonus_reasons"].append(equip_r["explanation"])

    return card


def load_mobile_sample(path: str) -> list:
    """Загрузить карточки из mobile_first_page_sample.json и привести к формату pipeline."""
    with open(path, "r", encoding="utf-8") as f:
        sample = json.load(f)

    cards = []
    for c in sample.get("cards", []):
        specs = c.get("specs", {})

        trans_raw = specs.get("transmission", {}).get("value", "unknown")
        trans_map = {
            "Автомат": "automatic", "Автоматическая": "automatic", "automatic": "automatic",
            "Робот": "dsg", "DSG": "dsg", "dsg": "dsg",
            "Вариатор": "cvt", "CVT": "cvt", "cvt": "cvt",
            "Механика": "manual", "Механическая": "manual", "manual": "manual",
        }
        transmission = trans_map.get(trans_raw, "unknown")

        drive_raw = specs.get("drive", {}).get("value", "unknown")
        drive_map = {"Полный": "awd", "awd": "awd", "Передний": "fwd", "Задний": "rwd",
                     "4WD": "awd", "4MATIC": "awd", "quattro": "awd", "xDrive": "awd"}
        drive = drive_map.get(drive_raw, "unknown")

        region = specs.get("region", {}).get("value", "unknown")
        engine = specs.get("engine", {}).get("value", "unknown")
        owners = specs.get("owners", {}).get("value", "unknown")
        legal = specs.get("legal_restrictions", {}).get("value", "unknown")

        raw = (c.get("raw_text", "") + " " + c.get("mobile_detail_raw_text", "")).lower()
        features = []
        feature_map = {
            "7 мест": "7_seats", "кож": "leather", "панорам": "panorama",
            "камера": "camera_360", "webasto": "webasto", "кожа": "leather",
            "вентиляц": "ventilation", "360": "camera_360",
        }
        for kw, feat in feature_map.items():
            if kw in raw:
                features.append(feat)

        card = {
            "url": c.get("url", c.get("mobile_url", "")),
            "title": c.get("title", ""),
            "brand": c.get("model_guess", ""),
            "model": c.get("model_guess", ""),
            "year": c.get("year", 0),
            "price": c.get("price", 0),
            "mileage": c.get("mileage", 0),
            "engine": engine,
            "transmission": transmission,
            "drive": drive,
            "region": region,
            "owners": owners,
            "legal_restrictions": legal,
            "features": features,
            "card_id": c.get("card_id", ""),
            "mobile_url": c.get("mobile_url", ""),
            "specs": specs,
            "raw_text": c.get("raw_text", ""),
            "mobile_detail_raw_text": c.get("mobile_detail_raw_text", ""),
        }
        cards.append(card)

    return cards


def check_region_allowed(region: str) -> tuple:
    """Проверить регион. Возвращает (is_allowed, status)."""
    if region == "unknown":
        return False, "warning_unknown"

    for allowed in ALLOWED_REGIONS:
        if allowed.lower() in region.lower() or region.lower() in allowed.lower():
            return True, "allowed"

    return False, "reject_wrong_region"


def check_legal_restrictions(legal: str) -> tuple:
    """Проверить юридические ограничения. Возвращает (is_clean, status)."""
    if legal == "unknown":
        return False, "warning_unknown"

    # "Без ограничений" — это OK
    if "без ограничен" in legal.lower():
        return True, "clean"

    # Проверить на реальные проблемы
    for kw in LEGAL_REJECT_KEYWORDS:
        if kw.lower() in legal.lower():
            return False, "reject"

    return True, "clean"


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("BLOCK 15 — TELEGRAM CANDIDATES AUDIT")
    log.info("=" * 60)

    # ── 15.1 ──
    sample, dry_run, config = load_input_files()

    # ── 15.2 ── Вытащить 16 кандидатов
    log.info("\n[15.2] Загрузка и скоринг 30 карточек...")
    raw_cards = load_mobile_sample(str(SAMPLE_PATH))

    candidates = []
    all_scored = []
    for raw in raw_cards:
        card = normalize_card(raw)
        # Переопределить поля из specs
        card["engine"] = raw.get("engine", "unknown")
        card["transmission"] = raw.get("transmission", "unknown")
        card["drive"] = raw.get("drive", "unknown")
        card["region"] = raw.get("region", "unknown")
        card["owners"] = raw.get("owners", "unknown")
        card["legal_restrictions"] = raw.get("legal_restrictions", "unknown")
        card["card_id"] = raw.get("card_id", "")
        card["mobile_url"] = raw.get("mobile_url", "")
        card["specs"] = raw.get("specs", {})
        card["raw_text"] = raw.get("raw_text", "")
        card["mobile_detail_raw_text"] = raw.get("mobile_detail_raw_text", "")

        # Manual filter
        if card.get("transmission") == "manual":
            continue

        card = score_card(card, config)

        all_scored.append(card)

        if card["decision"] in ("excellent_candidate", "good_candidate", "watch"):
            candidates.append(card)

    log.info(f"  Найдено {len(candidates)} кандидатов (good/watch/excellent)")

    # ── 15.3–15.9 — Аудит каждой карточки ──
    log.info("\n[15.3–15.9] Аудит кандидатов...")

    send_ready = []
    hold_manual = []
    do_not_send = []

    audit_checks = {
        "region": {"passed": 0, "failed": 0, "warnings": 0},
        "legal_restrictions": {"passed": 0, "failed": 0, "warnings": 0},
        "engine": {"passed": 0, "failed": 0, "warnings": 0},
        "transmission": {"passed": 0, "failed": 0, "warnings": 0},
        "drive": {"passed": 0, "failed": 0, "warnings": 0},
        "completeness": {"passed": 0, "failed": 0, "warnings": 0},
        "score_explanation": {"passed": 0, "failed": 0, "warnings": 0},
    }

    for card in candidates:
        reasons_hold = []
        reasons_reject = []
        card["audit"] = {}

        # ── 15.3 ── Регион
        region = card.get("region", "unknown")

        # Fallback: если unknown, пробуем распарсить из raw_text
        if region == "unknown":
            raw = (card.get("raw_text", "") + " " +
                   card.get("mobile_detail_raw_text", ""))
            rr = parse_region_v2(raw)
            if rr["allowed"]:
                region = rr["normalized"]
                card["region"] = region

        region_allowed, region_status = check_region_allowed(region)
        card["audit"]["region_status"] = region_status
        card["audit"]["region_value"] = region

        if region_status == "reject_wrong_region":
            reasons_reject.append(f"wrong_region: {region}")
            audit_checks["region"]["failed"] += 1
        elif region_status == "warning_unknown":
            # Unknown — warning, но НЕ блокируем отправку (Telegram v1 — разметка рынка)
            audit_checks["region"]["warnings"] += 1
        else:
            audit_checks["region"]["passed"] += 1

        # Обновить audit region_value (после fallback)
        card["audit"]["region_value"] = region

        # ── 15.4 ── Юридические ограничения
        legal = card.get("legal_restrictions", "unknown")

        # Fallback: если unknown, пробуем распарсить из raw_text через legal_parser
        if legal == "unknown":
            raw = (card.get("raw_text", "") + " " +
                   card.get("mobile_detail_raw_text", ""))
            lr = parse_legal_v2(raw)
            if lr["status"] == "clear":
                legal = "Без ограничений"
                card["legal_restrictions"] = legal
            elif lr["status"] == "restricted":
                legal = lr["value"]
                card["legal_restrictions"] = legal

        legal_clean, legal_status = check_legal_restrictions(legal)
        card["audit"]["legal_status"] = legal_status
        card["audit"]["legal_value"] = legal

        if legal_status == "reject":
            reasons_reject.append(f"legal_restrictions: {legal}")
            audit_checks["legal_restrictions"]["failed"] += 1
        elif legal_status == "warning_unknown":
            # Unknown — warning, но НЕ блокируем (Telegram v1 — разметка рынка)
            audit_checks["legal_restrictions"]["warnings"] += 1
        else:
            audit_checks["legal_restrictions"]["passed"] += 1

        # Обновить audit legal_value после fallback
        card["audit"]["legal_value"] = legal

        # ── 15.5 ── Коробка (hard-stop: unknown → reject)
        trans = card.get("transmission", "unknown")
        if trans == "manual":
            reasons_reject.append("manual_transmission")
            audit_checks["transmission"]["failed"] += 1
        elif trans == "unknown":
            reasons_reject.append("transmission_unknown")
            audit_checks["transmission"]["failed"] += 1
        else:
            audit_checks["transmission"]["passed"] += 1

        # ── 15.5a ── Двигатель (hard-stop: unknown → reject)
        engine = card.get("engine", "unknown")
        if engine == "unknown":
            reasons_reject.append("engine_unknown")
            audit_checks["engine"]["failed"] += 1
        else:
            audit_checks["engine"]["passed"] += 1

        # ── 15.6 ── Привод (hard-stop: unknown → reject)
        drive = card.get("drive", "unknown")
        if drive not in ("awd", "4matic", "quattro", "xdrive", "4wd"):
            if drive == "unknown":
                reasons_reject.append("drive_unknown")
                audit_checks["drive"]["failed"] += 1
            else:
                reasons_reject.append(f"not_awd: {drive}")
                audit_checks["drive"]["failed"] += 1
        else:
            audit_checks["drive"]["passed"] += 1

        # ── 15.7 ── Completeness
        required_fields = {
            "engine": card.get("engine", "unknown"),
            "transmission": card.get("transmission", "unknown"),
            "drive": card.get("drive", "unknown"),
            "price": card.get("price", 0),
            "mileage": card.get("mileage", 0),
        }
        missing = [k for k, v in required_fields.items() if not v or v == "unknown"]
        if missing:
            reasons_hold.append(f"missing_fields: {', '.join(missing)}")
            audit_checks["completeness"]["warnings"] += 1
        else:
            audit_checks["completeness"]["passed"] += 1

        # ── 15.8 ── Score explanation
        has_explanation = bool(card.get("bonus_reasons") or card.get("penalty_reasons"))
        if not has_explanation:
            reasons_hold.append("no_score_explanation")
            audit_checks["score_explanation"]["warnings"] += 1
        else:
            audit_checks["score_explanation"]["passed"] += 1

        # ── 15.9 ── Завышенные оценки
        if card.get("score", 0) >= 90:
            # Проверить что score обоснован
            price = card.get("price", 0)
            model_rules = get_model_by_id(config, card.get("model_id"))
            if model_rules:
                price_r = score_price(price, model_rules.get("price", {}))
                if price_r["category"] == "reject" or price_r["score"] < -20:
                    reasons_hold.append(f"suspicious_high_score: price_category={price_r['category']}")

        # ── Классификация ──
        card["audit"]["reasons_hold"] = reasons_hold
        card["audit"]["reasons_reject"] = reasons_reject

        if reasons_reject:
            card["audit"]["action"] = "do_not_send"
            do_not_send.append(card)
            log.info(f"  ❌ {card.get('card_id', '?')} {card.get('title', '')} ({card.get('year', '')}) — REJECT: {', '.join(reasons_reject)}")
        elif reasons_hold:
            card["audit"]["action"] = "hold_manual_review"
            hold_manual.append(card)
            log.info(f"  ⚠️ {card.get('card_id', '?')} {card.get('title', '')} ({card.get('year', '')}) — HOLD: {', '.join(reasons_hold)}")
        else:
            card["audit"]["action"] = "send_ready"
            send_ready.append(card)
            log.info(f"  ✅ {card.get('card_id', '?')} {card.get('title', '')} ({card.get('year', '')}) — READY (score={card.get('score', 0)})")

    # ── 15.10 ── Сохранить audited candidates
    log.info(f"\n[15.10] Финальный список:")
    log.info(f"  Send ready: {len(send_ready)}")
    log.info(f"  Hold: {len(hold_manual)}")
    log.info(f"  Do not send: {len(do_not_send)}")

    audited_data = {
        "generated_at": datetime.now().isoformat(),
        "total_candidates": len(candidates),
        "send_ready": len(send_ready),
        "hold_manual_review": len(hold_manual),
        "do_not_send": len(do_not_send),
        "cards": [
            {
                "card_id": c.get("card_id", ""),
                "title": c.get("title", ""),
                "year": c.get("year", 0),
                "price": c.get("price", 0),
                "score": c.get("score", 0),
                "decision": c.get("decision", ""),
                "action": c["audit"]["action"],
                "region": c["audit"].get("region_value", ""),
                "region_status": c["audit"].get("region_status", ""),
                "legal_status": c["audit"].get("legal_status", ""),
                "reasons_hold": c["audit"].get("reasons_hold", []),
                "reasons_reject": c["audit"].get("reasons_reject", []),
                "url": c.get("url", ""),
                "mobile_url": c.get("mobile_url", ""),
            }
            for c in candidates
        ],
    }

    audited_path = RESULTS_DIR / "telegram_candidates_audited.json"
    with open(audited_path, "w", encoding="utf-8") as f:
        json.dump(audited_data, f, ensure_ascii=False, indent=2)
    log.info(f"  💾 {audited_path}")

    # ── 15.11 ── Telegram preview для send_ready
    log.info("\n[15.11] Создание audited preview...")

    preview_lines = []
    for card in send_ready:
        card_text = format_car_card(card, config)
        preview_lines.append(card_text)

    # Добавим регион и юридический статус в начало
    audited_preview_path = RESULTS_DIR / "telegram_preview_audited.md"
    with open(audited_preview_path, "w", encoding="utf-8") as f:
        f.write(f"# Telegram Preview (Audited) — {len(send_ready)} карточек\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"---\n\n")
        f.write("\n---\n\n".join(preview_lines))
    log.info(f"  💾 {audited_preview_path}")

    # Hold review
    if hold_manual:
        hold_path = RESULTS_DIR / "telegram_hold_review.md"
        with open(hold_path, "w", encoding="utf-8") as f:
            f.write(f"# Hold for Manual Review — {len(hold_manual)} карточек\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write("---\n\n")
            for card in hold_manual:
                f.write(f"### {card.get('title', '')} ({card.get('year', '')}) — Score: {card.get('score', 0)}\n\n")
                f.write(f"- **Card ID:** {card.get('card_id', '')}\n")
                f.write(f"- **Price:** {card.get('price', 0):,} ₽\n")
                f.write(f"- **Region:** {card['audit'].get('region_value', 'unknown')} ({card['audit'].get('region_status', '')})\n")
                f.write(f"- **Legal:** {card['audit'].get('legal_value', 'unknown')} ({card['audit'].get('legal_status', '')})\n")
                f.write(f"- **Reasons:** {', '.join(card['audit'].get('reasons_hold', []))}\n")
                f.write(f"- **URL:** {card.get('url', '')}\n\n")
                f.write("---\n\n")
        log.info(f"  💾 {hold_path}")

    # ── 15.12 ── Финальный QA отчёт
    log.info("\n[15.12] Финальный QA отчёт...")

    audit_report = {
        "block": 15,
        "generated_at": datetime.now().isoformat(),
        "total_candidates": len(candidates),
        "send_ready": len(send_ready),
        "hold_manual_review": len(hold_manual),
        "do_not_send": len(do_not_send),
        "checks": {},
        "blockers": [],
        "next_step": "",
    }

    for check_name, stats in audit_checks.items():
        audit_report["checks"][check_name] = {
            "passed": stats["passed"],
            "failed": stats["failed"],
            "warnings": stats["warnings"],
        }

    # Blockers
    if any(c["audit"]["action"] == "do_not_send" for c in do_not_send):
        audit_report["blockers"].append(f"{len(do_not_send)} карточек отклонено (legal/wrong_region/manual/not_awd)")
    if hold_manual:
        audit_report["blockers"].append(f"{len(hold_manual)} карточек на manual review")

    # Next step
    sender_ready = len(send_ready) > 0 and not any(
        c.get("legal_restrictions", "").lower() in ["есть ограничение"] for c in send_ready
    )
    audit_report["telegram_sender_ready"] = sender_ready
    audit_report["next_step"] = "telegram_sender.py" if sender_ready else "fix blockers first"

    report_path = RESULTS_DIR / "telegram_candidates_audit_report.yaml"
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.dump(audit_report, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    log.info(f"  💾 {report_path}")

    # ── 15.13 ── Решение
    log.info(f"\n[15.13] Решение:")
    log.info(f"  Telegram sender ready: {sender_ready}")
    log.info(f"  Send ready: {len(send_ready)}")
    log.info(f"  Hold: {len(hold_manual)}")
    log.info(f"  Do not send: {len(do_not_send)}")

    if sender_ready:
        log.info(f"  ✅ Можно запускать telegram_sender.py")
    else:
        log.info(f"  ❌ Не готово — см. blockers в отчёте")

    # Summary
    log.info(f"\n{'='*60}")
    log.info("AUDIT SUMMARY:")
    log.info(f"{'='*60}")
    for check_name, stats in audit_checks.items():
        log.info(f"  {check_name}: {stats['passed']} passed, {stats['failed']} failed, {stats['warnings']} warnings")
    log.info(f"{'='*60}")


if __name__ == "__main__":
    main()
