"""
run_filter_one_8.py — тестовый запуск фильтров на одной модели.

Запуск:
    python run_filter_one_8.py --only ford_kuga          # реальный запуск
    python run_filter_one_8.py --only ford_kuga --dry-run # dry-run

Логика:
- загрузить config/awd_liquid_ready_8.yaml
- найти модель по id (--only)
- расширить цену через expand_search()
- если dry-run: показать параметры без браузера
- если не dry-run: открыть Haraba, применить фильтры, нажать поиск
- НЕ сохранять поиск
"""

import argparse
import sys
import time

from config_loader_8 import load_searches, get_model_by_id
from search_expander_8 import expand_search
from base import log


def _js_click_button(page):
    """Кликнуть на 'Мои поиски' через JS — обходит overlay."""
    page.evaluate("""(sel) => {
        const el = document.querySelector(sel);
        if (el) el.click();
    }""", "button.mat-warn[aria-haspopup='menu']")


def _clear_overlay_js(page):
    """Убрать overlay через JS."""
    page.evaluate("""() => {
        const container = document.querySelector('.cdk-overlay-container');
        if (container) container.innerHTML = '';
    }""")
    page.wait_for_timeout(500)


def print_dry_run(expanded) -> None:
    """Вывести dry-run информацию о фильтрах."""
    print(f"[START] {expanded.id}")
    print(f"[CONFIG] {expanded.brand} {expanded.model}")
    print(f"[PRICE] config: {expanded.price_from:,}-{expanded.price_to:,}")
    print(f"[PRICE] real: {expanded.price_from_real:,}-{expanded.price_to_real:,}")
    print(f"[DRY RUN] следующие фильтры будут применены:")
    print(f"  - марка: {expanded.brand}")
    print(f"  - модель: {expanded.model}")
    print(f"  - год от: {expanded.year_from}")
    if expanded.year_to:
        print(f"  - год до: {expanded.year_to}")
    print(f"  - цена от: {expanded.price_from_real:,}")
    print(f"  - цена до: {expanded.price_to_real:,}")
    if expanded.mileage_max:
        print(f"  - пробег до: {expanded.mileage_max:,}")
    else:
        print(f"  - пробег: не задан")
    print(f"[DRY RUN] no browser actions")


def run_browser(expanded) -> bool:
    """Открыть Haraba, применить фильтры, нажать поиск."""
    from session_manager import get_authenticated_page
    from apply_filters_8 import apply_filters_from_expanded_config, click_search

    log.info("=" * 60)
    log.info(f"Блок 4: Тест фильтров — {expanded.id}")
    log.info("=" * 60)

    page, context, browser = get_authenticated_page()

    try:
        # Открыть Haraba — страница поиска с фильтрами
        log.info("Открываю Haraba...")
        page.goto("https://haraba.ru/search")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(4000)  # Даём время загрузить фильтры

        # Закрыть cookie-баннер если есть
        cookie_btn = page.get_by_role("button", name="Хорошо")
        if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
            cookie_btn.first.click()
            page.wait_for_timeout(500)

        # ═══ ШАГ: Открыть фильтр через "Мои поиски" ═══
        log.info("=" * 60)
        log.info("ШАГ: Открытие основного фильтра через 'Мои поиски'")
        log.info("=" * 60)

        # 1. Нажать "Мои поиски" — открыть dropdown
        log.info("[1] Открываю 'Мои поиски' dropdown...")
        btn = page.get_by_role("button", name="Мои поиски")
        if btn.count() == 0:
            log.error("❌ Кнопка 'Мои поиски' не найдена!")
            return False
        btn.first.click()
        page.wait_for_timeout(2000)

        # 2. Проверить есть ли выбранные поиски
        options = page.locator("mat-list-option")
        has_selected = False
        for i in range(options.count()):
            opt = options.nth(i)
            aria = opt.get_attribute("aria-selected")
            if aria == "true":
                has_selected = True
                break

        if has_selected:
            # Сценарий 1: поиски выбраны → снять все
            log.info("[2] Поиски выбраны — снимаю все...")

            # Найти "Выбрать все"
            select_all = page.locator("mat-list-option").filter(has_text="Выбрать все")
            if select_all.count() > 0:
                aria_sa = select_all.first.get_attribute("aria-selected")
                if aria_sa == "true":
                    select_all.first.click()
                    page.wait_for_timeout(500)
                    log.info("  Снял 'Выбрать все' (первый клик)")

                # Проверить что всё снято
                options2 = page.locator("mat-list-option")
                for i in range(options2.count()):
                    opt = options2.nth(i)
                    text = opt.inner_text().strip()
                    aria_opt = opt.get_attribute("aria-selected")
                    if aria_opt == "true" and text != "Выбрать все":
                        opt.click()
                        page.wait_for_timeout(300)
                        log.info(f"  Снял: {text}")
            else:
                # Нет "Выбрать все" — снимаем каждый вручную
                for i in range(options.count()):
                    opt = options.nth(i)
                    aria = opt.get_attribute("aria-selected")
                    text = opt.inner_text().strip()
                    if aria == "true":
                        opt.click()
                        page.wait_for_timeout(300)
                        log.info(f"  Снял: {text}")

            # 3. Применить — JS клик "Мои поиски"
            log.info("[3] Применяю (JS клик 'Мои поиски')...")
            _js_click_button(page)
            page.wait_for_timeout(3000)
        else:
            # Сценарий 2: поиски НЕ выбраны → ещё раз нажать "Мои поиски"
            log.info("[2] Поиски НЕ выбраны — закрываю dropdown...")
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)

            # Закрыть overlay через JS
            _clear_overlay_js(page)

            log.info("[3] Применяю (JS клик 'Мои поиски')...")
            _js_click_button(page)
            page.wait_for_timeout(3000)

        # 4. Проверить что фильтр появился
        log.info("[4] Проверяю появление фильтра...")

        # Убрать overlay через JS
        _clear_overlay_js(page)
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        brand_sel = page.locator("#srch_fltr_mark")
        try:
            brand_sel.wait_for(state="visible", timeout=5000)
            log.info("  ✅ Фильтр появился!")
        except Exception:
            log.error("  ❌ Фильтр НЕ появился!")
            return False

        # ═══ ШАГ: Применить фильтры ═══
        filters_ok = apply_filters_from_expanded_config(page, expanded)

        if filters_ok:
            # 5. Нажать "Применить"
            search_ok = click_search(page)

            if search_ok:
                log.info(f"[SUCCESS] filters applied for {expanded.id}")

                page.screenshot(path="data/filter_result.png")
                log.info("📸 data/filter_result.png")

                log.info("Браузер остаётся открытым 5 сек — проверь фильтры в Haraba")
                import time
                time.sleep(5)
                return True
            else:
                log.error(f"[FAIL] не удалось нажать поиск для {expanded.id}")
                return False
        else:
            log.error(f"[FAIL] не удалось применить фильтры для {expanded.id}")
            return False

    finally:
        browser.close()


def main():
    parser = argparse.ArgumentParser(description="Тест фильтров на одной модели")
    parser.add_argument("--only", type=str, required=True, help="ID модели (например ford_kuga)")
    parser.add_argument("--dry-run", action="store_true", help="Показать параметры без запуска браузера")
    args = parser.parse_args()

    # Загрузить конфиг
    searches = load_searches()
    model = get_model_by_id(searches, args.only)

    if model is None:
        print(f"❌ Модель '{args.only}' не найдена в конфиге")
        print(f"Доступные ID: {[s.id for s in searches]}")
        sys.exit(1)

    # Расширить цену
    expanded = expand_search(model)

    if args.dry_run:
        # Dry-run — без браузера
        print_dry_run(expanded)
    else:
        # Реальный запуск
        success = run_browser(expanded)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
