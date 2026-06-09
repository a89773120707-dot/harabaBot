"""
dedup_store.py — Обёртка для backward compatibility.
Вся логика перенесена в feedback_store.py
"""
from feedback_store import (
    check_dedup, mark_sent, update_last_seen,
    was_sent, save_feedback, get_feedback_stats,
    get_feedback_all, get_sent_stats, reset_sent_ads, init_db
)

__all__ = [
    "check_dedup", "mark_sent", "update_last_seen",
    "was_sent", "save_feedback", "get_feedback_stats",
    "get_feedback_all", "get_sent_stats", "reset_sent_ads", "init_db"
]
