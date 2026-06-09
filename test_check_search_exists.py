"""
test_check_search_exists.py — тест функции check_search_exists.

Проверяет каждый из 8 поисков через check_search_exists.
"""

from session_manager import get_authenticated_page
from config_loader_8 import load_searches
from search_expander_8 import expand_search
from saved_search_helper_8 import check_search_exists
from base import log
import time


def main():
    searches = load_searches()

    page, context, browser = get_authenticated_page()

    try:
        page.goto("https://haraba.ru/search")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(5000)

        # Закрыть cookie-баннер
        cookie_btn = page.get_by_role("button", name="Хорошо")
        if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
            cookie_btn.first.click()
            page.wait_for_timeout(500)

        log.info("=" * 60)
        log.info("ТЕСТ: check_search_exists для 8 моделей")
        log.info("=" * 60)

        for s in searches:
            expanded = expand_search(s)
            log.info(f"\n[{s.id}] Проверяю: '{expanded.save_name}'...")

            exists = check_search_exists(page, expanded.save_name)
            log.info(f"  Результат: {'✅ существует' if exists else '❌ не найден'}")

            # Скриншот после каждой проверки
            page.screenshot(path=f"data/test_exists_{s.id}.png")

        log.info("\n" + "=" * 60)
        log.info("ТЕСТ ЗАВЕРШЁН")
        log.info("=" * 60)

        time.sleep(3)

    finally:
        browser.close()


if __name__ == "__main__":
    main()
