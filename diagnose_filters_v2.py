"""
diagnose_filters_v2.py — v2: кликнуть на фильтр, найти новые селекторы.
"""

from session_manager import get_authenticated_page
from base import log


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
        log.info("ДИАГНОСТИКА ФИЛЬТРОВ v2")
        log.info("=" * 60)

        # Ищем кнопку "Настройка ленты" или "Фильтры"
        filter_buttons = [
            "Настройка ленты",
            "Фильтры",
            "Filter",
            "Поиск",
        ]

        for btn_text in filter_buttons:
            btn = page.get_by_role("button", name=btn_text)
            if btn.count() > 0 and btn.first.is_visible():
                log.info(f"Найдена кнопка: '{btn_text}'")
                btn.first.click()
                page.wait_for_timeout(3000)
                log.info(f"Кликнул '{btn_text}' — жду загрузки...")
                break
        else:
            log.warning("Ни одна из кнопок фильтров не найдена")

        # Теперь ищем ВСЕ элементы на странице
        log.info("\n[1] Все mat-select после клика:")
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
                log.warning(f"  [{i}] Ошибка: {e}")

        log.info("\n[2] Все input после клика:")
        inputs = page.locator("input:not([type='hidden']):not([type='checkbox']):not([type='radio'])")
        count = inputs.count()
        log.info(f"  Найдено input: {count}")
        for i in range(count):
            inp = inputs.nth(i)
            try:
                inp_id = inp.get_attribute("id") or ""
                fcn = inp.get_attribute("formcontrolname") or ""
                placeholder = inp.get_attribute("placeholder") or ""
                inp_type = inp.get_attribute("type") or ""
                log.info(f"  [{i}] id='{inp_id}' formcontrolname='{fcn}' type='{inp_type}' placeholder='{placeholder}'")
            except Exception as e:
                log.warning(f"  [{i}] Ошибка: {e}")

        log.info("\n[3] Кнопки с текстом:")
        buttons = page.locator("button")
        count = buttons.count()
        for i in range(min(count, 50)):
            btn = buttons.nth(i)
            try:
                text = btn.inner_text().strip()
                if text:
                    log.info(f"  [{i}] '{text}'")
            except Exception as e:
                pass

        # Также dump весь HTML body для анализа
        log.info("\n[4] HTML фильтров (первые 10000 символов):")
        body = page.locator("body").inner_html()
        # Ищем секцию с фильтрами
        if "srch_fltr" in body:
            log.info("Найдено 'srch_fltr' в HTML!")
        if "formcontrolname" in body:
            # Извлечь все formcontrolname
            import re
            fcns = re.findall(r'formcontrolname="([^"]+)"', body)
            log.info(f"Все formcontrolname: {set(fcns)}")

        page.screenshot(path="data/diagnose_v2.png")
        log.info(f"\n📸 data/diagnose_v2.png")

        # Сохранить HTML для анализа
        with open("data/diagnose_v2.html", "w", encoding="utf-8") as f:
            f.write(body[:50000])
        log.info(f"📄 data/diagnose_v2.html")

        input("\nНажми Enter чтобы закрыть браузер...")

    finally:
        browser.close()


if __name__ == "__main__":
    main()
