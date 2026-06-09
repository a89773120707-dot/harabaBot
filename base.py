"""
base.py — базовые константы и настройка логирования для haraba-mini.

Аналог apply_filter.py констант для session_manager.py и других модулей.
"""

import logging
from pathlib import Path

BASE_DIR = Path(__file__).parent
STATE_PATH = BASE_DIR / "data" / "state.json"
SCREENSHOT_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
RESULTS_DIR = BASE_DIR / "results"

for d in [LOGS_DIR, SCREENSHOT_DIR, RESULTS_DIR]:
    d.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "haraba.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)
