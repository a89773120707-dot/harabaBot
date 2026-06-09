"""
test_one_car.py — Открыть m.haraba.ru/search/car/173295809 и показать что происходит.
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE = Path("data/state.json")
RESULTS = Path("results")

def main():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=False)
    
    context = browser.new_context(
        storage_state=str(STATE),
        viewport={"width": 375, "height": 812},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    )
    page = context.new_page()

    # Track redirects
    page.on("response", lambda resp: print(f"  Response: {resp.status} {resp.url[:80]}"))
    page.on("request", lambda req: print(f"  Request: {req.url[:80]}"))

    url = "https://m.haraba.ru/search/car/173295809"
    print(f"Открываю: {url}")
    
    try:
        page.goto(url, wait_until="commit", timeout=30000)
        print(f"\n✅ Загружено!")
        print(f"Final URL: {page.url}")
        print(f"Title: {page.title()}")
        
        time.sleep(3)
        
        body = page.inner_text("body", timeout=10000)
        print(f"\nPage text ({len(body)} chars):")
        print("=" * 50)
        print(body[:1500])
        print("=" * 50)
        
        # Check for expand button
        print("\n=== Expand buttons ===")
        for kw in ["Читать дальше", "Показать все", "Подробнее"]:
            loc = page.get_by_text(kw, exact=False)
            print(f"  '{kw}': {loc.count()}")
        
        page.screenshot(path=str(RESULTS / "test_one_car.png"), full_page=True)
        print(f"\nScreenshot: results/test_one_car.png")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"Current URL: {page.url}")
        page.screenshot(path=str(RESULTS / "test_one_car_error.png"))
        print(f"Error screenshot: results/test_one_car_error.png")

    browser.close()
    pw.stop()

if __name__ == "__main__":
    main()
