"""
apply_all_searches_17.py — активировать галочки на всех 17 поисках (8 старых + 9 новых).

Логика:
1. Открыть Haraba с авторизованной сессией
2. Открыть dropdown "Мои поиски"
3. Собрать все доступные search names
4. Сверить с ожидаемыми 17
5. Если missing > 0 — остановиться и вывести отчёт
6. Если все есть — снять лишние галочки, поставить нужные 17
7. Применить
8. Посчитать карточки
9. Сохранить отчёт: results/apply_all_searches_17_report.yaml
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

import yaml
from session_manager import get_authenticated_page
from base import log, RESULTS_DIR

# ──────────────────────────────────────────────────────────────
# 17 ожидаемых имён поисков
# ──────────────────────────────────────────────────────────────

EXPECTED_8 = [
    "Kia Sorento Prime 2016-2019",
    "Volkswagen Touareg NF 2010-2016",
    "Volkswagen Tiguan 2011-2018",
    "Nissan X-Trail 2011-2018",
    "Nissan Qashqai J11 2014-2018",
    "Ford Kuga 2013-2018",
    "Mercedes-Benz GLK 220 CDI 2012-2015",
    "Volkswagen Multivan T5 2010-2015",
]

EXPECTED_9 = [
    "Audi Q5 2012-2018",
    "Hyundai Santa Fe 2012-2018",
    "Kia Sorento 2012-2018",
    "Kia Sportage 2012-2018",
    "Mazda CX-5 2012-2020",
    "Mitsubishi Pajero IV 2008-2015",
    "Hyundai Grand Santa Fe 2014-2019",
    "Nissan Pathfinder R51 2011-2014",
    "Volvo XC90 2011-2014",
]

EXPECTED_ALL = EXPECTED_8 + EXPECTED_9


def _clear_overlay_js(page):
    page.evaluate("""() => {
        const container = document.querySelector('.cdk-overlay-container');
        if (container) container.innerHTML = '';
    }""")
    page.wait_for_timeout(500)


def _js_click(page):
    page.evaluate("""(sel) => {
        const el = document.querySelector(sel);
        if (el) el.click();
    }""", "button.mat-warn[aria-haspopup='menu']")


def main():
    log.info("=" * 60)
    log.info("apply_all_searches_17.py — активация 17 поисков")
    log.info("=" * 60)
    log.info(f"Ожидаемых: {len(EXPECTED_ALL)}")

    page, context, browser = get_authenticated_page()

    try:
        # ── Шаг 1: Открыть Haraba ──
        page.goto("https://haraba.ru/search")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(5000)

        # ── Шаг 2: Открыть dropdown "Мои поиски" ──
        log.info("\n[STEP 1] Открываю dropdown 'Мои поиски'...")
        _clear_overlay_js(page)
        _js_click(page)
        page.wait_for_timeout(5000)

        # ── Шаг 3: Собрать все имена ──
        log.info("[STEP 2] Собираю все search names...")
        options = page.locator("mat-list-option")
        opt_count = options.count()
        log.info(f"  Найдено {opt_count} mat-list-option")

        available_names = []
        all_items = []  # (index, text, aria-selected)

        for i in range(opt_count):
            opt = options.nth(i)
            text = opt.inner_text().strip()
            aria = opt.get_attribute("aria-selected")
            all_items.append((i, text, aria))
            # Игнорируем "Выбрать все" и пустые
            if text and len(text) > 3 and "выбрать" not in text.lower():
                available_names.append(text)
                log.info(f"  [{i}] '{text}' selected={aria}")

        log.info(f"  Всего поисков в dropdown: {len(available_names)}")

        # ── Шаг 4: Сверить с ожидаемыми 17 ──
        log.info("\n[STEP 3] Сверяю с ожидаемыми 17...")
        missing = []
        for expected in EXPECTED_ALL:
            found = any(expected in avail for avail in available_names)
            if found:
                log.info(f"  ✅ '{expected}'")
            else:
                log.error(f"  ❌ '{expected}' — НЕ НАЙДЕН")
                missing.append(expected)

        log.info(f"\n  Expected: {len(EXPECTED_ALL)}")
        log.info(f"  Found:    {len(EXPECTED_ALL) - len(missing)}")
        log.info(f"  Missing:  {len(missing)}")

        if missing:
            log.error(f"\n❌ {len(missing)} поисков отсутствует — останавливаюсь!")
            report = {
                "timestamp": datetime.now().isoformat(),
                "expected": len(EXPECTED_ALL),
                "found": len(EXPECTED_ALL) - len(missing),
                "missing": missing,
                "available": available_names,
                "status": "FAIL",
            }
            _save_report(report)
            return

        # ── Шаг 5: Снять лишние галочки ──
        log.info("\n[STEP 4] Снимаю лишние галочки...")
        for i, text, aria in all_items:
            if aria == "true" and text not in EXPECTED_ALL and not any(e in text for e in EXPECTED_ALL):
                log.info(f"  Снимаю '{text}'")
                options.nth(i).click()
                page.wait_for_timeout(200)

        # ── Шаг 6: Поставить галочки на 17 ──
        log.info("\n[STEP 5] Ставлю галочки на 17 нужных...")
        checked = 0
        for i, text, aria in all_items:
            matched = False
            for expected in EXPECTED_ALL:
                if expected in text:
                    matched = True
                    break
            if matched and aria != "true":
                log.info(f"  Отмечаю '{text}'")
                options.nth(i).click()
                page.wait_for_timeout(200)
                checked += 1
            elif matched and aria == "true":
                checked += 1
                log.info(f"  Уже отмечено: '{text}'")

        log.info(f"\n  Отмечено: {checked}")

        # ── Шаг 7: Применить ──
        log.info("\n[STEP 6] Нажимаю 'Мои поиски' — применить...")
        _js_click(page)
        page.wait_for_timeout(10000)

        # ── Шаг 8: Посчитать карточки ──
        log.info("\n[STEP 7] Считаю результаты...")
        result_count = 0
        for attempt in range(5):
            # Пробуем оба селектора
            rows = page.locator("table tbody tr")
            try:
                rows.wait_for(state="visible", timeout=5000)
                result_count = rows.count()
                if result_count > 0:
                    break
            except:
                pass
            log.info(f"  Попытка {attempt+1}: {result_count}, жду...")
            page.wait_for_timeout(5000)

        log.info(f"  Результатов: {result_count}")

        # ── Шаг 9: Отчёт ──
        report = {
            "timestamp": datetime.now().isoformat(),
            "expected": len(EXPECTED_ALL),
            "found": len(EXPECTED_ALL),
            "missing": [],
            "checked": checked,
            "result_count": result_count,
            "status": "PASS" if checked == 17 and result_count > 0 else "WARN",
            "search_names": EXPECTED_ALL,
        }
        _save_report(report)

        log.info(f"\n{'='*60}")
        log.info(f"SUMMARY")
        log.info(f"{'='*60}")
        log.info(f"  Expected: {report['expected']}")
        log.info(f"  Found:    {report['found']}")
        log.info(f"  Checked:  {report['checked']}")
        log.info(f"  Missing:  {len(report['missing'])}")
        log.info(f"  Results:  {report['result_count']}")
        log.info(f"  Status:   {report['status']}")

    finally:
        browser.close()


def _save_report(report):
    report_path = RESULTS_DIR / "apply_all_searches_17_report.yaml"
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.dump(report, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    log.info(f"\n📄 Отчёт сохранён: {report_path}")


if __name__ == "__main__":
    main()
