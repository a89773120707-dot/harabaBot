---
name: telegram-candidates-audit
description: Pre-send audit pipeline for Telegram candidates — 13-block checks (region, legal, transmission, drive, completeness, score) splitting candidates into send_ready / hold / do_not_send
source: auto-skill
extracted_at: '2026-06-08T21:38:00.000Z'
---

## Problem

Before sending scored cards to Telegram, each candidate must pass a multi-block audit to prevent cars with critical issues from being sent: wrong region, legal restrictions, manual transmission, incomplete data, or inflated scores without justification.

## Architecture

```
mobile_first_page_sample.json (30 fresh cards with specs)
    ↓
load_mobile_sample() + normalize_card() + score_card()
    ↓
Filter: only good_candidate / watch / excellent (16 candidates)
    ↓
15.3  Region audit → allowed / warning_unknown / reject_wrong_region
15.4  Legal audit → clean / warning_unknown / reject
15.5  Transmission audit → not manual
15.6  Drive audit → must be awd
15.7  Completeness → engine/transmission/drive/price/mileage present
15.8  Score explanation → bonus_reasons or penalty_reasons exist
15.9  Suspicious high score → score ≥ 90 must have real justification
    ↓
Classification: send_ready / hold_manual_review / do_not_send
    ↓
telegram_preview_audited.md (send_ready only)
telegram_hold_review.md (hold cards with reasons)
telegram_candidates_audit_report.yaml (final QA)
```

## Audit checks

### 15.3 — Region audit

**Allowed regions:**
```
Москва, Московская область, Москва и МО
Ярославль, Ярославская область, Ярославская обл.
Тверь, Тверская область, Тверская обл.
Владимир, Владимирская область, Владимирская обл.
Калуга, Калужская область, Калужская обл.
Рязань, Рязанская область, Рязанская обл.
Тула, Тульская область, Тульская обл.
```

| Value | Status | Action |
|-------|--------|--------|
| Match in allowed list | allowed | ✅ pass |
| "unknown" | warning_unknown | ⚠️ hold for review |
| Not in allowed list | reject_wrong_region | ❌ do_not_send |

### 15.4 — Legal restrictions audit

**Critical fix:** "Ограничение на регистрацию" is just a **section header** in the Avtotechka panel, NOT an actual restriction. The value is on the next line.

**Correct parsing:**
```python
for i, line in enumerate(lines):
    if "Ограничение на регистрацию" in line:
        next_line = lines[i+1].strip().lower()
        if any(kw in next_line for kw in ["есть", "да", "запрет", "арест", "огранич"]):
            return {"value": "Есть ограничение", "source": "mobile_detail"}
        else:
            return {"value": "Без ограничений", "source": "mobile_detail"}
```

**Also critical:** `check_legal_restrictions()` must handle "Без ограничений" correctly:
```python
def check_legal_restrictions(legal: str) -> tuple:
    if legal == "unknown":
        return False, "warning_unknown"
    if "без ограничен" in legal.lower():  # ← MUST check this FIRST
        return True, "clean"
    for kw in LEGAL_REJECT_KEYWORDS:
        if kw.lower() in legal.lower():
            return False, "reject"
    return True, "clean"
```

**Without the "без ограничен" check**, the keyword "огранич" in "Без ограничений" matches LEGAL_REJECT_KEYWORDS and incorrectly rejects all clean cards.

| Value | Status | Action |
|-------|--------|--------|
| "Без ограничений" | clean | ✅ pass |
| "Есть ограничение" | reject | ❌ do_not_send |
| "unknown" | warning_unknown | ⚠️ hold for review |

### 15.5 — Transmission audit

| Value | Action |
|-------|--------|
| automatic / cvt / dsg | ✅ pass |
| manual | ❌ do_not_send |
| unknown | ⚠️ hold |

### 15.6 — Drive audit

| Value | Action |
|-------|--------|
| awd / 4wd / 4matic / quattro / xdrive | ✅ pass |
| fwd / rwd | ❌ do_not_send |
| unknown | ⚠️ hold |

### 15.7 — Completeness

Required fields (must NOT be "unknown" or 0): engine, transmission, drive, price, mileage.

Missing any → ⚠️ hold.

### 15.8 — Score explanation

Must have `bonus_reasons` or `penalty_reasons`. Empty → ⚠️ hold.

### 15.9 — Suspicious high score

If score ≥ 90, verify price_category is not "reject" and price score is not < -20. If violated → ⚠️ hold.

## Classification rules

```
send_ready:
  - region allowed (or unknown → hold)
  - no legal restrictions
  - transmission not manual
  - drive is awd
  - all required fields present
  - score explanation exists

hold_manual_review:
  - region unknown
  - legal unknown
  - missing non-critical field
  - suspicious high score

do_not_send:
  - legal restrictions found
  - wrong region
  - manual transmission
  - not awd
```

## Command

```bash
python telegram_audit.py
```

## Output files

| File | Purpose |
|------|---------|
| `results/telegram_candidates_audited.json` | All 16 candidates with audit status, reasons, action |
| `results/telegram_preview_audited.md` | Telegram preview for send_ready cards only |
| `results/telegram_hold_review.md` | Hold cards with reasons (region, legal, etc.) |
| `results/telegram_candidates_audit_report.yaml` | QA summary: checks pass/fail/warn counts, telegram_sender_ready |

## Typical results

| Metric | Example |
|--------|---------|
| total_candidates | 16 |
| send_ready | 6 |
| hold_manual_review | 10 |
| do_not_send | 0 |

## Decision

`telegram_sender_ready: true` when:
- `send_ready >= 1`
- No legal restrictions in send_ready
- No manual in send_ready
- Preview audited created

## Key pitfalls

1. **"Ограничение на регистрацию" is a header, not a value** — the actual status is on the next line
2. **"Без ограничений" contains "огранич"** — check for "без ограничен" BEFORE matching reject keywords
3. **normalize_card must pass region** — add `"region": raw.get("region", "unknown")` to return dict
4. **load_mobile_sample must transform Russian values** — transmission "Автомат" → "automatic", drive "Полный" → "awd"
