"""test_save_sportage.py — тест save_current_search на Kia Sportage 2012-2018"""
import sys
sys.path.insert(0, '.')
from session_manager import get_authenticated_page
from saved_search_helper_8 import save_current_search, check_search_exists, _clear_overlays
from base import log

SAVE_NAME = "Kia Sportage 2012-2018"

page, context, browser = get_authenticated_page()

try:
    # 1. Открываем Haraba
    log.info("Открываю Haraba...")
    page.goto("https://haraba.ru", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(3000)
    _clear_overlays(page)

    # 2. Открываем фильтры
    log.info("Открываю фильтры...")
    my_searches = page.get_by_text("Мои поиски").first
    if my_searches.count() > 0:
        my_searches.click()
        page.wait_for_timeout(2000)

    # 3. Сбрасываем
    log.info("Сбрасываю фильтры...")
    clear_btn = page.get_by_text("Сбросить").first
    if clear_btn.count() > 0:
        clear_btn.click()
        page.wait_for_timeout(1000)

    # 4. Марка
    log.info("Марка: Kia")
    brand_select = page.locator("mat-select[formcontrolname='mark']").first
    if brand_select.count() > 0:
        brand_select.click()
        page.wait_for_timeout(1000)
        page.get_by_text("Kia").first.click()
        page.wait_for_timeout(3000)

    # 5. Год — ДО модели!
    log.info("Год: 2012-2018")
    year_min = page.locator("input[formcontrolname='yearMin']").first
    if year_min.count() > 0:
        year_min.fill("2012")
        page.wait_for_timeout(500)
    year_max = page.locator("input[formcontrolname='yearMax']").first
    if year_max.count() > 0:
        year_max.fill("2018")
        page.wait_for_timeout(500)

    # 6. Модель
    log.info("Модель: Sportage")
    model_select = page.locator("mat-select[formcontrolname='model']").first
    if model_select.count() > 0:
        model_select.click()
        page.wait_for_timeout(1000)
        page.get_by_text("Sportage").first.click()
        page.wait_for_timeout(3000)

    # 7. Привод AWD
    log.info("Привод: AWD")
    drive_select = page.locator("mat-select[formcontrolname='drivetrain']").first
    if drive_select.count() > 0:
        drive_select.click()
        page.wait_for_timeout(1000)
        drive_opt = page.get_by_text("Полный").first
        if drive_opt.count() == 0:
            drive_opt = page.get_by_text("полный").first
        if drive_opt.count() > 0:
            drive_opt.click()
            page.wait_for_timeout(1000)

    # 8. Применяем
    log.info("Применяю...")
    apply_btn = page.get_by_text("Применить").first
    if apply_btn.count() > 0:
        apply_btn.click()
        page.wait_for_timeout(5000)

    page.screenshot(path="results/test_sportage_before_save.png")
    log.info("Скриншот до сохранения: results/test_sportage_before_save.png")

    # 9. Проверяем — может уже существует?
    log.info(f"Проверяю существует ли '{SAVE_NAME}'...")
    if check_search_exists(page, SAVE_NAME):
        log.info(f"✅ '{SAVE_NAME}' уже существует — пропускаю сохранение")
    else:
        log.info(f"Не существует — сохраняю...")
        result = save_current_search(page, SAVE_NAME)
        if result:
            log.info(f"✅ Сохранено: {SAVE_NAME}")
        else:
            log.info(f"❌ Не удалось сохранить: {SAVE_NAME}")

    # 10. Финальная проверка
    log.info("Финальная проверка...")
    exists = check_search_exists(page, SAVE_NAME)
    log.info(f"Поиск '{SAVE_NAME}' существует: {exists}")

    page.screenshot(path="results/test_sportage_final.png")
    log.info("Финальный скриншот: results/test_sportage_final.png")

finally:
    browser.close()
