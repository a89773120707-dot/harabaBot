---
name: haraba-mobile-auth
description: Mobile Haraba (m.haraba.ru) requires separate authentication — saved cookies from desktop don't work; need 30s manual login via mobile viewport
source: auto-skill
extracted_at: '2026-06-09T07:48:26.658Z'
---

## Problem

Saved Playwright session (`data/state.json`) from desktop Haraba **does not work** on `m.haraba.ru/search/car/{id}`. The mobile page shows "Вход или регистрация" even when cookies are valid and `check_session.py` reports VALID.

**Root cause:** `m.haraba.ru` uses different auth tokens/cookies than `haraba.ru`. Desktop `.AspNetCore.Cookies` is valid but not recognized on mobile subdomain.

## Detection

Symptoms:
- `page.goto("https://m.haraba.ru/search/car/...")` → returns 200
- `page.title()` → "Haraba - поиск автомобилей с пробегом" (NOT an error)
- `page.inner_text("body")` → contains "Вход или регистрация" / "Номер телефона" / "Продолжить"
- No "Читать дальше" or card details visible

**Check:**
```python
body = page.inner_text("body")
if "вход" in body.lower() or "регистраци" in body.lower() or "номер телефона" in body.lower():
    print("Auth required on mobile!")
```

## Solution: Manual mobile auth with 30s timeout

```python
from playwright.sync_api import sync_playwright
import time

context = browser.new_context(
    storage_state="data/state.json",
    viewport={"width": 375, "height": 812},
    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) ...",
)
page = context.new_context()

page.goto("https://m.haraba.ru/search", wait_until="domcontentloaded", timeout=30000)
time.sleep(2)

# Check if auth is needed
body = page.inner_text("body")
needs_auth = any(kw in body.lower() for kw in ["войти", "логин", "войдите", "авториз", "номер телефона", "регистраци"])

if needs_auth:
    print("⏳ 30 sec — log in via mobile...")
    time.sleep(30)
    page.reload(wait_until="domcontentloaded")
    time.sleep(3)

# Save new session (includes mobile auth tokens)
context.storage_state(path="data/state.json")
```

## After auth

1. Mobile pages will show car details, not login screen
2. `m.haraba.ru/search/car/{id}` → shows specs, seller description, "Читать дальше"
3. **Save the new `state.json`** — it now contains mobile auth tokens

## Important

- **Mobile auth session is separate from desktop** — the new `state.json` after mobile auth will have additional cookies/tokens
- **Always use mobile viewport** when interacting with `m.haraba.ru`
- **Wait 3-5 seconds** after page load for JS to render (Haraba uses Angular)
- **"Читать дальше" button** may require `evaluate("el => el.click()")` + `time.sleep(2)` to expand seller description

## Commands

```bash
# Quick mobile auth
python refresh_session_mobile.py

# Test single car after auth
python test_one_car.py
```
