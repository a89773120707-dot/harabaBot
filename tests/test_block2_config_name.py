"""
tests/test_block2_config_name.py — проверка Блока 2: config_name flow.
"""
import sys
import json
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from base import RESULTS_DIR, log
from feedback_store import init_db, get_conn, mark_sent_with_chat_id, check_dedup_with_chat_id
from config_loader import load_config, get_model_by_id
from model_matcher import match_card_to_model

CONFIG_PATH = RESULTS_DIR / "awd_liquid_full_config.yaml"

def test_migration():
    """Проверить что config_name колонка существует."""
    init_db()
    conn = get_conn()
    c = conn.cursor()
    c.execute("PRAGMA table_info(sent_ads)")
    cols = {row[1] for row in c.fetchall()}
    conn.close()
    
    assert "config_name" in cols, f"config_name column missing! Columns: {cols}"
    log.info("✅ Migration: config_name column exists")

def test_config_name_from_audit():
    """Проверить что step_audit логика даёт config_name."""
    config = load_config(str(CONFIG_PATH))
    
    # Тестовая карточка
    test_cards = [
        {"title": "Volkswagen Tiguan 2013", "brand": "Volkswagen", "model": "Tiguan", "year": 2013, "price": 1200000, "mileage": 140000, "drive": "awd", "transmission": "automatic", "engine": "2.0 TSI"},
        {"title": "Kia Sportage IV", "brand": "Kia", "model": "Sportage", "year": 2018, "price": 1500000, "mileage": 95000, "drive": "awd", "transmission": "automatic", "engine": "2.0 CRDi"},
        {"title": "Mazda CX-5 II", "brand": "Mazda", "model": "CX-5", "year": 2019, "price": 1800000, "mileage": 80000, "drive": "awd", "transmission": "automatic", "engine": "2.5 SKYACTIV"},
    ]
    
    for card in test_cards:
        model_id = match_card_to_model(card, config)
        assert model_id is not None, f"model_id not found for {card['title']}"
        
        model_rules = get_model_by_id(config, model_id)
        if model_rules:
            config_name = f"{model_rules['brand']} {model_rules['model']}"
            log.info(f"  ✅ {card['title']} → model_id={model_id} → config_name='{config_name}'")
        else:
            log.warning(f"  ⚠️ {card['title']} → model_id={model_id} → NO model_rules")

def test_mark_sent_with_config_name():
    """Проверить что mark_sent_with_chat_id сохраняет config_name."""
    # Удаляем тестовую запись если есть
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM sent_ads WHERE card_id = 'test_block2_001'")
    conn.commit()
    conn.close()
    
    test_card = {
        "card_id": "test_block2_001",
        "title": "Volkswagen Tiguan 2013",
        "url": "https://haraba.ru/common/click?id=999999",
        "mobile_url": "https://m.haraba.ru/search/car/999999",
        "year": 2013,
        "price": 1200000,
        "mileage": 140000,
        "region": "Москва",
        "model_id": "volkswagen_tiguan",
        "config_name": "Volkswagen Tiguan",
    }
    
    mark_sent_with_chat_id(test_card, "test_chat_001", status="new")
    
    # Проверить что config_name записан
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT config_name, model_id, title FROM sent_ads WHERE card_id = 'test_block2_001'")
    row = c.fetchone()
    conn.close()
    
    assert row is not None, "Test card not found in sent_ads"
    assert row["config_name"] == "Volkswagen Tiguan", f"Expected 'Volkswagen Tiguan', got '{row['config_name']}'"
    log.info(f"✅ mark_sent: config_name='{row['config_name']}', model_id='{row['model_id']}'")
    
    # Очистить тестовую запись
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM sent_ads WHERE card_id = 'test_block2_001'")
    conn.commit()
    conn.close()

def test_join_feedback_sent_ads():
    """Проверить что JOIN feedback → sent_ads вернёт config_name."""
    # Тестовая запись в sent_ads
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM sent_ads WHERE card_id = 'test_join_001'")
    c.execute("DELETE FROM feedback WHERE card_id = 'test_join_001'")
    conn.commit()
    
    # INSERT sent_ads с config_name
    from datetime import datetime
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO sent_ads (stable_car_key, card_id, chat_id, title, model_id, config_name, year, price, mileage, region, first_sent_at, last_seen_at, last_sent_at, send_count)
        VALUES ('test:join_001', 'test_join_001', '123456', 'Test Car', 'volkswagen_tiguan', 'Volkswagen Tiguan', 2013, 1200000, 140000, 'Москва', ?, ?, ?, 1)
    """, (now, now, now))
    
    # INSERT feedback
    c.execute("""
        INSERT INTO feedback (card_id, title, action, telegram_user_id, telegram_chat_id, created_at)
        VALUES ('test_join_001', 'Test Car', 'review', '123456', '123456', ?)
    """, (now,))
    conn.commit()
    conn.close()
    
    # JOIN query
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT f.id, f.card_id, f.action, s.config_name, s.title
        FROM feedback f
        JOIN sent_ads s 
            ON s.card_id = f.card_id 
           AND s.chat_id = f.telegram_user_id
        WHERE f.card_id = 'test_join_001'
    """)
    row = c.fetchone()
    conn.close()
    
    assert row is not None, "JOIN returned no results"
    assert row["config_name"] == "Volkswagen Tiguan", f"Expected config_name='Volkswagen Tiguan', got '{row['config_name']}'"
    log.info(f"✅ JOIN: config_name='{row['config_name']}', action='{row['action']}'")
    
    # Очистить
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM sent_ads WHERE card_id = 'test_join_001'")
    c.execute("DELETE FROM feedback WHERE card_id = 'test_join_001'")
    conn.commit()
    conn.close()

def test_config_name_unknown():
    """Проверить что config_name='unknown' если model_id не найден."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM sent_ads WHERE card_id = 'test_unknown_001'")
    conn.commit()
    conn.close()
    
    test_card = {
        "card_id": "test_unknown_001",
        "title": "Unknown Model 2020",
        "url": "https://haraba.ru/common/click?id=888888",
        "mobile_url": "https://m.haraba.ru/search/car/888888",
        "year": 2020,
        "price": 1000000,
        "mileage": 50000,
        "region": "Москва",
        "model_id": None,
        "config_name": "unknown",
    }
    
    mark_sent_with_chat_id(test_card, "test_chat_002", status="new")
    
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT config_name FROM sent_ads WHERE card_id = 'test_unknown_001'")
    row = c.fetchone()
    conn.close()
    
    assert row["config_name"] == "unknown", f"Expected 'unknown', got '{row['config_name']}'"
    log.info(f"✅ config_name=unknown works correctly")
    
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM sent_ads WHERE card_id = 'test_unknown_001'")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("BLOCK 2: config_name tests")
    log.info("=" * 60)
    
    test_migration()
    log.info("")
    
    test_config_name_from_audit()
    log.info("")
    
    test_mark_sent_with_config_name()
    log.info("")
    
    test_join_feedback_sent_ads()
    log.info("")
    
    test_config_name_unknown()
    log.info("")
    
    log.info("=" * 60)
    log.info("ALL BLOCK 2 TESTS PASSED ✅")
    log.info("=" * 60)
