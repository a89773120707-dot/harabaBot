---
name: legal-parser-v1
description: Parse legal restrictions from Avtoteka raw_text, distinguishing section headers from actual restriction status
source: auto-skill
extracted_at: '2026-06-09T07:07:04.375Z'
---

## Problem

In Avtoteka mobile detail pages, phrases like "Сведения о залоге" and "Ограничение на регистрацию" are **section headers** in the Avtoteka report preview, NOT actual restriction statuses. The old parser in `telegram_audit.py` (`check_legal_restrictions()`) only checked for keyword presence, which would incorrectly flag all cards as restricted.

**Before:** 0 cards had `legal=unknown` but no card was correctly parsed as restricted vs clear from raw_text.

## Solution: Three-tier classification in `legal_parser.py`

### Tier 1: Clear (no restrictions)

Phrases that confirm the car is clean:
- "без ограничен" (without restrictions)
- "ограничений нет" (no restrictions)
- "юридически чист" (legally clean)
- "нет ограничений" (no restrictions found)

### Tier 2: Restricted (do not send)

Phrases that confirm actual restrictions:
- "есть ограничение" (there IS a restriction)
- "запрет регистрационных" (registration ban)
- "арест" (arrest/seizure)
- "обременение" (encumbrance)

**NOT restricted (these are Avtoteka section headers):**
- "сведения о залоге" (information about lien — section title)
- "ограничение на регистрацию" (restriction on registration — section title)
- "сведения о розыске" (information about wanted — section title)
- "предпроверка от автотеки" (pre-check from Autoteka — section title)

### Tier 3: Unknown (warning but send)

No legal-related text found in raw_text. For Telegram v1, this is a warning but NOT a hard block.

## Algorithm

```python
def parse_legal(text):
    t = text.lower()
    
    # 1. Check for restrictions — but exclude Avtoteka headers
    for kw in RESTRICTED_KEYWORDS:
        if kw in t:
            # "залог" in "сведения о залоге" → header, skip
            # "залог" in "залог не найден" → OK, not a header
            is_header = any(h in t and t.count(h) <= t.count(kw) + 1
                          for h in AVTOTEDA_HEADERS if kw in h)
            if not is_header:
                return {"status": "restricted", "value": kw}
    
    # 2. Check for clear status
    for kw in CLEAR_KEYWORDS:
        if kw in t:
            return {"status": "clear", "value": kw}
    
    # 3. Unknown
    return {"status": "unknown", "value": "unknown"}
```

## Key design decisions

1. **Avtoteka headers are NOT restrictions** — "Сведения о залоге" is a section title in the Avtoteka preview. The actual status would be "Залог не найден" or "Залог обнаружен" AFTER the header. Since mobile detail pages show only section titles (not the actual Avtoteka report content), we cannot determine restriction status from these headers alone.

2. **Only explicit phrases count** — "юридически чист" in seller comments is a strong clear signal. "без ограничений" in the legal field is the primary clear signal.

3. **Unknown does NOT block** — for Telegram v1 market labeling, unknown legal status is a warning but cards still send. Only confirmed restrictions (hard-stop) block.

## Integration

- `telegram_audit.py` — fallback when `card.legal_restrictions == "unknown"`:
  ```python
  if legal == "unknown":
      raw = card.get("raw_text", "") + " " + card.get("mobile_detail_raw_text", "")
      lr = parse_legal(raw)
      if lr["status"] == "clear":
          legal = "Без ограничений"
      elif lr["status"] == "restricted":
          legal = lr["value"]  # → reasons_reject
  ```
- `mobile_first_page_sampler.py` — existing `parse_mobile_specs()` handles "Без ограничений" from structured specs; legal_parser handles fallback from raw_text

## Results

After legal_parser integration on 16 candidates:
- **12 clear** ("Без ограничений" from specs or raw_text)
- **4 unknown** (no Avtoteka section in raw_text — too short/cut off)
- **0 restricted** (no actual restrictions found)

All 16 cards proceed to send_ready (unknown legal = warning but not block).
