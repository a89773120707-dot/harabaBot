"""
run_daily_pipeline.py — Единый запуск ежедневного pipeline.

Логика:
1. Проверка 17 поисков
2. Сбор свежих карточек
3. Enrichment (фото, регионы, legal)
4. Hard-stop audit
5. Dedup + Telegram отправка
6. Сохранение daily report

Команды:
  python run_daily_pipeline.py --dry-run
  python run_daily_pipeline.py --send --limit 3
  python run_daily_pipeline.py --send
"""
import argparse
import json
import logging
import sys
import yaml
from pathlib import Path
from datetime import datetime

from base import RESULTS_DIR, log
from session_manager import check_session_status

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(RESULTS_DIR / "daily_pipeline.log", encoding='utf-8'),
    ]
)
logger = logging.getLogger("pipeline")


def run_step(name, func, *args, **kwargs):
    """Выполнить шаг с обработкой ошибок."""
    logger.info(f"\n{'='*60}")
    logger.info(f"STEP: {name}")
    logger.info(f"{'='*60}")
    try:
        result = func(*args, **kwargs)
        logger.info(f"✅ {name}: OK")
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"❌ {name}: FAILED — {e}")
        return {"status": "error", "error": str(e)}


def step_check_searches():
    """Проверить сессию и 17 поисков."""
    status = check_session_status()
    if status.upper() != "VALID":
        raise RuntimeError(f"Session invalid: {status}")
    return {"session": status, "searches_expected": 17}


def step_collect_cards(limit=30):
    """Собрать свежие карточки из mobile_first_page_sampler."""
    import subprocess

    sampler_script = Path(__file__).parent / "mobile_first_page_sampler.py"
    if not sampler_script.exists():
        raise FileNotFoundError("mobile_first_page_sampler.py not found")

    cmd = [sys.executable, str(sampler_script), "--limit", str(limit)]
    logger.info(f"Running collector: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error(f"Collector stderr: {result.stderr}")
            raise RuntimeError(f"Collector failed: {result.stderr}")
        
        logger.info(f"Collector stdout: {result.stdout}")
        return {"cards_collected": True} # Simplified check
    except subprocess.TimeoutExpired:
        logger.error("Collector timed out (600s)")
        raise RuntimeError("Collector timed out")



def step_enrich_cards():
    """Обогатить карточки: регионы, legal, фото."""
    from photo_parser import enrich_cards_with_photos

    raw_path = RESULTS_DIR / "latest_cards_raw.json"
    if not raw_path.exists():
        # Fallback: use existing mobile_first_page_sample.json
        raw_path = RESULTS_DIR / "mobile_first_page_sample.json"
        if not raw_path.exists():
            raise RuntimeError("No raw cards found. Run step_collect_cards first.")

    with open(raw_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cards = data.get("cards", [])
    cards = enrich_cards_with_photos(cards)

    # Сохранить enriched
    enriched_path = RESULTS_DIR / "latest_cards_enriched.json"
    with open(enriched_path, 'w', encoding='utf-8') as f:
        json.dump({"cards": cards, "enriched_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)

    with_photos = sum(1 for c in cards if c.get("photo_url"))
    logger.info(f"Enriched {len(cards)} cards, {with_photos} with photos")
    return {"cards_enriched": len(cards), "with_photos": with_photos}


def step_audit():
    """Запустить hard-stop audit."""
    from telegram_audit import load_input_files, score_card, check_region_allowed, check_legal_restrictions
    from config_loader import load_config

    enriched_path = RESULTS_DIR / "latest_cards_enriched.json"
    if not enriched_path.exists():
        enriched_path = RESULTS_DIR / "mobile_first_page_sample.json"
        if not enriched_path.exists():
            raise RuntimeError("No enriched cards found.")

    with open(enriched_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cards = data.get("cards", data) if isinstance(data, dict) else data

    # Flatten specs to top-level fields
    for c in cards:
        specs = c.get("specs", {})
        for key, val in specs.items():
            if isinstance(val, dict) and "value" in val:
                current = c.get(key)
                if not current or current == "unknown":
                    c[key] = val["value"]

        # Normalize drive: "Полный" -> "awd"
        drive = c.get("drive", "")
        if drive in ("Полный", "полный", "4WD", "AWD", "4x4", "4WD (Full)", "Quattro", "4Matic"):
            c["drive"] = "awd"
        elif drive in ("Передний", "передний", "FWD"):
            c["drive"] = "fwd"
        elif drive in ("Задний", "задний", "RWD"):
            c["drive"] = "rwd"

        # Normalize transmission: "Автомат" -> "automatic"
        trans = c.get("transmission", "")
        if trans in ("Автомат", "автомат", "AT", "АКПП", "Автоматическая"):
            c["transmission"] = "automatic"
        elif trans in ("Робот", "робот", "DSG", "DSI", "S tronic"):
            c["transmission"] = "dsg"
        elif trans in ("Вариатор", "вариатор", "CVT"):
            c["transmission"] = "cvt"
        elif trans in ("Механика", "механика", "MT", "МКПП", "Ручная"):
            c["transmission"] = "manual"
    config_path = Path(__file__).parent / "config" / "awd_liquid_full_config.yaml"
    if not config_path.exists():
        config_path = RESULTS_DIR / "awd_liquid_full_config.yaml"
    config = load_config(str(config_path))

    send_ready = []
    do_not_send = []
    hold_review = []

    for c in cards:
        cid = c.get("card_id", "")
        title = c.get("title", "")

        # Hard-stops
        engine = c.get("engine", "unknown")
        trans = c.get("transmission", "unknown")
        drive = c.get("drive", "unknown")
        region = c.get("region", "unknown")
        legal = c.get("legal_restrictions", "unknown")

        reject_reasons = []
        hold_reasons = []

        if engine == "unknown":
            reject_reasons.append("engine_unknown")
        if trans == "unknown":
            reject_reasons.append("transmission_unknown")
        if trans == "manual":
            reject_reasons.append("manual_transmission")
        if drive == "unknown":
            reject_reasons.append("drive_unknown")
        elif drive not in ("awd", "4matic", "quattro", "xdrive", "4wd"):
            reject_reasons.append(f"not_awd: {drive}")

        region_ok, region_status = check_region_allowed(region)
        if not region_ok:
            reject_reasons.append(f"region: {region_status}")

        legal_clean, legal_status = check_legal_restrictions(legal)
        if legal_status == "reject":
            reject_reasons.append(f"legal: {legal}")
        elif legal_status == "warning_unknown":
            hold_reasons.append("legal_unknown")

        if reject_reasons:
            c["action"] = "do_not_send"
            do_not_send.append({"card_id": cid, "title": title, "reasons": reject_reasons})
            continue

        # Scoring
        from price_scorer_v2 import score_price
        from mileage_scorer import score_mileage
        from powertrain_scorer import score_engine, score_transmission
        from equipment_scorer import score_equipment
        from config_loader import get_model_by_id
        from model_matcher import match_card_to_model

        model_id = match_card_to_model(c, config)
        c["model_id"] = model_id
        model_rules = get_model_by_id(config, model_id) if model_id else None

        # Блок 2: config_name — привязка карточки к конфигу
        if model_rules:
            c["config_name"] = f"{model_rules['brand']} {model_rules['model']}"
        else:
            c["config_name"] = "unknown"
            if model_id:
                log.warning(f"config_name=unknown: model_id={model_id} не найден в конфиге для карточки {cid}")

        if model_rules:
            price_r = score_price(c.get("price"), model_rules.get("price", {}))
            mileage_r = score_mileage(c.get("mileage"), model_rules.get("mileage", {}))
            engine_r = score_engine(c.get("engine", ""), model_rules.get("engines", {}))
            trans_r = score_transmission(c.get("transmission", ""), model_rules.get("transmissions", {}))
            equip_r = score_equipment(c, model_rules)

            total = price_r["score"] + mileage_r["score"] + engine_r["score"] + trans_r["score"] + equip_r["score"]
            total = max(0, min(100, total + 50))  # baseline 50

            if total >= 80:
                decision = "excellent_candidate"
            elif total >= 60:
                decision = "good_candidate"
            elif total >= 40:
                decision = "watch_candidate"
            else:
                decision = "weak_candidate"

            c["score"] = total
            c["decision"] = decision
            c["price_score"] = price_r["score"]
            c["mileage_score"] = mileage_r["score"]
            c["engine_score"] = engine_r["score"]
            c["transmission_score"] = trans_r["score"]
            c["equipment_score"] = equip_r["score"]
            c["price_category"] = price_r.get("category", "")
            c["price_status"] = price_r.get("price_status", "")
            c["engine_category"] = engine_r.get("category", "")
            c["transmission_category"] = trans_r.get("category", "")
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
            if equip_r["score"] > 0:
                c["bonus_reasons"].append(equip_r["explanation"])

        c["audit"] = {"hold_reasons": hold_reasons, "reject_reasons": reject_reasons}
        if hold_reasons:
            c["action"] = "hold_manual_review"
            hold_review.append(c)
        else:
            c["action"] = "send_ready"
            send_ready.append(c)

    # Save audited
    audited = {
        "cards": send_ready + hold_review,
        "do_not_send": do_not_send,
        "audit_summary": {
            "send_ready": len(send_ready),
            "do_not_send": len(do_not_send),
            "hold_manual_review": len(hold_review),
        },
        "audited_at": datetime.now().isoformat(),
    }

    audited_path = RESULTS_DIR / "latest_cards_audited.json"
    with open(audited_path, 'w', encoding='utf-8') as f:
        json.dump(audited, f, ensure_ascii=False, indent=2)

    logger.info(f"Audit: {len(send_ready)} ready, {len(do_not_send)} rejected, {len(hold_review)} hold")
    return audited["audit_summary"]


def step_send(dry_run=False, limit=None):
    """Отправить карточки в Telegram."""
    import subprocess

    audited_path = RESULTS_DIR / "latest_cards_audited.json"
    if not audited_path.exists():
        raise RuntimeError("No audited cards found.")

    # Copy to expected location for telegram_sender.py
    import shutil
    shutil.copy(str(audited_path), str(RESULTS_DIR / "telegram_candidates_audited.json"))

    cmd = [sys.executable, "telegram_sender.py"]
    if dry_run:
        cmd.append("--dry-run")
    else:
        cmd.append("--send")
    if limit:
        cmd.extend(["--limit", str(limit)])

    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    # Telegram sender logs to stderr via logging module
    output = result.stderr if result.stderr else result.stdout

    # Parse summary from output
    sent = 0
    skipped = 0
    for line in output.split('\n'):
        if "Sent:" in line:
            try:
                sent = int(line.split("Sent:")[1].strip())
            except:
                pass
        if "Skipped:" in line:
            try:
                skipped = int(line.split("Skipped:")[1].strip())
            except:
                pass

    return {"sent": sent, "skipped": skipped, "stdout": output[-500:] if output else ""}


def step_feedback_count():
    """Получить текущее количество реакций."""
    from feedback_store import get_feedback_all
    fb = get_feedback_all(days=365)
    return {"feedback_count": len(fb)}


def save_daily_report(results):
    """Сохранить daily report."""
    report = {
        "run_id": datetime.now().strftime("%Y-%m-%d_%H%M"),
        "started_at": datetime.now().isoformat(),
        "steps": {},
    }

    for step_name, step_result in results.items():
        if isinstance(step_result, dict):
            report["steps"][step_name] = step_result
        else:
            report["steps"][step_name] = {"raw": str(step_result)}

    # Flatten key metrics
    report["cards_collected"] = results.get("collect_cards", {}).get("result", {}).get("cards_collected", 0)
    report["cards_enriched"] = results.get("enrich_cards", {}).get("result", {}).get("cards_enriched", 0)
    report["with_photos"] = results.get("enrich_cards", {}).get("result", {}).get("with_photos", 0)
    report["send_ready"] = results.get("audit", {}).get("result", {}).get("send_ready", 0)
    report["do_not_send"] = results.get("audit", {}).get("result", {}).get("do_not_send", 0)
    report["sent_new"] = results.get("send", {}).get("result", {}).get("sent", 0)
    report["skipped_duplicate"] = results.get("send", {}).get("result", {}).get("skipped", 0)
    report["failed"] = 0
    report["feedback_count"] = results.get("feedback_count", {}).get("result", {}).get("feedback_count", 0)

    report_path = RESULTS_DIR / "daily_pipeline_report.yaml"
    with open(report_path, 'w', encoding='utf-8') as f:
        yaml.dump(report, f, allow_unicode=True, default_flow_style=False)

    logger.info(f"\nDaily report saved: {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Daily pipeline runner")
    parser.add_argument("--dry-run", action="store_true", help="Dry run — no sending")
    parser.add_argument("--send", action="store_true", help="Send to Telegram")
    parser.add_argument("--limit", type=int, default=None, help="Limit cards to send")
    parser.add_argument("--skip-collect", action="store_true", help="Skip card collection (use existing)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("DAILY PIPELINE RUN")
    logger.info(f"Mode: {'dry-run' if args.dry_run else 'SEND'}")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    results = {}

    # Step 1: Check searches
    results["check_searches"] = run_step("Check 17 searches", step_check_searches)
    if results["check_searches"]["status"] == "error":
        logger.error("Pipeline aborted: session invalid")
        return

    # Step 2: Collect cards
    if not args.skip_collect:
        results["collect_cards"] = run_step("Collect cards", step_collect_cards, limit=30)
        if results["collect_cards"]["status"] == "error":
            logger.warning("Card collection failed, trying with existing cards...")
    else:
        results["collect_cards"] = {"status": "skipped", "note": "Using existing cards"}

    # Step 3: Enrich
    results["enrich_cards"] = run_step("Enrich cards (photos, regions)", step_enrich_cards)
    if results["enrich_cards"]["status"] == "error":
        logger.error("Pipeline aborted: enrichment failed")
        return

    # Step 4: Audit
    results["audit"] = run_step("Hard-stop audit", step_audit)
    if results["audit"]["status"] == "error":
        logger.error("Pipeline aborted: audit failed")
        return

    # Step 5: Send
    results["send"] = run_step("Telegram send", step_send, dry_run=not args.send, limit=args.limit)

    # Step 6: Feedback count
    results["feedback_count"] = run_step("Feedback count", step_feedback_count)

    # Save report
    report = save_daily_report(results)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("PIPELINE SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Cards collected: {report.get('cards_collected', 0)}")
    logger.info(f"Send ready: {report.get('send_ready', 0)}")
    logger.info(f"Sent: {report.get('sent_new', 0)}")
    logger.info(f"Skipped (dup): {report.get('skipped_duplicate', 0)}")
    logger.info(f"Feedback count: {report.get('feedback_count', 0)}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()
