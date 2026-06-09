"""
analyze_haraba_ui.py — полный анализатор UI Haraba.

Открывает "Мои поиски", перебирает все варианты, показывает все кнопки и элементы.
"""

from session_manager import get_authenticated_page
from base import log
import re
import time


def dump_page_info(page, label=""):
    """Полный дамп информации о странице."""
    if label:
        log.info(f"\n{'='*60}")
        log.info(label)
        log.info(f"{'='*60}")

    log.info(f"URL: {page.url}")
    log.info(f"Title: {page.title()}")

    # mat-select
    selects = page.locator("mat-select")
    log.info(f"\nmat-select: {selects.count()}")
    for i in range(selects.count()):
        sel = selects.nth(i)
        try:
            log.info(f"  [{i}] id='{sel.get_attribute('id') or ''}' fcn='{sel.get_attribute('formcontrolname') or ''}'")
        except:
            pass

    # input
    inputs = page.locator("input:not([type='hidden']):not([type='checkbox']):not([type='radio'])")
    log.info(f"\ninput: {inputs.count()}")
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            log.info(f"  [{i}] id='{inp.get_attribute('id') or ''}' fcn='{inp.get_attribute('formcontrolname') or ''}' placeholder='{inp.get_attribute('placeholder') or ''}'")
        except:
            pass

    # Кнопки
    buttons = page.locator("button")
    log.info(f"\nbuttons: {buttons.count()}")
    for i in range(min(buttons.count(), 40)):
        btn = buttons.nth(i)
        try:
            text = btn.inner_text().strip()
            btn_id = btn.get_attribute("id") or ""
            if text and len(text) < 60:
                log.info(f"  [{i}] id='{btn_id}' text='{text}'")
        except:
            pass

    # formcontrolname
    body = page.inner_html()
    fcns = re.findall(r'formcontrolname="([^"]+)"', body)
    log.info(f"\nformcontrolname: {sorted(set(fcns))}")

    # srch_fltr
    if "srch_fltr" in body:
        fltr_ids = re.findall(r'id="(srch_fltr[^"]+)"', body)
        log.info(f"srch_fltr IDs: {fltr_ids}")
    else:
        log.info("srch_fltr: НЕ НАЙДЕН")


def main():
    page, context, browser = get_authenticated_page()

    try:
        # 1. Открываем /search
        log.info("Открываю /search...")
        page.goto("https://haraba.ru/search")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(4000)

        # Закрыть cookie-баннер
        cookie_btn = page.get_by_role("button", name="Хорошо")
        if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
            cookie_btn.first.click()
            page.wait_for_timeout(500)

        dump_page_info(page, "ШАГ 1: /search (пустая страница)")

        # 2. Нажать "Мои поиски" — открыть dropdown
        log.info("\n\n>>> НАЖИМАЮ 'Мои поиски' (открыть dropdown)...")
        btn = page.get_by_role("button", name="Мои поиски")
        if btn.count() > 0:
            btn.first.click()
            page.wait_for_timeout(3000)
            dump_page_info(page, "ШАГ 2: 'Мои поиски' dropdown открыт")

            # Показать все mat-list-option
            options = page.locator("mat-list-option")
            log.info(f"\nmat-list-option в dropdown: {options.count()}")
            for i in range(options.count()):
                opt = options.nth(i)
                try:
                    text = opt.inner_text().strip()
                    aria = opt.get_attribute("aria-selected")
                    cls = opt.get_attribute("class") or ""
                    log.info(f"  [{i}] '{text}' aria-selected={aria} selected={'mat-selected' in cls}")
                except:
                    pass

            # Закрыть dropdown
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
        else:
            log.error("Кнопка 'Мои поиски' НЕ НАЙДЕНА!")

        # 3. Попробовать перейти на /search/my-searches
        log.info("\n\n>>> Перехожу на /search/my-searches...")
        page.goto("https://haraba.ru/search/my-searches")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(4000)
        dump_page_info(page, "ШАГ 3: /search/my-searches")

        # 4. Вернуться на /search и попробовать нажать "Мои поиски" + снять все + применить
        log.info("\n\n>>> Перехожу обратно на /search...")
        page.goto("https://haraba.ru/search")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        log.info("\n>>> Открываю 'Мои поиски' dropdown...")
        btn = page.get_by_role("button", name="Мои поиски")
        if btn.count() > 0:
            btn.first.click()
            page.wait_for_timeout(2000)

            # Найти и кликнуть "Выбрать все" если есть
            select_all = page.locator("mat-list-option").filter(has_text="Выбрать все")
            if select_all.count() > 0:
                aria = select_all.first.get_attribute("aria-selected")
                log.info(f"'Выбрать все' aria-selected={aria}")
                if aria == "true":
                    select_all.first.click()
                    page.wait_for_timeout(500)
                    log.info("Снял 'Выбрать все'")
                else:
                    log.info("'Выбрать все' уже снят")
            else:
                # Снять все поиски вручную
                options = page.locator("mat-list-option")
                for i in range(options.count()):
                    opt = options.nth(i)
                    aria = opt.get_attribute("aria-selected")
                    text = opt.inner_text().strip()
                    if aria == "true":
                        opt.click()
                        page.wait_for_timeout(300)
                        log.info(f"Снял: {text}")

            # Снова нажать "Мои поиски" для применения — через click на overlay backdrop
            log.info("\n>>> Применяю (клик на backdrop)...")
            page.keyboard.press("Escape")
            page.wait_for_timeout(2000)

            # Или нажать кнопку "Применить" если есть
            apply_btn = page.get_by_role("button", name="Применить")
            if apply_btn.count() > 0 and apply_btn.first.is_visible():
                apply_btn.first.click()
                page.wait_for_timeout(3000)
                log.info("Кликнул 'Применить'")
            else:
                # Попробовать найти кнопку с текстом "Применить"
                buttons = page.locator("button")
                for i in range(buttons.count()):
                    btn_el = buttons.nth(i)
                    try:
                        text = btn_el.inner_text().strip()
                        if "применить" in text.lower():
                            btn_el.click()
                            page.wait_for_timeout(3000)
                            log.info(f"Кликнул '{text}'")
                            break
                    except:
                        pass

        dump_page_info(page, "ШАГ 4: После снятия всех поисков")

        # 5. Скриншоты и HTML
        page.screenshot(path="data/analyze_ui.png")
        log.info("\n📸 data/analyze_ui.png")

        body = page.inner_html()
        with open("data/analyze_ui.html", "w", encoding="utf-8") as f:
            f.write(body[:100000])
        log.info("📄 data/analyze_ui.html")

        # Ждём 3 секунды чтобы посмотреть
        time.sleep(3)

    finally:
        browser.close()


if __name__ == "__main__":
    main()
