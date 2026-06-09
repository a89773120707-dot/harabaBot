"""
session_manager.py — надёжное сохранение и восстановление Haraba-сессии.

Функции:
  - is_session_valid(page) → bool
  - backup_state() → Path | None
  - check_session_status() → "VALID" | "EXPIRED" | "MISSING"
  - refresh_session_manual() → bool
  - get_authenticated_page() → (page, context, browser)
"""

import json
import time
import shutil
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

from base import STATE_PATH, BASE_DIR, log

SESSION_LOG_PATH = BASE_DIR / "logs" / "session.log"
BACKUP_PATH = BASE_DIR / "data" / "state_backup.json"

# Отдельный логгер для сессии
session_log = logging.getLogger("session")
session_log.setLevel(logging.INFO)

if not session_log.handlers:
    session_log.addHandler(
        logging.FileHandler(str(SESSION_LOG_PATH), encoding="utf-8")
    )
    session_log.addHandler(logging.StreamHandler())
    session_log.handlers[-1].setFormatter(
        logging.Formatter("%(asctime)s [SESSION] %(message)s")
    )


def is_session_valid(page: Page) -> bool:
    """
    Проверить что пользователь авторизован на Haraba.

    Признаки валидной сессии:
    - Нет кнопки "Войти"
    - Есть таблица tr.mat-row (результаты поиска) или навигация

    Returns: True если авторизован, False если нет.
    """
    try:
        page.goto("https://haraba.ru/search?mode=online", timeout=15000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)

        # Закрыть cookie-баннер если есть
        cookie_btn = page.get_by_role("button", name="Хорошо")
        if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
            cookie_btn.first.click()
            page.wait_for_timeout(500)

        # Признак 1: нет кнопки "Войти"
        login_btn = page.get_by_role("button", name="Войти")
        if login_btn.count() > 0 and login_btn.first.is_visible():
            session_log.warning("Обнаружена кнопка 'Войти' — сессия невалидна")
            return False

        # Признак 2: есть таблица с результатами
        rows = page.locator("tr.mat-row")
        if rows.count() > 0:
            session_log.info("Таблица с результатами найдена — сессия валидна")
            return True

        # Может быть что таблица есть но пустая — это тоже валидно (авторизован)
        # Проверяем наличие меню пользователя или навигации
        nav = page.locator("mat-toolbar, nav, .mat-toolbar")
        if nav.count() > 0:
            session_log.info("Навигация найдена — сессия валидна")
            return True

        session_log.warning("Не удалось определить статус авторизации")
        return False

    except Exception as e:
        session_log.error(f"Ошибка проверки сессии: {e}")
        return False


def backup_state() -> Path | None:
    """
    Создать резервную копию state.json → state_backup.json.

    Returns: путь к бэкапу или None если нечего бэкапить.
    """
    if not STATE_PATH.exists():
        return None

    try:
        shutil.copy2(str(STATE_PATH), str(BACKUP_PATH))
        session_log.info(f"Бэкап создан: {BACKUP_PATH}")
        return BACKUP_PATH
    except Exception as e:
        session_log.error(f"Ошибка создания бэкапа: {e}")
        return None


def check_session_status() -> str:
    """
    Проверить статус сессии без открытия браузера (быстрая проверка файла).

    Returns:
      "VALID"   — файл есть, JSON валидный, есть cookies/origins
      "EXPIRED" — файл битый или пустой
      "MISSING" — файла нет
    """
    if not STATE_PATH.exists():
        session_log.warning("state.json отсутствует")
        return "MISSING"

    try:
        with open(STATE_PATH, "r") as f:
            state = json.load(f)

        if not state.get("cookies") and not state.get("origins"):
            session_log.warning("state.json пустой (нет cookies/origins)")
            return "EXPIRED"

        session_log.info("state.json валиден (файл)")
        return "VALID"

    except json.JSONDecodeError:
        session_log.error("state.json битый (невалидный JSON)")
        return "EXPIRED"


def refresh_session_manual() -> bool:
    """
    Полуручной перелогин:
    1. Создать бэкап текущего state.json
    2. Открыть Haraba без сессии
    3. Пользователь логинится вручную
    4. Нажимает Enter
    5. Сохранить новый state.json

    Returns: True если сессия обновлена, False если пользователь отменил.
    """
    session_log.info("Начинаю обновление сессии (ручной режим)")

    # Бэкап
    backup_state()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()  # Без storage_state!
        page = context.new_page()

        session_log.info("Открыта Haraba — войди вручную и нажми Enter...")
        page.goto("https://haraba.ru")

        try:
            input("\n[SESSION] Войди в аккаунт, затем нажми Enter (или Ctrl+C для отмены): ")
        except (KeyboardInterrupt, EOFError):
            session_log.warning("Пользователь отменил перелогин")
            browser.close()
            return False

        try:
            context.storage_state(path=str(STATE_PATH))
            session_log.info(f"Сессия сохранена → {STATE_PATH}")

            # Проверить что сохранилось
            status = check_session_status()
            if status == "VALID":
                session_log.info("Новая сессия валидна ✓")
                browser.close()
                return True
            else:
                session_log.warning(f"Новая сессия подозрительна: {status}")
                browser.close()
                return False

        except Exception as e:
            session_log.error(f"Ошибка сохранения сессии: {e}")
            browser.close()
            return False


def get_authenticated_page(headless: bool = False):
    """
    Открыть браузер с сохранённой сессией и перейти на Haraba.

    Args:
        headless: Если True — браузер без GUI (по умолчанию False)

    Returns:
        tuple: (page, context, browser)

    Raises:
        FileNotFoundError: если state.json отсутствует
        ValueError: если сессия истекла

    Пример:
        page, context, browser = get_authenticated_page()
        try:
            page.goto("https://haraba.ru/search?mode=online")
            # ... работа со страницей
        finally:
            browser.close()
    """
    status = check_session_status()

    if status == "MISSING":
        raise FileNotFoundError(
            "state.json отсутствует!\n"
            "Запусти: python login.py  (первый вход)\n"
            "   или: python refresh_session.py  (обновление сессии)"
        )

    if status == "EXPIRED":
        raise ValueError(
            "Сессия истекла!\n"
            "Запусти: python refresh_session.py"
        )

    # status == "VALID"
    session_log.info("Сессия валидна — открываю браузер...")

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=str(STATE_PATH))
    page = context.new_page()

    session_log.info("Браузер открыт с авторизованной сессией ✓")
    return page, context, browser
