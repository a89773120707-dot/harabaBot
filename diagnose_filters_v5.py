"""
diagnose_filters_v5.py — открыть фильтр через "Мои поиски" → снять все → применить.
"""

from session_manager import get_authenticated_page
from base import log
import re


def main():
    page, context, browser = get_authenticated_page()

    try:
        page.goto("https://haraba.ru/search?mode=online")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        # Закрыть cookie-баннер
        cookie_btn = page.get_by_role("button", name="Хорошо")
        if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
            cookie_btn.first.click()
            page.wait_for_timeout(500)

        log.info("=" * 60)
        log.info("ДИАГНОСТИКА ФИЛЬТРОВ v5 — через 'Мои поиски'")
        log.info("=" * 60)

        # 1. Нажать "Мои поиски"
        log.info("\n[1] Открываю 'Мои поиски'...")
        my_searches_btn = page.get_by_role("button", name="Мои поиски")
        if my_searches_btn.count() > 0:
            my_searches_btn.first.click()
            page.wait_for_timeout(2000)
            log.info("  ✅ Кликнул 'Мои поиски'")
        else:
            log.error("  ❌ Кнопка 'Мои поиски' не найдена!")
            input("\nНажми Enter чтобы закрыть браузер...")
            return

        # 2. Найти и снять "Выбрать все"
        log.info("\n[2] Ищу 'Выбрать все'...")
        select_all = page.get_by_role("option", name="Выбрать все")
        if select_all.count() == 0:
            # Попробуем mat-list-option
            select_all = page.locator("mat-list-option").filter(has_text="Выбрать все")
        
        if select_all.count() > 0:
            # Проверить есть ли aria-selected
            aria_sel = select_all.first.get_attribute("aria-selected")
            log.info(f"  'Выбрать все' aria-selected={aria_sel}")
            
            if aria_sel == "true":
                select_all.first.click()
                page.wait_for_timeout(1000)
                log.info("  ✅ Снял галочку 'Выбрать все'")
            else:
                log.info("  'Выбрать все' уже снят")
        else:
            log.warning("  ⚠ 'Выбрать все' не найден")
            # Показать все options
            options = page.locator("mat-list-option")
            cnt = options.count()
            log.info(f"  mat-list-option найдено: {cnt}")
            for i in range(cnt):
                opt = options.nth(i)
                text = opt.inner_text().strip()
                aria = opt.get_attribute("aria-selected")
                log.info(f"    [{i}] '{text}' aria-selected={aria}")

        # 3. Снова нажать "Мои поиски" для применения
        log.info("\n[3] Применяю (клик 'Мои поиски')...")
        my_searches_btn.first.click()
        page.wait_for_timeout(3000)
        log.info("  ✅ Кликнул 'Мои поиски' для применения")

        page.screenshot(path="data/diagnose_v5_after.png")
        log.info("📸 data/diagnose_v5_after.png")

        # 4. Теперь ищем элементы фильтров
        log.info("\n[4] mat-select элементы:")
        selects = page.locator("mat-select")
        count = selects.count()
        log.info(f"  Найдено mat-select: {count}")
        for i in range(count):
            sel = selects.nth(i)
            try:
                fcn = sel.get_attribute("formcontrolname") or ""
                sid = sel.get_attribute("id") or ""
                aria_label = sel.get_attribute("aria-label") or ""
                log.info(f"  [{i}] id='{sid}' formcontrolname='{fcn}' aria-label='{aria_label}'")
            except Exception as e:
                pass

        log.info("\n[5] input элементы:")
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

        log.info("\n[6] Кнопки с текстом:")
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

        # 7. Проверка известных селекторов
        log.info("\n[7] Проверка известных селекторов:")
        known = [
            "#srch_fltr_mark", "#srch_fltr_model",
            "#srch_fltr_year_from", "#srch_fltr_year_to",
            "#srch_fltr_price_from", "#srch_fltr_price_to",
            "#srch_fltr_mileage_to",
            "button:has-text('Применить')",
            "button:has-text('Очистить фильтр')",
        ]
        for sel in known:
            try:
                el = page.locator(sel)
                visible = el.is_visible()
                cnt = el.count()
                log.info(f"  {'✅' if visible else '❌'} {sel} (count={cnt})")
            except Exception as e:
                log.info(f"  ❌ {sel} — {e}")

        # 8. Все formcontrolname
        body = page.locator("body").inner_html()
        fcns = re.findall(r'formcontrolname="([^"]+)"', body)
        log.info(f"\n[8] Все formcontrolname: {sorted(set(fcns))}")

        # 9. srch_fltr?
        if "srch_fltr" in body:
            log.info("✅ Найдено 'srch_fltr' в HTML")
            fltr_ids = re.findall(r'id="(srch_fltr[^"]+)"', body)
            log.info(f"  srch_fltr IDs: {fltr_ids}")
        else:
            log.info("❌ 'srch_fltr' НЕ найден в HTML")

        with open("data/diagnose_v5.html", "w", encoding="utf-8") as f:
            f.write(body[:80000])
        log.info("📄 data/diagnose_v5.html")

        # Ждём 5 секунд чтобы посмотреть результат
        import time
        time.sleep(5)

    finally:
        browser.close()


if __name__ == "__main__":
    main()
