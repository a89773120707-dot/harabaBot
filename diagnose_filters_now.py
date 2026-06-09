"""
diagnose_filters_now.py — диагностика актуальных селекторов фильтров Haraba.

Запуск:
    python diagnose_filters_now.py

Открывает Haraba и выводит все элементы фильтров (mat-select, input, button).
"""

import sys
from session_manager import get_authenticated_page
from base import log


def main():
    log.info("Открываю Haraba для диагностики фильтров...")
    page, context, browser = get_authenticated_page()

    try:
        page.goto("https://haraba.ru/search?mode=online")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        # Закрыть cookie-баннер если есть
        cookie_btn = page.get_by_role("button", name="Хорошо")
        if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
            cookie_btn.first.click()
            page.wait_for_timeout(500)

        log.info("=" * 60)
        log.info("ДИАГНОСТИКА ФИЛЬТРОВ")
        log.info("=" * 60)

        # 1. Все mat-select
        log.info("\n[1] mat-select элементы:")
        selects = page.locator("mat-select")
        count = selects.count()
        log.info(f"  Найдено mat-select: {count}")
        for i in range(count):
            sel = selects.nth(i)
            try:
                formcontrolname = sel.get_attribute("formcontrolname") or ""
                id_attr = sel.get_attribute("id") or ""
                aria_label = sel.get_attribute("aria-label") or ""
                placeholder = sel.get_attribute("placeholder") or ""
                log.info(f"  [{i}] id='{id_attr}' formcontrolname='{formcontrolname}' aria-label='{aria_label}' placeholder='{placeholder}'")
            except Exception as e:
                log.warning(f"  [{i}] Ошибка: {e}")

        # 2. Все input
        log.info("\n[2] input элементы (type=text/number):")
        inputs = page.locator("input:not([type='hidden']):not([type='checkbox']):not([type='radio'])")
        count = inputs.count()
        log.info(f"  Найдено input: {count}")
        for i in range(count):
            inp = inputs.nth(i)
            try:
                inp_id = inp.get_attribute("id") or ""
                formcontrolname = inp.get_attribute("formcontrolname") or ""
                placeholder = inp.get_attribute("placeholder") or ""
                inp_type = inp.get_attribute("type") or ""
                log.info(f"  [{i}] id='{inp_id}' formcontrolname='{formcontrolname}' type='{inp_type}' placeholder='{placeholder}'")
            except Exception as e:
                log.warning(f"  [{i}] Ошибка: {e}")

        # 3. Все кнопки
        log.info("\n[3] Кнопки:")
        buttons = page.locator("button")
        count = buttons.count()
        log.info(f"  Найдено button: {count}")
        for i in range(min(count, 30)):
            btn = buttons.nth(i)
            try:
                text = btn.inner_text().strip()
                btn_id = btn.get_attribute("id") or ""
                log.info(f"  [{i}] id='{btn_id}' text='{text}'")
            except Exception as e:
                log.warning(f"  [{i}] Ошибка: {e}")

        # 4. Проверка старых селекторов
        log.info("\n[4] Проверка известных селекторов:")
        known_selectors = [
            "#srch_fltr_mark",
            "#srch_fltr_model",
            "#srch_fltr_year_from",
            "#srch_fltr_year_to",
            "#srch_fltr_price_from",
            "#srch_fltr_price_to",
            "#srch_fltr_mileage_to",
            "button:has-text('Применить')",
            "button:has-text('Очистить фильтр')",
        ]
        for sel in known_selectors:
            try:
                el = page.locator(sel)
                visible = el.is_visible()
                count = el.count()
                log.info(f"  {'✅' if visible else '❌'} {sel} (count={count}, visible={visible})")
            except Exception as e:
                log.info(f"  ❌ {sel} — ОШИБКА: {e}")

        # Скриншот
        page.screenshot(path="data/diagnose_filters.png")
        log.info(f"\n📸 data/diagnose_filters.png")

        log.info("\n" + "=" * 60)
        input("Нажми Enter чтобы закрыть браузер...")

    finally:
        browser.close()


if __name__ == "__main__":
    main()
