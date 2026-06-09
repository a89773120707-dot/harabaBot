---
name: haraba-mobile-photo-parsing
description: Extract photos from Haraba mobile detail pages — wait_until="load", hero selector, img filtering
source: auto-skill
extracted_at: '2026-06-09T14:30:00.000Z'
---

## Haraba Mobile Photo Parsing

### Critical: wait_until="load"

**Problem:** `wait_until="domcontentloaded"` → page body is empty (0 chars), no imgs found.

**Fix:**
```python
page.goto(mobile_url, wait_until="load", timeout=30000)
page.wait_for_timeout(5000)  # JS render after load
```

### Hero image (main photo)

```python
hero = page.locator("[class*='hero'], [class*='MainPhoto'], [class*='mainPhoto'], [class*='swiper-slide-active'] img").first
hero_src = hero.get_attribute("src", timeout=2000)
if hero_src and "static" not in hero_src.lower():
    main_photo = hero_src
```

### All img elements

```python
imgs = page.locator("img")
count = imgs.count()

for i in range(count):
    src = imgs.nth(i).get_attribute("src", timeout=500)
    alt = imgs.nth(i).get_attribute("alt", timeout=500) or ""

    if not src or not src.startswith("http"):
        continue

    # Filter out static assets, icons, logos
    if any(skip in src.lower() for skip in ["/static/", "logo", "icon", "avatar", "sprite", "favicon", "arrow", "chevron"]):
        continue
    if any(skip in alt.lower() for skip in ["logo", "icon", "avatar", "notification"]):
        continue
```

### Photo sources found

| Source | Description |
|--------|-------------|
| `avatars.mds.yandex.net` | Auto.ru images |
| `*.img.avito.st` | Avito images |
| `s*.auto.drom.ru` | Drom.ru images |

### Send to Telegram

**URL parameter fails** for avito.st. Must download as bytes:

```python
import requests
from io import BytesIO

resp = requests.get(photo_url, timeout=10, stream=True)
resp.raise_for_status()
photo_bytes = BytesIO(resp.content)

await bot.send_photo(chat_id=chat_id, photo=photo_bytes, caption=caption, reply_markup=keyboard)
```

### Fallback

If photo download fails → `send_message(text=text)` — never block pipeline.

### Files

- `mobile_first_page_sampler.py` — `open_mobile_detail()` with wait_until="load"
- `photo_parser.py` — offline extraction from raw_text
- `telegram_sender.py` — send_photo with bytes download
