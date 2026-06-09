"""
analyze_and_test_filters.py — анализатор + тест фильтров Haraba.

Алгоритм:
1. Открыть /search
2. Нажать "Мои поиски" → проверить галочки
3. Если галочки есть → снять все (двойной клик на "Выбрать все")
4. Применить (нажать "Мои поиски")
5. Показать все элементы фильтров
6. Применить фильтры для ford_kuga
7. Нажать "Применить"
8. Показать результат
"""

from session_manager import get_authenticated_page
from base import log
from config_loader_8 import load_searches, get_model_by_id
from search_expander_8 import expand_search
from apply_filters_8 import apply_filters_from_expanded_config, click_search
import time


def ensure_filters_visible(page):
    """Убедиться что основной фильтр видим — снять все сохранённые поиски."""
    log.info("\n" + "=" * 60)
    log.info("ШАГ: Подготовка фильтров (снятие сохранённых поисков)")
    log.info("=" * 60)

    # 1. Нажать "Мои поиски" — открыть dropdown
    log.info("[1] Открываю 'Мои поиски' dropdown...")
    btn = page.get_by_role("button", name="Мои поиски")
    if btn.count() == 0:
        log.error("❌ Кнопка 'Мои поиски' не найдена!")
        return False
    btn.first.click()
    page.wait_for_timeout(2000)

    # 2. Найти "Выбрать все"
    select_all = page.locator("mat-list-option").filter(has_text="Выбрать все")

    if select_all.count() > 0:
        aria = select_all.first.get_attribute("aria-selected")
        log.info(f"[2] 'Выбрать все' aria-selected={aria}")

        if aria == "true":
            # Первый клик — снять все
            select_all.first.click()
            page.wait_for_timeout(500)
            log.info("  Первый клик на 'Выбрать все' — снял все поиски")

            # Проверить что все сняты
            options = page.locator("mat-list-option")
            for i in range(options.count()):
                opt = options.nth(i)
                text = opt.inner_text().strip()
                aria_opt = opt.get_attribute("aria-selected")
                if aria_opt == "true":
                    # Ещё снят — кликнуть ещё раз
                    log.info(f"  '{text}' ещё выбран — снимаю повторно")
                    opt.click()
                    page.wait_for_timeout(300)
        else:
            log.info("  'Выбрать все' уже снят — все поиски отключены")
    else:
        # Нет "Выбрать все" — снимаем каждый поиск вручную
        log.info("[2] 'Выбрать все' не найден — снимаю каждый поиск вручную...")
        options = page.locator("mat-list-option")
        for i in range(options.count()):
            opt = options.nth(i)
            text = opt.inner_text().strip()
            aria_opt = opt.get_attribute("aria-selected")
            if aria_opt == "true":
                opt.click()
                page.wait_for_timeout(300)
                log.info(f"  Снял: {text}")

    # 3. Применить — нажать на backdrop или Escape
    log.info("[3] Применяю (Escape)...")
    page.keyboard.press("Escape")
    page.wait_for_timeout(3000)

    # 4. Проверить что фильтр появился
    log.info("[4] Проверяю появление фильтров...")
    brand_sel = page.locator("#srch_fltr_mark")
    try:
        brand_sel.wait_for(state="visible", timeout=5000)
        log.info("  ✅ Фильтр появился! (#srch_fltr_mark visible)")
        return True
    except Exception:
        log.warning("  ⚠ Фильтр НЕ появился — пробую нажать 'Применить' кнопку...")
        # Попробовать найти кнопку "Применить" в контексте моих поисков
        apply_in_menu = page.get_by_role("button", name="Применить")
        if apply_in_menu.count() > 0 and apply_in_menu.first.is_visible():
            apply_in_menu.first.click()
            page.wait_for_timeout(3000)
            try:
                brand_sel.wait_for(state="visible", timeout=5000)
                log.info("  ✅ Фильтр появился после 'Применить'!")
                return True
            except:
                pass

        # Fallback — ещё раз Escape + подождать
        page.keyboard.press("Escape")
        page.wait_for_timeout(3000)
        try:
            brand_sel.wait_for(state="visible", timeout=5000)
            log.info("  ✅ Фильтр появился после повторного Escape!")
            return True
        except:
            log.error("  ❌ Фильтр НЕ появился!")
            return False


def dump_filters_state(page):
    """Показать состояние фильтров."""
    log.info("\n" + "=" * 60)
    log.info("ДАМП ФИЛЬТРОВ")
    log.info("=" * 60)

    # mat-select
    selects = page.locator("mat-select")
    log.info(f"mat-select: {selects.count()}")
    for i in range(selects.count()):
        sel = selects.nth(i)
        try:
            fcn = sel.get_attribute("formcontrolname") or ""
            sid = sel.get_attribute("id") or ""
            log.info(f"  [{i}] id='{sid}' fcn='{fcn}'")
        except:
            pass

    # input
    inputs = page.locator("input:not([type='hidden']):not([type='checkbox']):not([type='radio'])")
    log.info(f"\ninput: {inputs.count()}")
    for i in range(inputs.count()):
        inp = inputs.nth(i)
        try:
            inp_id = inp.get_attribute("id") or ""
            placeholder = inp.get_attribute("placeholder") or ""
            log.info(f"  [{i}] id='{inp_id}' placeholder='{placeholder}'")
        except:
            pass


def main():
    log.info("=" * 60)
    log.info("АНАЛИЗ + ТЕСТ ФИЛЬТРОВ HARABA")
    log.info("=" * 60)

    page, context, browser = get_authenticated_page()

    try:
        # 1. Открыть /search
        log.info("Открываю https://haraba.ru/search...")
        page.goto("https://haraba.ru/search")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(4000)

        # Закрыть cookie-баннер
        cookie_btn = page.get_by_role("button", name="Хорошо")
        if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
            cookie_btn.first.click()
            page.wait_for_timeout(500)

        # 2. Убедиться что фильтр видим
        if not ensure_filters_visible(page):
            log.error("Не удалось открыть фильтр — останавливаюсь")
            return

        # 3. Дамп фильтров
        dump_filters_state(page)

        # 4. Применить фильтры для ford_kuga
        log.info("\n" + "=" * 60)
        log.info("ШАГ: Применение фильтров для ford_kuga")
        log.info("=" * 60)

        searches = load_searches()
        ford = get_model_by_id(searches, "ford_kuga")
        if ford is None:
            log.error("ford_kuga не найден!")
            return

        expanded = expand_search(ford)

        filters_ok = apply_filters_from_expanded_config(page, expanded)

        if filters_ok:
            # 5. Нажать "Применить"
            search_ok = click_search(page)

            if search_ok:
                log.info("\n✅ [SUCCESS] filters applied for ford_kuga")

                page.screenshot(path="data/ford_kuga_result.png")
                log.info("📸 data/ford_kuga_result.png")

                log.info("\nБраузер остаётся открытым 5 сек — проверь результат...")
                time.sleep(5)
            else:
                log.error("❌ Не удалось нажать 'Применить'")
        else:
            log.error("❌ Не удалось применить фильтры")

    finally:
        browser.close()


if __name__ == "__main__":
    main()
