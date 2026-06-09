"""
card_data_loader.py — Загрузка полных данных карточек для feedback bot.

Используется telegram_feedback_bot.py и test_feedback_integrity.py
"""

import json
import logging
from pathlib import Path

from base import RESULTS_DIR

log = logging.getLogger(__name__)


def load_card_data():
    """Загрузить полные данные карточек из audited + sample."""
    audited_path = RESULTS_DIR / "telegram_candidates_audited.json"
    sample_path = RESULTS_DIR / "mobile_first_page_sample.json"

    if not audited_path.exists():
        log.error(f"Файл не найден: {audited_path}")
        return {}

    with open(audited_path, "r", encoding="utf-8") as f:
        audited = json.load(f)

    sample_lookup = {}
    if sample_path.exists():
        with open(sample_path, "r", encoding="utf-8") as f:
            sample = json.load(f)
        for c in sample.get("cards", []):
            cid = c.get("card_id", "")
            if cid:
                sample_lookup[cid] = c

    cards = {}
    for c in audited.get("cards", []):
        cid = c.get("card_id", "")
        s = sample_lookup.get(cid, {})
        specs = s.get("specs", {})

        cards[cid] = {
            "card_id": cid,
            "title": c.get("title", s.get("title", "")),
            "url": c.get("url", s.get("url", "")),
            "model_id": c.get("model_id", ""),
            "price": c.get("price", s.get("price", 0)),
            "mileage": c.get("mileage", s.get("mileage", 0)),
            "year": c.get("year", s.get("year", 0)),
            "score": c.get("score", 0),
            "decision": c.get("decision", ""),
            "engine": specs.get("engine", {}).get("value", "unknown"),
            "transmission": specs.get("transmission", {}).get("value", "unknown"),
            "drive": specs.get("drive", {}).get("value", "unknown"),
            "region": specs.get("region", {}).get("value", "unknown"),
            "owners": specs.get("owners", {}).get("value", "unknown"),
            "legal_restrictions": specs.get("legal_restrictions", {}).get("value", "unknown"),
            "autoteka_status": specs.get("autoteka_status", {}).get("value", "unknown"),
            "mobile_detail_raw_text": s.get("mobile_detail_raw_text", ""),
            "raw_text": s.get("raw_text", ""),
        }

    log.info(f"Загружено {len(cards)} карточек для feedback")
    return cards
