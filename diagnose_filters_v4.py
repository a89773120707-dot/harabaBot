"""
diagnose_filters_v4.py — найти как открыть панель фильтров.
Пробуем: /search?mode=manual, поиск кнопки filter/tune.
"""

from session_manager import get_authenticated_page
from base import log
import re


def main():
    page, context, browser = get_authenticated_page()

    try:
        # Пробуем mode=manual
        page.goto("https://haraba.ru/search?mode=manual")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(4000)

        # Закрыть cookie-баннер
        cookie_btn = page.get_by_role("button", name="Хорошо")
        if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
            cookie_btn.first.click()
            page.wait_for_timeout(500)

        log.info("=" * 60)
        log.info("ДИАГНОСТИКА ФИЛЬТРОВ v4 — /search?mode=manual")
        log.info("=" * 60)

        # 1. Все mat-select
        log.info("\n[1] mat-select элементы:")
        selects = page.locator("mat-select")
        count = selects.count()
        log.info(f"  Найдено mat-select: {count}")
        for i in range(count):
            sel = selects.nth(i)
            try:
                fcn = sel.get_attribute("formcontrolname") or ""
                sid = sel.get_attribute("id") or ""
                log.info(f"  [{i}] id='{sid}' formcontrolname='{fcn}'")
            except Exception as e:
                pass

        # 2. Все input
        log.info("\n[2] input элементы:")
        inputs = page.locator("input:not([type='hidden']):not([type='checkbox']):not([type='radio'])")
        count = inputs.count()
        log.info(f"  Найдено input: {count}")
        for i in range(count):
            inp = inputs.nth(i)
            try:
                inp_id = inp.get_attribute("id") or ""
                fcn = inp.get_attribute("formcontrolname") or ""
                placeholder = inp.get_attribute("placeholder") or ""
                log.info(f"  [{i}] id='{inp_id}' formcontrolname='{fcn}' placeholder='{placeholder}'")
            except Exception as e:
                pass

        # 3. Кнопки с текстом
        log.info("\n[3] Кнопки с текстом:")
        buttons = page.locator("button")
        count = buttons.count()
        for i in range(min(count, 50)):
            btn = buttons.nth(i)
            try:
                text = btn.inner_text().strip()
                if text and len(text) < 50:
                    log.info(f"  [{i}] '{text}'")
            except Exception:
                pass

        # 4. Проверка известных селекторов
        log.info("\n[4] Проверка известных селекторов:")
        known = [
            "#srch_fltr_mark", "#srch_fltr_model",
            "#srch_fltr_year_from", "#srch_fltr_year_to",
            "#srch_fltr_price_from", "#srch_fltr_price_to",
            "#srch_fltr_mileage_to",
            "button:has-text('Применить')",
            "button:has-text('Очистить фильтр')",
            "button:has-text('Найти')",
            "button:has-text('Поиск')",
        ]
        for sel in known:
            try:
                el = page.locator(sel)
                visible = el.is_visible()
                cnt = el.count()
                log.info(f"  {'✅' if visible else '❌'} {sel} (count={cnt})")
            except Exception as e:
                log.info(f"  ❌ {sel} — {e}")

        # 5. Все formcontrolname
        body = page.locator("body").inner_html()
        fcns = re.findall(r'formcontrolname="([^"]+)"', body)
        log.info(f"\n[5] Все formcontrolname: {sorted(set(fcns))}")

        # 6. srch_fltr?
        if "srch_fltr" in body:
            log.info("✅ Найдено 'srch_fltr' в HTML")
            fltr_ids = re.findall(r'id="(srch_fltr[^"]+)"', body)
            log.info(f"  srch_fltr IDs: {fltr_ids}")
        else:
            log.info("❌ 'srch_fltr' НЕ найден в HTML")

        page.screenshot(path="data/diagnose_v4.png")
        log.info(f"\n📸 data/diagnose_v4.png")

        with open("data/diagnose_v4.html", "w", encoding="utf-8") as f:
            f.write(body[:80000])
        log.info("📄 data/diagnose_v4.html")

        input("\nНажми Enter чтобы закрыть браузер...")

    finally:
        browser.close()


if __name__ == "__main__":
    main()
