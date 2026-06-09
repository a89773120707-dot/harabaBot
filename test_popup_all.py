"""test_popup_all.py — тестирую клик "Подробнее про оценку стоимости" на карточке с "Выше оценки"
"""
from playwright.sync_api import sync_playwright
import re

# Карточка #1 — "Выше оценки на 8%"
url = "https://auto.ru/cars/used/sale/audi/q5/1132732001-8b6b8296/"

p = sync_playwright().start()
b = p.chromium.launch(headless=False)
c = b.new_context(viewport={"width": 1920, "height": 1080})
pg = c.new_page()

print(f"Открываю: {url}")
pg.goto(url, wait_until="domcontentloaded", timeout=15000)
pg.wait_for_timeout(3000)

# 1. Сначала покажу что есть на странице
badge = pg.locator("[class*='OfferPriceBadgeNew']").first
if badge.count() > 0:
    badge_text = badge.evaluate("el => el.childNodes[0].textContent").strip()
    print(f"Badge: {badge_text}")
else:
    print("Badge не найден")

# 2. Ищу ссылку "Подробнее про оценку стоимости"
link = pg.get_by_role("link", name="Подробнее про оценку стоимости").first
print(f"\nСсылка найдена: {link.count() > 0}")

if link.count() > 0:
    link_text = link.inner_text(timeout=2000)
    print(f"Текст ссылки: {link_text}")
    
    # 3. Кликаю!
    print("\nКликаю...")
    try:
        with pg.expect_popup(timeout=15000) as popup_info:
            link.click()
        
        popup = popup_info.value
        popup.wait_for_load_state("domcontentloaded", timeout=10000)
        popup.wait_for_timeout(2000)
        
        popup.screenshot(path="results/popup_screenshot.png")
        print(f"Popup скриншот: results/popup_screenshot.png")
        
        # Ищу диапазон
        title_elem = popup.locator(".EvaluationFormResult__title-fEw84").first
        if title_elem.count() > 0:
            title_text = title_elem.inner_text(timeout=3000)
            print(f"Popup title: {title_text}")
            
            m = re.search(r"([\d\s]+)\s*[–—\-]\s*([\d\s]+)\s*₽", title_text)
            if m:
                mn = int(m.group(1).replace(" ", "").replace("\xa0", ""))
                mx = int(m.group(2).replace(" ", "").replace("\xa0", ""))
                print(f"✅ Min: {mn:,} ₽")
                print(f"✅ Max: {mx:,} ₽")
            else:
                print(f"❌ Диапазон не найден в: {title_text}")
        else:
            print("❌ Элемент .EvaluationFormResult__title-fEw84 не найден")
            # Покажу весь текст popup
            body = popup.inner_text("body", timeout=3000)
            print(f"Popup body (first 500):\n{body[:500]}")
        
        popup.close()
    except Exception as e:
        print(f"Ошибка: {e}")
else:
    # Покажу что вообще есть на странице
    body = pg.inner_text("body", timeout=5000)
    # Ищем что-то похожее на "оценка" или "подробнее"
    for keyword in ["оценк", "подробнее", "fair", "price"]:
        if keyword.lower() in body.lower():
            idx = body.lower().index(keyword.lower())
            print(f"Найдено '{keyword}' в: ...{body[max(0,idx-50):idx+100]}...")

b.close()
p.stop()
print("\nГотово")
