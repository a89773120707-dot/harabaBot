"""
test_open_haraba.py — открыть Haraba и сделать скриншот.
"""

from session_manager import get_authenticated_page
from base import log
import time

page, context, browser = get_authenticated_page()

try:
    log.info("Открываю https://haraba.ru/search...")
    page.goto("https://haraba.ru/search")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(5000)

    # Закрыть cookie-баннер
    cookie_btn = page.get_by_role("button", name="Хорошо")
    if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
        cookie_btn.first.click()
        page.wait_for_timeout(500)

    page.screenshot(path="data/test_open_haraba.png", full_page=True)
    log.info(f"📸 data/test_open_haraba.png")
    log.info(f"URL: {page.url}")
    log.info(f"Title: {page.title()}")

    # Показать что есть на странице
    log.info(f"body text (первые 500 символов):")
    body_text = page.inner_text("body")
    log.info(body_text[:500])

    time.sleep(3)

finally:
    browser.close()
