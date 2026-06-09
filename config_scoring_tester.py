"""
БЛОК 10: config_scoring_tester.py — итоговый скорер + CLI

Использует все модули:
- config_loader
- cards_loader
- model_matcher
- reject_engine
- price_scorer
- mileage_scorer
- powertrain_scorer
- equipment_scorer

Команды:
  python config_scoring_tester.py --limit 1     # одна карточка
  python config_scoring_tester.py --limit 5     # пять карточек
  python config_scoring_tester.py --limit 15    # пятнадцать карточек
  python config_scoring_tester.py --all         # все доступные
"""
import argparse
import yaml
import json
import glob
import logging
from pathlib import Path
from datetime import datetime

from config_loader import load_config, get_models, get_model_by_id, validate_config_basic
from cards_loader import load_cards, normalize_card
from model_matcher import match_card_to_model
from reject_engine import check_reject
from price_scorer_v2 import score_price
from mileage_scorer import score_mileage
from powertrain_scorer import score_engine, score_transmission
from equipment_scorer import score_equipment

from base import BASE_DIR, RESULTS_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

CONFIG_PATH = RESULTS_DIR / "awd_liquid_full_config.yaml"

# Пороги решений v2 — excellent только при условиях
def get_decision(score: int, rejected: bool, price_category: str = "", mileage_category: str = "",
                 strong_bonus_count: int = 0, has_warnings: bool = False) -> str:
    """Decision engine v2 — excellent только при условиях."""
    if rejected:
        return "reject"
    if score < 40:
        return "reject"

    # excellent_candidate — только если выполнены ВСЕ условия:
    if (score >= 80
            and price_category in ("excellent", "good")
            and mileage_category in ("excellent", "good")
            and strong_bonus_count >= 2
            and not has_warnings):
        return "excellent_candidate"

    # good_candidate
    if score >= 80 and not rejected:
        return "good_candidate"

    # watch
    if score >= 55:
        return "watch"

    # weak
    if score >= 40:
        return "weak"

    return "reject"


def score_card(card: dict, config: dict) -> dict:
    """Скорит одну карточку по полному конфигу."""
    global_rules = config.get("global_rules", {})

    # 1. Определяем модель
    model_id = match_card_to_model(card, config)
    if not model_id:
        return {
            "url": card.get("url", ""),
            "title": card.get("title", ""),
            "model_id": None,
            "decision": "skipped_unknown_model",
            "score": 0,
            "price_score": 0,
            "mileage_score": 0,
            "engine_score": 0,
            "transmission_score": 0,
            "equipment_score": 0,
            "reject_reasons": [],
            "bonus_reasons": [],
            "penalty_reasons": [],
            "warnings": ["Unknown model — cannot apply rules"],
            "missing_fields": card.get("missing_fields", []),
        }

    model_rules = get_model_by_id(config, model_id)
    if not model_rules:
        return {
            "url": card.get("url", ""),
            "title": card.get("title", ""),
            "model_id": model_id,
            "decision": "error",
            "score": 0,
            "warnings": [f"Model {model_id} not found in config"],
        }

    # 2. Reject-проверка (раньше скоринга!)
    reject_result = check_reject(card, model_rules, global_rules)

    reject_reasons = reject_result["reasons"]
    penalty_reasons = []
    bonus_reasons = []
    warnings = []

    if reject_result["rejected"]:
        return {
            "url": card.get("url", ""),
            "title": card.get("title", ""),
            "model_id": model_id,
            "decision": "reject",
            "score": 0,
            "price_score": 0,
            "mileage_score": 0,
            "engine_score": 0,
            "transmission_score": 0,
            "equipment_score": 0,
            "reject_reasons": reject_reasons,
            "bonus_reasons": [],
            "penalty_reasons": reject_reasons,
            "warnings": [],
            "explanation": f"REJECT: {', '.join(reject_reasons)}",
        }

    # 3. Ценовой скоринг
    price_result = score_price(card.get("price"), model_rules.get("price", {}))
    if price_result["score"] > 0:
        bonus_reasons.append(price_result["explanation"])
    elif price_result["score"] < 0:
        penalty_reasons.append(price_result["explanation"])

    # 4. Пробег
    mileage_result = score_mileage(card.get("mileage"), model_rules.get("mileage", {}))
    if mileage_result["score"] > 0:
        bonus_reasons.append(mileage_result["explanation"])
    elif mileage_result["score"] < 0:
        penalty_reasons.append(mileage_result["explanation"])

    # 5. Двигатель
    engine_result = score_engine(card.get("engine", ""), model_rules.get("engines", {}))
    if engine_result["score"] > 0:
        bonus_reasons.append(engine_result["explanation"])
    elif engine_result["score"] < 0:
        penalty_reasons.append(engine_result["explanation"])

    # 6. Коробка
    trans_result = score_transmission(card.get("transmission", ""), model_rules.get("transmissions", {}))
    if trans_result["score"] > 0:
        bonus_reasons.append(trans_result["explanation"])
    elif trans_result["score"] < 0:
        penalty_reasons.append(trans_result["explanation"])

    # 7. Комплектация
    equip_result = score_equipment(card, model_rules)
    if equip_result["score"] > 0:
        bonus_reasons.append(equip_result["explanation"])

    # 8. Итоговый score (база = 50)
    base_score = 50
    total_score = base_score + price_result["score"] + mileage_result["score"] + \
                  engine_result["score"] + trans_result["score"] + equip_result["score"]
    total_score = max(0, min(100, total_score))

    # 9. Решение
    decision = get_decision(
        total_score, False,
        price_category=price_result["category"],
        mileage_category=mileage_result["category"],
        strong_bonus_count=len(card.get("features", [])),
        has_warnings=bool(warnings),
    )

    # 10. Missing fields
    missing = card.get("missing_fields", [])
    if missing:
        warnings.append(f"Missing fields: {', '.join(missing)}")

    return {
        "url": card.get("url", ""),
        "title": card.get("title", ""),
        "model_id": model_id,
        "decision": decision,
        "score": total_score,
        "price_score": price_result["score"],
        "mileage_score": mileage_result["score"],
        "engine_score": engine_result["score"],
        "transmission_score": trans_result["score"],
        "equipment_score": equip_result["score"],
        "reject_reasons": reject_reasons,
        "bonus_reasons": bonus_reasons,
        "penalty_reasons": penalty_reasons,
        "warnings": warnings,
        "explanation": _build_explanation(card, model_id, price_result, mileage_result,
                                           engine_result, trans_result, equip_result,
                                           bonus_reasons, penalty_reasons),
    }


def _build_explanation(card, model_id, price_r, mileage_r, engine_r, trans_r, equip_r,
                        bonuses, penalties) -> str:
    parts = [f"Model: {model_id}"]

    if card.get("price"):
        parts.append(f"Price: {card['price']:,} ₽ → {price_r['category']} ({price_r['score']:+d})")
    if card.get("mileage"):
        parts.append(f"Mileage: {card['mileage']:,} км → {mileage_r['category']} ({mileage_r['score']:+d})")
    if card.get("engine"):
        parts.append(f"Engine: {card['engine']} → {engine_r['category']} ({engine_r['score']:+d})")
    if card.get("transmission"):
        parts.append(f"Trans: {card['transmission']} → {trans_r['category']} ({trans_r['score']:+d})")
    if equip_r["bonuses"]:
        parts.append(f"Equipment: +{equip_r['score']} ({', '.join(equip_r['bonuses'])})")

    return " | ".join(parts)


def build_test_cards() -> list[dict]:
    """Создаёт тестовые карточки: фейковые для reject-логики ПЕРВЫМИ + реальные после."""
    cards = []

    # Фейковые карточки для проверки reject-логики — ИДУТ ПЕРВЫМИ
    test_cards = [
        # Красная автотека
        {
            "url": "test://red_autoteka",
            "title": "Audi Q5 2015 2.0 TDI quattro",
            "brand": "Audi", "model": "Q5",
            "year": 2015, "price": 1800000, "mileage": 120000,
            "drive": "awd", "engine": "2.0 TDI", "transmission": "automatic",
            "autoteka_status": "red", "features": ["leather", "panorama"],
        },
        # Без AWD (для модели где требуется AWD)
        {
            "url": "test://fwd_q5",
            "title": "Audi Q5 2014 2.0 TFSI передний привод",
            "brand": "Audi", "model": "Q5",
            "year": 2014, "price": 1600000, "mileage": 90000,
            "drive": "fwd", "engine": "2.0 TFSI", "transmission": "automatic",
            "autoteka_status": "green", "features": [],
        },
        # Топовая машина — excellent candidate
        {
            "url": "test://excellent_santa_fe",
            "title": "Hyundai Santa Fe III Рестайлинг 2.2 CRDi AWD Executive",
            "brand": "Hyundai", "model": "Santa Fe",
            "year": 2016, "price": 1750000, "mileage": 80000,
            "drive": "awd", "engine": "2.2 CRDi diesel", "transmission": "automatic",
            "autoteka_status": "green", "features": ["leather", "panorama", "7_seats", "ventilation", "rear_camera", "keyless"],
        },
        # Выше рынка без комплектации
        {
            "url": "test://overpriced_bare",
            "title": "Kia Sportage 2015 2.0 базовая",
            "brand": "Kia", "model": "Sportage",
            "year": 2015, "price": 1600000, "mileage": 160000,
            "drive": "awd", "engine": "2.0 petrol", "transmission": "automatic",
            "autoteka_status": "green", "features": [],
        },
        # Большой пробег
        {
            "url": "test://high_mileage",
            "title": "Mitsubishi Pajero IV 3.2 DI-D 2010",
            "brand": "Mitsubishi", "model": "Pajero",
            "year": 2010, "price": 1500000, "mileage": 320000,
            "drive": "awd", "engine": "3.2 DI-D diesel", "transmission": "automatic",
            "autoteka_status": "green", "features": ["leather"],
        },
        # 7-местная с бонусами
        {
            "url": "test://seven_seat_sorento",
            "title": "Kia Sorento Prime 2.2 CRDi GT-Line 7 мест кожа панорама",
            "brand": "Kia", "model": "Sorento Prime",
            "year": 2017, "price": 2000000, "mileage": 95000,
            "drive": "awd", "engine": "2.2 CRDi diesel", "transmission": "automatic",
            "autoteka_status": "green", "features": ["7_seats", "leather", "panorama", "gt_line", "ventilation", "rear_camera", "keyless", "led"],
        },
    ]

    for tc in test_cards:
        cards.append(normalize_card(tc))

    # Реальные карточки из evaluations — ПОСЛЕ фейковых
    for json_file in [
        "results/evaluations_audi_q5_8r.json",
        "results/evaluations_hyundai_santa_fe.json",
        "results/evaluations_hyundai_grand_santa_fe.json",
        "results/evaluations_audi_q5.json",
    ]:
        path = BASE_DIR / json_file
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for c in data:
                    cards.append(normalize_card(c))
            elif isinstance(data, dict):
                for c in data.get("cards", []):
                    cards.append(normalize_card(c))

    return cards


def main():
    parser = argparse.ArgumentParser(description="Config Scoring Tester")
    parser.add_argument("--limit", type=int, default=None, help="Сколько карточек тестировать")
    parser.add_argument("--all", action="store_true", help="Все доступные карточки")
    parser.add_argument("--cards-file", type=str, default=None, help="Путь к JSON с карточками")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("CONFIG SCORING TESTER — БЛОК 11")
    log.info("=" * 60)

    # 1. Загрузка конфига
    log.info(f"Загрузка конфига: {CONFIG_PATH}")
    config = load_config(str(CONFIG_PATH))
    validation = validate_config_basic(config)
    log.info(f"Конфиг: {validation['models_total']} моделей, status={validation['status']}")
    if validation["errors"]:
        log.error(f"Errors: {validation['errors']}")

    # 2. Загрузка карточек
    if args.cards_file:
        cards = load_cards(args.cards_file)
        log.info(f"Загрузка из файла: {args.cards_file}")
    else:
        cards = build_test_cards()
    log.info(f"Карточек: {len(cards)}")

    # Limit
    if args.limit:
        cards = cards[:args.limit]
        log.info(f"Лимит: {args.limit}")
    elif args.all:
        log.info("Все карточки")
    else:
        cards = cards[:5]
        log.info(f"По умолчанию: 5 карточек")

    # 3. Скоринг
    results = []
    for i, card in enumerate(cards):
        log.info(f"\n[{i+1}/{len(cards)}] {card.get('title', 'unknown')[:60]}...")
        result = score_card(card, config)
        results.append(result)
        log.info(f"  → decision={result['decision']}, score={result['score']}")
        if result.get("reject_reasons"):
            log.info(f"    REJECT: {result['reject_reasons']}")
        if result.get("bonus_reasons"):
            for b in result["bonus_reasons"]:
                log.info(f"    + {b}")
        if result.get("penalty_reasons"):
            for p in result["penalty_reasons"]:
                log.info(f"    - {p}")

    # 4. Summary
    decisions = {}
    for r in results:
        d = r["decision"]
        decisions[d] = decisions.get(d, 0) + 1

    total = len(results)
    scored = [r for r in results if r["decision"] not in ("reject", "skipped_unknown_model")]
    summary = {
        "total_cards": total,
        "scored": len(scored),
        "rejected": decisions.get("reject", 0),
        "skipped_unknown": decisions.get("skipped_unknown_model", 0),
        "by_decision": decisions,
        "distribution_pct": {
            d: round(c / total * 100, 1) for d, c in decisions.items()
        },
        "avg_score": round(sum(r["score"] for r in results if r["decision"] != "reject") / max(1, len(scored)), 1),
    }

    # 5. Distribution по моделям
    model_dist = {}
    for r in results:
        mid = r.get("model_id") or "unknown"
        if mid not in model_dist:
            model_dist[mid] = {"total": 0, "decisions": {}}
        model_dist[mid]["total"] += 1
        d = r["decision"]
        model_dist[mid]["decisions"][d] = model_dist[mid]["decisions"].get(d, 0) + 1

    # Добавляем % к каждой модели
    for mid, md in model_dist.items():
        t = md["total"]
        md["distribution_pct"] = {
            d: round(c / t * 100, 1) for d, c in md["decisions"].items()
        }

    output = {
        "generated_at": datetime.now().isoformat(),
        "config_version": config.get("version", "unknown"),
        "summary": summary,
        "model_distribution": model_dist,
        "results": results,
    }

    suffix = "500" if args.cards_file else (args.limit if args.limit else ("all" if args.all else "5"))
    out_path = RESULTS_DIR / f"config_scoring_test_{suffix}.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)

    log.info(f"\n💾 Сохранено: {out_path}")

    # Вывод summary
    log.info(f"\n{'='*60}")
    log.info("SUMMARY:")
    for k, v in summary.items():
        log.info(f"  {k}: {v}")

    # Вывод distribution по моделям
    log.info(f"\n{'='*60}")
    log.info("DISTRIBUTION BY MODEL:")
    log.info(f"{'Model':<30} {'Total':>6} {'excellent':>10} {'good':>8} {'watch':>8} {'weak':>8} {'reject':>8} {'skipped':>9}")
    log.info("-" * 100)
    for mid, md in sorted(model_dist.items()):
        dec = md["decisions"]
        log.info(f"{mid:<30} {md['total']:>6} {dec.get('excellent_candidate', 0):>10} {dec.get('good_candidate', 0):>8} {dec.get('watch', 0):>8} {dec.get('weak', 0):>8} {dec.get('reject', 0):>8} {dec.get('skipped_unknown_model', 0):>9}")

    log.info(f"{'='*60}")


if __name__ == "__main__":
    main()
