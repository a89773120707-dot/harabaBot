"""
mobile_first_page_sampler.py — сбор свежих карточек из текущей выдачи Haraba (17 поисков активны).

Использует:
  - session_manager.py → get_authenticated_page()
  - apply_all_searches_17_report.yaml → проверка что 17 поисков активны
  - Селекторы из haraba_bot: tr.mat-row, .cdk-column-*

Аргументы:
  --limit N      — собрать N карточек (default 30)
  --dry-run      — показать план без браузера
  --out PATH     — выходной файл (default results/mobile_first_page_sample.json)
  --debug        -- режим отладки: только 3 карточки + verbose
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yaml
from session_manager import get_authenticated_page
from base import log, RESULTS_DIR

REPORT_PATH = RESULTS_DIR / "apply_all_searches_17_report.yaml"
DEFAULT_OUT = RESULTS_DIR / "mobile_first_page_sample.json"
CACHE_OUT = RESULTS_DIR / "mobile_details_cache_17.json"


# ============================================================
# Блок 12.1 — Проверка активности 17 поисков
# ============================================================

def check_17_active() -> dict:
    """Проверить что 17 поисков активны. Возвращает report dict или None."""
    if not REPORT_PATH.exists():
        log.error(f"Отчёт {REPORT_PATH} не найден — запустите apply_all_searches_17.py")
        return None

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = yaml.safe_load(f)

    checks = [
        ("status == PASS", report.get("status") == "PASS"),
        ("expected == 17", report.get("expected") == 17),
        ("found == 17", report.get("found") == 17),
        ("checked == 17", report.get("checked") == 17),
        ("missing == 0", len(report.get("missing", [])) == 0),
        ("result_count > 0", report.get("result_count", 0) > 0),
    ]

    all_ok = True
    for name, ok in checks:
        if ok:
            log.info(f"  ✅ {name}")
        else:
            log.error(f"  ❌ {name} (actual: {report.get(name.split()[0].replace('== ', ''), 'N/A')})")
            all_ok = False

    if all_ok:
        log.info("  ✅ 17 поисков активны, можно собирать карточки")
        return report
    else:
        log.error("  ❌ 17 поисков НЕ активны — останов")
        return None


# ============================================================
# Блок 12.3 — Парсинг карточек с первой страницы
# ============================================================

def parse_cards_from_rows(rows, limit=30):
    """Парсить карточки из уже найденных строк."""
    total = rows.count()
    log.info(f"  Найдено {total} карточек, лимит {limit}")

    cards = []
    for i in range(min(total, limit)):
        row = rows.nth(i)

        # URL — ищем <a> в строке
        links = row.locator("a")
        url = ""
        ad_id = ""
        for j in range(links.count()):
            try:
                href = links.nth(j).get_attribute("href", timeout=1000)
                if href and ("click?id=" in href or "/search/car/" in href):
                    url = href if href.startswith("http") else f"https://haraba.ru{href}"
                    m1 = re.search(r"id=(\d+)", url)
                    m2 = re.search(r"/(\d{6,})", url)
                    ad_id = (m1 or m2).group(1) if (m1 or m2) else ""
                    break
            except:
                pass

        def get_cell(css_class):
            try:
                cell = row.locator(f".{css_class}")
                return cell.inner_text(timeout=1000).strip()
            except:
                return ""

        title = get_cell("cdk-column-car") or get_cell("cdk-column-model")
        year = get_cell("cdk-column-year")
        price_str = get_cell("cdk-column-price")
        mileage_str = get_cell("cdk-column-mileage")
        seller = get_cell("cdk-column-seller")
        source = get_cell("cdk-column-source")

        price = int(re.sub(r"[^\d]", "", price_str)) if price_str and re.search(r"\d", price_str) else 0
        mileage = int(re.sub(r"[^\d]", "", mileage_str)) if mileage_str and re.search(r"\d", mileage_str) else 0
        year_int = int(year) if year and re.match(r"\d{4}", year) else 0

        mobile_url = f"https://m.haraba.ru/search/car/{ad_id}" if ad_id else ""
        model_guess = title.split()[0] if title else "unknown"

        card = {
            "card_id": ad_id,
            "source": source,
            "model_guess": model_guess,
            "title": title,
            "year": year_int,
            "price": price,
            "mileage": mileage,
            "url": url,
            "mobile_url": mobile_url,
            "raw_text": f"{title} {year} {price_str} {mileage_str} {seller} {source}".strip(),
            "specs": {},
            "mobile_detail_raw_text": "",
        }
        cards.append(card)

    log.info(f"  Спарсено {len(cards)} карточек")
    return cards


def parse_cards_from_table(page, limit=30):
    """Парсить карточки из таблицы текущей выдачи Haraba."""
    log.info(f"[PARSE] Парсинг карточек (limit={limit})...")

    rows = page.locator("tr.mat-row")
    try:
        rows.wait_for(state="visible", timeout=10000)
    except Exception:
        log.error("  ❌ tr.mat-row не появились")
        rows = page.locator("table tbody tr")
        try:
            rows.wait_for(state="visible", timeout=10000)
        except Exception:
            log.error("  ❌ table tbody tr тоже не появились")
            return []

    return parse_cards_from_rows(rows, limit)


# ============================================================
# Блок 12.5 — Открытие mobile/detail карточки
# ============================================================

def open_mobile_detail(page, card, debug=False):
    """Открыть mobile detail страницу и получить raw_text + фото."""
    ad_id = card.get("card_id", "")
    if not ad_id:
        log.warning(f"  [SKIP] card без card_id")
        return card

    mobile_url = f"https://m.haraba.ru/search/car/{ad_id}?source=Telegram&fromMonolith=true"

    try:
        if debug:
            log.info(f"  [DEBUG] Открываю {mobile_url}")

        page.goto(mobile_url, wait_until="load", timeout=30000)
        page.wait_for_timeout(5000)  # JS render

        # Закрыть любые drawer overlay
        try:
            drawer = page.locator(".MuiDrawer-root .MuiModal-backdrop").first
            if drawer.count() > 0:
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
        except:
            pass

        # Клик "Показать все" / "Читать дальше"
        try:
            read_more = page.get_by_text("Показать все").first
            if read_more.count() == 0:
                read_more = page.get_by_text("Читать дальше").first
            if read_more.count() > 0:
                read_more.evaluate("el => el.click()")
                page.wait_for_timeout(2000)
        except:
            pass

        # Получить полный текст страницы
        body_text = page.inner_text("body", timeout=5000)
        card["mobile_detail_raw_text"] = body_text

        # Блок 19: Парсинг фото со страницы
        try:
            photos = []
            main_photo = None

            # 1. Hero image (главное фото)
            try:
                hero = page.locator("[class*='hero'], [class*='MainPhoto'], [class*='mainPhoto'], [class*='swiper-slide-active'] img").first
                hero_src = hero.get_attribute("src", timeout=2000)
                if hero_src and "static" not in hero_src.lower():
                    main_photo = hero_src
                    photos.append(hero_src)
            except:
                pass

            # 2. Все img теги
            img_elements = page.locator("img")
            count = img_elements.count()

            for i in range(count):
                try:
                    img = img_elements.nth(i)
                    src = img.get_attribute("src", timeout=500)
                    alt = img.get_attribute("alt", timeout=500) or ""

                    if not src or not src.startswith("http"):
                        continue

                    # Фильтровать статические, иконки, логотипы
                    if any(skip in src.lower() for skip in ["/static/", "logo", "icon", "avatar", "sprite", "favicon", "arrow", "chevron"]):
                        continue
                    if any(skip in alt.lower() for skip in ["logo", "icon", "avatar", "notification"]):
                        continue

                    if not main_photo:
                        main_photo = src
                    if src not in photos:
                        photos.append(src)
                except:
                    pass

            # Убрать дубли
            seen = set()
            unique_photos = []
            for p in photos:
                if p not in seen:
                    seen.add(p)
                    unique_photos.append(p)

            card["photos"] = {
                "main_photo_url": main_photo,
                "gallery": unique_photos[:10],
                "photo_count": len(unique_photos),
                "source": "mobile_detail"
            }
            if main_photo:
                card["photo_url"] = main_photo
                card["photo_count"] = len(unique_photos)

            if debug:
                log.info(f"  [DEBUG] Photos found: {len(unique_photos)}")
                if main_photo:
                    log.info(f"  [DEBUG] Main: {main_photo[:80]}")
        except Exception as e:
            if debug:
                log.warning(f"  [DEBUG] Photo parsing error: {e}")
            card["photos"] = {"main_photo_url": None, "gallery": [], "photo_count": 0, "source": "error"}

        if debug:
            log.info(f"  [DEBUG] raw_text length: {len(body_text)}")
            # Показать первые 200 символов
            log.info(f"  [DEBUG] raw_text preview: {body_text[:200]}...")

        return card

    except Exception as e:
        log.warning(f"  [WARN] Ошибка открытия {mobile_url}: {e}")
        card["mobile_detail_raw_text"] = f"ERROR: {e}"
        card["photos"] = {"main_photo_url": None, "gallery": [], "photo_count": 0, "source": "error"}
        return card


# ============================================================
# Блок 12.6 — Парсер характеристик
# ============================================================

def parse_mobile_specs(raw_text: str) -> dict:
    """Извлечь engine/transmission/drive/region/owners/autoteka из raw_text."""
    specs = {
        "engine": {"value": "unknown", "source": "not_found"},
        "transmission": {"value": "unknown", "source": "not_found"},
        "drive": {"value": "unknown", "source": "not_found"},
        "region": {"value": "unknown", "source": "not_found"},
        "owners": {"value": "unknown", "source": "not_found"},
        "autoteka_status": {"value": "unknown", "source": "not_found"},
        "body_state": {"value": "unknown", "source": "not_found"},
        "legal_restrictions": {"value": "unknown", "source": "not_found"},
    }

    if not raw_text or "ERROR:" in raw_text:
        return specs

    # Модификация: "2.2 CRDi 4WD AT (200 л.с.)" → это engine
    m = re.search(r"Модификация\s*\n\s*([^\n]+)", raw_text)
    if m:
        val = m.group(1).strip()
        if val and len(val) > 3:
            specs["engine"] = {"value": val, "source": "mobile_detail"}

    # Двигатель: "Тип двигателя\nДизель"
    m = re.search(r"Тип двигателя\s*\n\s*([^\n]+)", raw_text)
    if m:
        val = m.group(1).strip()
        if val and len(val) > 2:
            # Объединить с модификацией
            existing = specs["engine"]["value"]
            if existing == "unknown":
                specs["engine"] = {"value": val, "source": "mobile_detail"}
            else:
                specs["engine"] = {"value": f"{existing} ({val})", "source": "mobile_detail"}

    # Объём: "2.2 л"
    m = re.search(r"Объём двигателя\s*\n\s*([^\n]+)", raw_text)
    if m:
        val = m.group(1).strip()
        existing = specs["engine"]["value"]
        if existing != "unknown" and val:
            specs["engine"] = {"value": f"{existing}, {val}", "source": "mobile_detail"}

    # КПП
    m = re.search(r"КПП\s*\n\s*([^\n]+)", raw_text)
    if m:
        val = m.group(1).strip()
        if val and len(val) > 2:
            specs["transmission"] = {"value": val, "source": "mobile_detail"}

    # Привод
    m = re.search(r"Привод\s*\n\s*([^\n]+)", raw_text)
    if m:
        val = m.group(1).strip()
        if val and len(val) > 2:
            specs["drive"] = {"value": val, "source": "mobile_detail"}

    # Регион — искать город/область в начале текста или где угодно
    # Регион — используем region_parser
    from region_parser import parse_region as _pr
    rr = _pr(raw_text)
    if rr["allowed"]:
        specs["region"] = {"value": rr["normalized"], "source": "mobile_detail"}

    # Владельцы: "Владельцы\n3"
    m = re.search(r"Владельцы\s*\n\s*(\d+)", raw_text)
    if m:
        specs["owners"] = {"value": m.group(1), "source": "mobile_detail"}

    # Автотека
    if "Предпроверка от Автотеки" in raw_text:
        specs["autoteka_status"] = {"value": "available", "source": "mobile_detail"}

    # Состояние кузова
    m = re.search(r"Состояние\s*\n\s*([^\n]+)", raw_text)
    if m:
        val = m.group(1).strip()
        if val and len(val) > 2:
            specs["body_state"] = {"value": val, "source": "mobile_detail"}

    # Ограничения — искать факт наличия, а не просто заголовок поля
    # "Ограничение на регистрацию" — это заголовок, значение на след строке
    # Если после заголовка нет явного "Есть", "Запрет", "Арест" — считаем чистым
    lines = raw_text.split('\n')
    legal_found = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "Ограничение на регистрацию" in stripped:
            # Проверить следующую строку — это значение
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip().lower()
                if any(kw in next_line for kw in ["есть", "да", "запрет", "арест", "огранич"]):
                    specs["legal_restrictions"] = {"value": "Есть ограничение", "source": "mobile_detail"}
                    legal_found = True
                else:
                    specs["legal_restrictions"] = {"value": "Без ограничений", "source": "mobile_detail"}
                    legal_found = True
            break

    if not legal_found:
        # Fallback: если нет секции Ограничение — проверить на явные关键词
        if any(kw in raw_text for kw in ["Запрет регистрационных", "Залог", "Арест"]):
            specs["legal_restrictions"] = {"value": "Есть ограничение", "source": "mobile_detail"}
        else:
            specs["legal_restrictions"] = {"value": "unknown", "source": "not_found"}

    return specs


# ============================================================
# Блок 12.9 — Coverage report
# ============================================================

def compute_coverage(cards):
    """Посчитать coverage для каждого поля."""
    total = len(cards)
    if total == 0:
        return {}

    fields = ["engine", "transmission", "drive", "region", "owners", "autoteka_status"]
    coverage = {}

    for field in fields:
        found = sum(1 for c in cards if c.get("specs", {}).get(field, {}).get("value", "unknown") != "unknown")
        coverage[field] = {
            "found": found,
            "missing": total - found,
            "coverage_percent": round(found / total * 100, 1),
        }

    return coverage


# ============================================================
# Блок 12.10 — Decision
# ============================================================

def make_decision(coverage):
    """Решить: mobile достаточно или нужен detail enrichment."""
    thresholds = {
        "engine": 70,
        "transmission": 70,
        "region": 70,
        "drive": 90,
    }

    blockers = []
    for field, threshold in thresholds.items():
        if field in coverage:
            pct = coverage[field]["coverage_percent"]
            if pct < threshold:
                blockers.append(f"{field}: {pct}% < {threshold}%")

    if not blockers:
        return {
            "primary_source": "mobile_detail",
            "telegram_ready": True,
            "reason": "All fields above threshold",
        }
    else:
        return {
            "primary_source": "mobile_detail_plus_extra_enrichment",
            "telegram_ready": False,
            "blockers": blockers,
        }


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Сбор свежих карточек из 17 активных поисков Haraba")
    parser.add_argument("--limit", type=int, default=30, help="Макс карточек (default 30)")
    parser.add_argument("--dry-run", action="store_true", help="Проверить без браузера")
    parser.add_argument("--out", type=str, default=str(DEFAULT_OUT), help="Выходной файл")
    parser.add_argument("--debug", action="store_true", help="Debug mode: 3 cards + verbose")
    args = parser.parse_args()

    if args.debug:
        args.limit = 3

    if args.dry_run:
        log.info("=== DRY RUN ===")
        log.info(f"  limit={args.limit}")
        log.info(f"  out={args.out}")
        log.info("Проверяю активность 17 поисков...")
        report = check_17_active()
        if report:
            log.info("✅ 17 поисков активны, можно запускать")
        else:
            log.error("❌ 17 поисков НЕ активны")
        return

    # Блок 12.1: Проверка активности
    log.info("\n[STEP 1] Проверка активности 17 поисков...")
    report = check_17_active()
    if not report:
        log.error("17 поисков не активны — останавливаюсь")
        sys.exit(1)

    # Открыть браузер
    log.info("\n[STEP 2] Открываю Haraba...")
    page, context, browser = get_authenticated_page()

    try:
        # Открыть текущую выдачу
        page.goto("https://haraba.ru/search")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        # Проверить есть ли результаты — если нет, активировать 17 поисков
        rows_check = page.locator("table tbody tr")
        has_results = False
        try:
            rows_check.wait_for(state="visible", timeout=3000)
            if rows_check.count() > 0:
                has_results = True
        except:
            pass

        if not has_results:
            log.info("  Результаты не найдены — активирую 17 поисков...")
            from apply_all_searches_17 import (
                EXPECTED_ALL, _clear_overlay_js, _js_click
            )

            # Открыть dropdown
            _clear_overlay_js(page)
            _js_click(page)
            page.wait_for_timeout(5000)

            # Отметить все 17
            options = page.locator("mat-list-option")
            for i in range(options.count()):
                opt = options.nth(i)
                text = opt.inner_text().strip()
                aria = opt.get_attribute("aria-selected")
                matched = any(e in text for e in EXPECTED_ALL)
                if matched and aria != "true":
                    opt.click()
                    page.wait_for_timeout(200)

            # Применить — перезагрузить страницу (Haraba сохранит галочки)
            page.reload(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)

            # Скроллить вниз чтобы увидеть таблицу с результатами
            page.evaluate("window.scrollTo(0, 1000)")
            page.wait_for_timeout(3000)

            # Проверить что появились результаты — попробовать ВСЕ возможные селекторы
            page.screenshot(path="results/debug_after_activate.png")
            log.info("  📸 results/debug_after_activate.png")

            selectors_to_try = [
                "tr.mat-row",
                "table tbody tr",
                ".mat-row",
                "mat-row",
                "[data-row]",
                "tbody tr",
                ".cdk-row",
                "div.card",
                "div.mat-card",
                "mat-card",
            ]

            rows = None
            for sel in selectors_to_try:
                try:
                    els = page.locator(sel)
                    cnt = els.count()
                    log.info(f"  Селектор '{sel}': {cnt}")
                    if cnt > 0:
                        rows = els
                        log.info(f"  ✅ Нашёл: '{sel}' → {cnt}")
                        break
                except:
                    log.info(f"  Селектор '{sel}': ошибка")

            if rows is None:
                log.error("  ❌ Ни один селектор не нашёл карточки")
                body_text = page.inner_text("body", timeout=5000)
                log.info(f"  Body text preview: {body_text[:500]}")
                sys.exit(1)

            # Парсим найденные карточки
            cards = parse_cards_from_rows(rows, limit=args.limit)

        else:
            # Результаты уже есть — парсим
            log.info("\n[STEP 3] Парсинг карточек с первой страницы...")
            cards = parse_cards_from_table(page, limit=args.limit)

        if not cards:
            log.error("Карточки не найдены — останавливаюсь")
            sys.exit(1)

        # Блок 12.5: Открыть mobile detail для каждой
        log.info(f"\n[STEP 4] Открытие mobile detail для {len(cards)} карточек...")
        for i, card in enumerate(cards):
            log.info(f"  [{i+1}/{len(cards)}] {card.get('title', 'unknown')} ({card.get('card_id', '?')})")
            card = open_mobile_detail(page, card, debug=args.debug)
            cards[i] = card

        # Блок 12.6: Парсинг характеристик
        log.info("\n[STEP 5] Парсинг характеристик...")
        for card in cards:
            card["specs"] = parse_mobile_specs(card.get("mobile_detail_raw_text", ""))

        # Блок 12.9: Coverage report
        log.info("\n[STEP 6] Coverage report...")
        coverage = compute_coverage(cards)
        for field, stats in coverage.items():
            log.info(f"  {field}: {stats['coverage_percent']}% ({stats['found']}/{stats['found']+stats['missing']})")

        # Блок 12.10: Decision
        log.info("\n[STEP 7] Decision...")
        decision = make_decision(coverage)
        log.info(f"  Telegram ready: {decision.get('telegram_ready', False)}")
        if decision.get("blockers"):
            for b in decision["blockers"]:
                log.info(f"  ❌ {b}")

        # Блок 12.8: Сохранить результат
        # Блок 19: Обогатить фото
        from photo_parser import enrich_cards_with_photos
        cards = enrich_cards_with_photos(cards)

        log.info(f"\n[STEP 8] Сохраняю в {args.out}...")
        sample = {
            "generated_at": datetime.now().isoformat(),
            "source": "haraba_current_17_searches",
            "cards_total": len(cards),
            "cards": cards,
        }
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sample, f, ensure_ascii=False, indent=2)
        log.info(f"  ✅ Сохранено {len(cards)} карточек")

        # Coverage report
        coverage_path = RESULTS_DIR / "mobile_fields_coverage_report.yaml"
        with open(coverage_path, "w", encoding="utf-8") as f:
            yaml.dump({
                "total_cards": len(cards),
                "coverage": coverage,
                "decision": decision,
            }, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        log.info(f"  ✅ Coverage report: {coverage_path}")

        # Decision report
        decision_path = RESULTS_DIR / "telegram_data_source_decision.yaml"
        with open(decision_path, "w", encoding="utf-8") as f:
            yaml.dump(decision, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        log.info(f"  ✅ Decision: {decision_path}")

        # Cache
        with open(CACHE_OUT, "w", encoding="utf-8") as f:
            json.dump(cards, f, ensure_ascii=False, indent=2)
        log.info(f"  ✅ Cache: {CACHE_OUT}")

    finally:
        browser.close()

    log.info("\n✅ Готово!")


if __name__ == "__main__":
    main()
