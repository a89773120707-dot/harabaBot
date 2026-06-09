"""
diagnose_ford_models.py — выбрать Ford и показать доступные модели.
"""

from session_manager import get_authenticated_page
from base import log
import time


def ensure_filters_visible(page):
    """Снять все сохранённые поиски чтобы фильтр появился."""
    btn = page.get_by_role("button", name="Мои поиски")
    if btn.count() == 0:
        return False
    btn.first.click()
    page.wait_for_timeout(2000)

    # Снять все поиски
    options = page.locator("mat-list-option")
    for i in range(options.count()):
        opt = options.nth(i)
        aria = opt.get_attribute("aria-selected")
        text = opt.inner_text().strip()
        if aria == "true":
            opt.click()
            page.wait_for_timeout(300)

    page.keyboard.press("Escape")
    page.wait_for_timeout(3000)

    brand_sel = page.locator("#srch_fltr_mark")
    try:
        brand_sel.wait_for(state="visible", timeout=5000)
        return True
    except:
        return False


def main():
    page, context, browser = get_authenticated_page()

    try:
        page.goto("https://haraba.ru/search")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(4000)

        cookie_btn = page.get_by_role("button", name="Хорошо")
        if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
            cookie_btn.first.click()
            page.wait_for_timeout(500)

        if not ensure_filters_visible(page):
            log.error("Фильтр не появился!")
            return

        # 1. Выбрать Ford
        log.info("Выбираю марку Ford...")
        from apply_filters_8 import _select_mat_option, _close_dropdown
        _select_mat_option(page, "#srch_fltr_mark", "Ford")
        page.wait_for_timeout(2000)

        # 2. Показать все mat-option для моделей
        log.info("\nОткрываю dropdown моделей...")
        model_sel = page.locator("#srch_fltr_model")
        model_sel.click()
        page.wait_for_timeout(3000)

        options = page.locator("mat-option")
        count = options.count()
        log.info(f"\nДоступно моделей для Ford: {count}")
        for i in range(count):
            opt = options.nth(i)
            try:
                text = opt.inner_text().strip()
                log.info(f"  [{i}] '{text}'")
            except:
                pass

        # 3. Также показать все mat-option с классами
        log.info("\nПодробно:")
        for i in range(count):
            opt = options.nth(i)
            try:
                text = opt.inner_text().strip()
                cls = opt.get_attribute("class") or ""
                disabled = opt.get_attribute("aria-disabled")
                log.info(f"  [{i}] text='{text}' class='{cls[:50]}' disabled={disabled}")
            except:
                pass

        page.screenshot(path="data/ford_models.png")
        log.info(f"\n📸 data/ford_models.png")

        _close_dropdown(page)
        time.sleep(3)

    finally:
        browser.close()


if __name__ == "__main__":
    main()
