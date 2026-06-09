# Дополнительные фильтры Блок 9
from base import log
from apply_filters_8 import _select_mat_option, _close_dropdown

DRIVE_SELECTOR = "#srch_fltr_drive_type"
SELLER_SELECTOR = "#srch_fltr_salers_type"
LEGAL_SELECTOR = "#srch_fltr_restrictions"
OWNERS_SELECTOR = "#srch_fltr_owners"
COND_SELECTOR = "#srch_fltr_confition"
TRANSMISSION_SELECTOR = "#srch_fltr_transmission"
MILEAGE_SELECTOR = "#srch_fltr_mileage_to"

HARABA_MAP = {
    "drivetrain": {"awd": "Полный", "fwd": "Передний", "rwd": "Задний", "4matic": "Полный"},
    "seller_type": {"private": "Частник", "dealer": "Дилер"},
    "legal_restrictions": {"none": "Без ограничения"},
    "owners_range": {"1-3": "1-3", "1-2": "1-2", "1": "1"},
    "condition": {"not_damaged": "Кроме битых"},
    "transmission": {"automatic": "Автомат", "dsg": "Робот", "manual": "Механика", "cvt": "Вариатор", "robot": "Робот"},
}


def _set_mat_select_multi(page, selector, values):
    """Выбрать несколько значений из mat-select (для transmission)."""
    if isinstance(values, str):
        values = [values]
    sel = page.locator(selector)
    try:
        sel.wait_for(state="visible", timeout=5000)
    except:
        return
    sel.click()
    page.wait_for_timeout(1000)
    for val in values:
        options = page.locator("mat-option")
        for i in range(options.count()):
            try:
                opt_text = options.nth(i).inner_text().strip()
                if val in opt_text:
                    options.nth(i).click()
                    page.wait_for_timeout(300)
                    break
            except:
                pass
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)


def _apply_additional_filters(page, expanded):
    """Применить дополнительные фильтры."""
    # Регионы
    if expanded.regions:
        log.info("[ACTION] regions: %d selected" % len(expanded.regions))
        sel = page.locator("#srch_fltr_region")
        try:
            sel.wait_for(state="visible", timeout=5000)
            for region in expanded.regions:
                sel.click()
                page.wait_for_timeout(1500)
                options = page.locator("mat-option")
                found = False
                for i in range(options.count()):
                    try:
                        opt_text = options.nth(i).inner_text().strip()
                        if region in opt_text:
                            options.nth(i).click()
                            page.wait_for_timeout(500)
                            found = True
                            break
                    except:
                        pass
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
        except:
            pass

    # Привод
    if expanded.drivetrain:
        val = HARABA_MAP["drivetrain"].get(expanded.drivetrain, expanded.drivetrain)
        log.info("[ACTION] drivetrain: %s" % val)
        _select_mat_option(page, DRIVE_SELECTOR, val)
        page.wait_for_timeout(500)

    # Ограничения
    if expanded.legal_restrictions:
        val = HARABA_MAP["legal_restrictions"].get(expanded.legal_restrictions, expanded.legal_restrictions)
        log.info("[ACTION] legal restrictions: %s" % val)
        _select_mat_option(page, LEGAL_SELECTOR, val)
        page.wait_for_timeout(500)

    # Продавец
    if expanded.seller_type:
        val = HARABA_MAP["seller_type"].get(expanded.seller_type, expanded.seller_type)
        log.info("[ACTION] seller type: %s" % val)
        _select_mat_option(page, SELLER_SELECTOR, val)
        page.wait_for_timeout(500)

    # Владельцы
    if expanded.owners_range:
        val = HARABA_MAP["owners_range"].get(expanded.owners_range, expanded.owners_range)
        log.info("[ACTION] owners: %s" % val)
        _select_mat_option(page, OWNERS_SELECTOR, val)
        page.wait_for_timeout(500)

    # Пробег до
    if expanded.mileage_max:
        log.info("[ACTION] mileage_max: %s" % expanded.mileage_max)
        inp = page.locator(MILEAGE_SELECTOR)
        try:
            inp.wait_for(state="visible", timeout=5000)
            inp.click()
            page.wait_for_timeout(200)
            inp.fill(str(expanded.mileage_max))
            page.wait_for_timeout(300)
            log.info("[ACTION] mileage set: %s" % expanded.mileage_max)
        except:
            pass

    # Коробка передач (может быть списком)
    if expanded.transmission:
        trans = expanded.transmission
        if isinstance(trans, str):
            trans = [trans]
        haraba_vals = [HARABA_MAP["transmission"].get(t, t) for t in trans]
        log.info("[ACTION] transmission: %s" % ", ".join(haraba_vals))
        _set_mat_select_multi(page, TRANSMISSION_SELECTOR, haraba_vals)
        page.wait_for_timeout(500)

    # Состояние
    if expanded.condition:
        val = HARABA_MAP["condition"].get(expanded.condition, expanded.condition)
        log.info("[ACTION] condition: %s" % val)
        _select_mat_option(page, COND_SELECTOR, val)
        page.wait_for_timeout(500)
