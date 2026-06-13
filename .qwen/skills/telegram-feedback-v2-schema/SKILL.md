---
name: telegram-feedback-v2-schema
description: Feedback database schema v2 with 30+ fields, RIS tables (reaction_reasons, reaction_details), and review/think/skip reaction model
source: auto-skill
extracted_at: '2026-06-09T16:50:00.000Z'
---

# Telegram Feedback V2 Schema

## Overview

Extended feedback table to support multi-recipient system with full card context preservation. Each reaction stores complete snapshot of the card state at time of reaction.

**Feedback V2 (2026-06-11):** Reaction model changed from like/dislike/fire to review/think/skip with reason codes stored in separate tables.

## Schema

### feedback table

```sql
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT,
    model_id TEXT,
    title TEXT,
    price INTEGER,
    mileage INTEGER,
    engine TEXT,
    transmission TEXT,
    drive TEXT,
    region TEXT,
    owners TEXT,
    legal_restrictions TEXT,
    autoteka_status TEXT,
    score INTEGER,
    telegram_status TEXT,
    price_status TEXT,
    price_score INTEGER,
    mileage_score INTEGER,
    engine_score INTEGER,
    transmission_score INTEGER,
    equipment_score INTEGER,
    photo_url TEXT,
    photo_count INTEGER,
    full_location TEXT,
    action TEXT,          -- review / think / skip (was: buy/watch/skip/like/dislike/fire)
    comment TEXT,
    telegram_chat_id TEXT,
    telegram_user_id TEXT,
    telegram_username TEXT,
    reviewer_role TEXT,
    created_at TEXT
)
```

### reaction_reasons table (RIS)

Reference table mapping reason codes to reaction types:

```sql
CREATE TABLE reaction_reasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reaction_type TEXT NOT NULL,   -- review/think/skip
    reason_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL
);
```

27 reasons total:
- **review** (9): good_price, good_condition, low_mileage, few_owners, good_history, good_equipment, liquid_model, good_region, review_other
- **think** (10): high_price, high_mileage, many_owners, bad_color, poor_equipment, history_questions, bad_modification, bad_region, need_more_info, think_other
- **skip** (8): not_my_model, not_my_segment, too_expensive, too_mileage, bad_condition, legal_risk, illiquid, skip_other

### reaction_details table (RIS)

Links reasons to specific feedback entries:

```sql
CREATE TABLE reaction_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_id INTEGER NOT NULL,
    reason_code TEXT,  -- NULL if user skipped
    created_at TEXT,
    FOREIGN KEY (feedback_id) REFERENCES feedback(id)
);
```

### learning_rules table (RIS)

```sql
CREATE TABLE learning_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type TEXT NOT NULL,
    target TEXT NOT NULL,
    condition_json TEXT,
    effect_value INTEGER,
    status TEXT DEFAULT 'pending',  -- pending/active/rejected/disabled
    source_reactions INTEGER,
    created_at TEXT,
    approved_at TEXT,
    approved_by TEXT
);
```

## Reaction model migration

**Old → New mapping:**
- like → review
- fire → review
- dislike → skip
- watch → think
- buy → review

**Historical data preserved** — old actions are updated in-place, never deleted.

## Analytics

### Config Report (per model)

```sql
SELECT f.model_id,
       COUNT(*) as reaction_count,
       SUM(CASE WHEN f.action = 'review' THEN 1 ELSE 0 END) as review_count,
       SUM(CASE WHEN f.action = 'think' THEN 1 ELSE 0 END) as think_count,
       SUM(CASE WHEN f.action = 'skip' THEN 1 ELSE 0 END) as skip_count
FROM feedback f
WHERE f.model_id IS NOT NULL
GROUP BY f.model_id
```

### Reasons per model

```sql
SELECT rr.reaction_type, rr.title, COUNT(*) as cnt
FROM reaction_details rd
JOIN reaction_reasons rr ON rd.reason_code = rr.reason_code
JOIN feedback f ON rd.feedback_id = f.id
WHERE f.model_id = ?
GROUP BY rr.reason_code
```

## Key Rules

1. **action** field uses review/think/skip (not like/dislike/fire)
2. **reason_code** is optional (NULL if user skipped reason selection)
3. **reviewer_role** and **telegram_chat_id** are required (never NULL)
4. **learning_rules** start as `pending` — never auto-apply
5. Migration must use `CREATE TABLE IF NOT EXISTS` — never break existing DB
