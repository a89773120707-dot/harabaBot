---
name: telegram-feedback-v2-reactions
description: Feedback V2 reaction system with review/think/skip model, main/extra reason split, back button, and reason weights
source: auto-skill
extracted_at: '2026-06-11T23:00:00.000Z'
---

# Telegram Feedback V2 — Reaction System (Updated)

## Reaction Model

Reactions use three types instead of like/dislike/fire:

| Reaction | Emoji | Callback | Meaning |
|----------|-------|----------|---------|
| review | 👀 Посмотреть | `review:{card_id}` | Card interested the manager |
| think | 🤔 Подумать | `think:{card_id}` | Potentially interesting but with doubts |
| skip | ⏭ Скип | `skip:{card_id}` | Not interesting |

## Reason Codes (27 total)

### review (9 reasons)
`good_price`, `good_condition`, `low_mileage`, `few_owners`, `good_history`, `good_equipment`, `liquid_model`, `good_region`, `review_other`

### think (10 reasons)
`high_price`, `high_mileage`, `many_owners`, `bad_color`, `poor_equipment`, `history_questions`, `bad_modification`, `bad_region`, `need_more_info`, `think_other`

### skip (8 reasons)
`not_my_model`, `not_my_segment`, `too_expensive`, `too_mileage`, `bad_condition`, `legal_risk`, `illiquid`, `skip_other`

## UX: Reason Selection (v3 — Simplified)

Each reaction shows **4 main reasons** + **💬 Написать комментарий** button.

No "Без причина" duplicates. No "Ещё причины" toggle by default.

### Main reasons per reaction:
- **review**: good_price, low_mileage, liquid_model, good_equipment, + 💬 комментарий
- **think**: high_price, high_mileage, many_owners, poor_equipment, + 💬 комментарий
- **skip**: too_expensive, too_mileage, bad_condition, legal_risk, + 💬 комментарий

### Extra reasons (available under "💬 Написать комментарий" flow for custom reasons):
- **review**: good_condition, good_history, few_owners, good_region, review_other
- **think**: history_questions, bad_color, bad_modification, bad_region, need_more_info, think_other
- **skip**: not_my_model, not_my_segment, illiquid, skip_other

### Keyboard layout (v3):
```
💰 Хорошая цена   📉 Небольшой пробег
🔥 Ликвидная модель  ⚙ Хорошая комплектация
💬 Написать комментарий   ← opens comment input directly
```

### Navigation callbacks:
- `reason:{reason_code}` → saves reason, shows confirmation
- `reason:comment` → asks for user comment (sets pending_reason="comment")
- `reasons_main:{action}` → shows main reasons (back from extra)
- `reasons_extra:{action}` → shows extra reasons (with "⬅️ Назад" button)

### Reason Weights (stored, NOT used for scoring yet)

Each reason has a weight (1-10) for future Config Intelligence. Heavy reasons like `high_price=10` matter more than `bad_color=2`.

| Weight | Reasons |
|--------|---------|
| 10 | good_price, high_price, too_expensive |
| 9 | good_history, history_questions, legal_risk |
| 8 | low_mileage, liquid_model, high_mileage, too_mileage |
| 7 | good_condition, many_owners, bad_condition |
| 6 | need_more_info, illiquid |
| 5 | few_owners, poor_equipment, not_my_model |
| 4 | good_equipment, bad_modification, not_my_segment |
| 3 | good_region, bad_region |
| 2 | bad_color |
| 1 | review_other, think_other, skip_other |

## Click Logic

**Standard reasons** (no comment needed):
1. Click reaction (👀/🤔/⏭)
2. Click reason → "✅ Реакция сохранена" with type and reason title — done

**💬 Написать комментарий**:
1. Click reaction → see 4 reasons + 💬 button
2. Click 💬 → bot asks "Напиши комментарий:"
3. User types → feedback saved with reason_code="comment"

**Reasons requiring comment** (extra reasons):
- `need_more_info`, `review_other`, `think_other`, `skip_other`

After selecting these, bot asks for comment, then shows confirmation with reason title.

## Implementation Files

| File | Purpose |
|------|---------|
| `ris_reason_keyboard.py` | Inline buttons for reason selection |
| `ris_reason_store.py` | `needs_comment()`, `save_reaction_detail()`, `get_last_feedback_id()` |
| `ris_analytics.py` | `get_learning_report()`, `get_learning_reasons()`, `get_config_report()` |
| `telegram_feedback_bot.py` | `reason_handler`, `_save_feedback_for_chat`, `_get_reason_title` |
| `telegram_sender.py` | `build_inline_keyboard()` with review/think/skip buttons |

## Database Tables

### reaction_reasons
```sql
CREATE TABLE reaction_reasons (
    id INTEGER PRIMARY KEY,
    reaction_type TEXT NOT NULL,  -- review/think/skip
    reason_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL
);
```

### reaction_details
```sql
CREATE TABLE reaction_details (
    id INTEGER PRIMARY KEY,
    feedback_id INTEGER NOT NULL,  -- FK to feedback.id
    reason_code TEXT,
    created_at TEXT
);
```

### learning_rules
```sql
CREATE TABLE learning_rules (
    id INTEGER PRIMARY KEY,
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

## Key Functions

```python
# ris_reason_store.py
def needs_comment(reason_code: str) -> bool
def save_reaction_detail(feedback_id: int, reason_code: str | None) -> None
def get_last_feedback_id() -> int

# ris_analytics.py
def get_learning_report() -> dict  # total, by_type, top_models, top_reasons
def get_learning_reasons() -> dict  # reasons grouped by review/think/skip
def get_config_report() -> dict  # per-model reactions with reasons
```

## Reaction Prompts

Each reaction type has a specific prompt shown when reasons are displayed:

| Reaction | Prompt |
|----------|--------|
| review | "👀 Посмотреть\n\nЧто понравилось?" |
| think | "🤔 Подумать\n\nЧто мешает принять решение?" |
| skip | "⏭ Скип\n\nПочему пропускаем?" |

These are defined in `REACTION_PROMPTS` in `ris_reason_keyboard.py`.

## Migration

Existing reactions are migrated:
- `like` → `review`
- `fire` → `review`
- `dislike` → `skip`
- `watch` → `think`
- `buy` → `review`

Historical data is preserved, not deleted.

## Known Issues & Troubleshooting

### ImportError: cannot import name 'needs_comment'

**Symptom:** Manager clicks reaction + reason → nothing happens, log shows:
```
ImportError: cannot import name 'needs_comment' from 'ris_reason_store'
  File "telegram_feedback_bot.py", line 358, in reason_handler
    from ris_reason_store import needs_comment, save_reaction_detail, get_last_feedback_id
```

**Root cause:** `needs_comment()` function and `REASONS_NEED_COMMENT` set exist locally but were not committed/deployed to VPS.

**Fix:** 
1. Verify local file has the function: `grep -n 'def needs_comment' ris_reason_store.py`
2. Commit and push: `git add ris_reason_store.py && git commit -m "Add needs_comment" && git push`
3. On VPS: `git reset --hard origin/main && sudo systemctl restart haraba-feedback-bot`
4. Test: click 👀 → reason → verify reaction_details record

**Prevention:** After any local changes to `ris_reason_store.py`, verify all functions are committed before expecting them to work on VPS. Run: `git diff ris_reason_store.py` to see uncommitted changes.

## Important Notes

1. `get_last_feedback_id()` returns `row[0]` (tuple index), NOT `row["max_id"]` — connection doesn't use `row_factory=sqlite3.Row`
2. `edit_message_text()` does NOT accept `reply_to_message_id` — use `query.message.reply_text()` for new messages
3. Deploy scripts with passwords must be deleted immediately after use
4. `ADMIN_BOT_TOKEN` must be added to VPS `.env` separately — never commit secrets
5. `reason:comment` is a special callback that opens comment input directly (sets `pending_reason="comment"`)
6. Local and VPS databases can have different `telegram_users` statuses — always sync before testing sender
7. The "comment" reason_code is stored as a string literal `"comment"` in reaction_details when user clicks 💬 button
