---
name: ris-reaction-intelligence-system
description: Pattern for adding reason codes and learning rules to an existing reaction/feedback system (review/think/skip model)
source: auto-skill
extracted_at: '2026-06-11T17:45:00.000Z'
---

## When to use

When you have an existing feedback/reaction system and want to:
- Collect **reasons** for reactions (not just the reaction itself)
- Analyze patterns across models, regions, etc.
- Generate learning rules that improve scoring
- Apply rules only after owner confirmation

## Reaction model

**Current model** (Feedback V2):
- 👀 **review** — карточка заинтересовала (was like/fire)
- 🤔 **think** — потенциально интересная, но есть сомнения (new)
- ⏭ **skip** — неинтересна (was dislike)

**Migration mapping**: like→review, fire→review, dislike→skip, watch→think, buy→review

**Historical data preserved** — old reactions are updated in-place, never deleted.

## Architecture

### Database schema (safe migration)

All tables use `CREATE TABLE IF NOT EXISTS` — never break existing DB.

```sql
-- 1. Reference table: reason codes per reaction type
CREATE TABLE IF NOT EXISTS reaction_reasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reaction_type TEXT NOT NULL,   -- review/think/skip
    reason_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL
);

-- 2. Link table: which reason was chosen for each feedback
CREATE TABLE IF NOT EXISTS reaction_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_id INTEGER NOT NULL,  -- FK to feedback.id
    reason_code TEXT,              -- NULL if user skipped
    created_at TEXT,
    FOREIGN KEY (feedback_id) REFERENCES feedback(id)
);

-- 3. Rules table: generated rules, pending owner approval
CREATE TABLE IF NOT EXISTS learning_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type TEXT NOT NULL,       -- model_bonus, region_bonus, etc.
    target TEXT NOT NULL,          -- model_id, region, etc.
    condition_json TEXT,           -- thresholds that triggered this
    effect_value INTEGER,          -- score adjustment (-5 to +5)
    status TEXT DEFAULT 'pending', -- pending/active/rejected/disabled
    source_reactions INTEGER,      -- how many reactions support this
    created_at TEXT,
    approved_at TEXT,
    approved_by TEXT
);
```

### Reason codes per reaction type

**review** (9): good_price, good_condition, low_mileage, few_owners, good_history, good_equipment, liquid_model, good_region, review_other

**think** (10): high_price, high_mileage, many_owners, bad_color, poor_equipment, history_questions, bad_modification, bad_region, need_more_info, think_other

**skip** (8): not_my_model, not_my_segment, too_expensive, too_mileage, bad_condition, legal_risk, illiquid, skip_other

Note: "other" codes are prefixed (review_other, think_other, skip_other) to satisfy UNIQUE constraint on reason_code.

### UI Flow (inline buttons)

```
User sees card with [👀 Посмотреть] [🤔 Подумать] [⏭ Скип]
  ↓ clicks 👀
Bot shows reason buttons:
  [💰 Хорошая цена] [🚗 Хорошее состояние] [📉 Небольшой пробег] ...
  [⏭ Без причины]
  ↓ clicks reason
Bot: edits original message to "✅ Причина записана."
Bot: sends NEW message "✍️ Напиши комментарий (или '-' если без):"
  ↓ types comment
Bot saves: feedback(action='review') + reason_code linked to feedback.id
```

### ⚠️ Critical bug: edit_message_text does NOT accept reply_to_message_id

`CallbackQuery.edit_message_text()` does NOT support `reply_to_message_id` parameter.

**WRONG** (crashes):
```python
await query.edit_message_text(
    "✅ Причина записана.\n\nНапиши комментарий:",
    reply_to_message_id=query.message.message_id,  # ❌ TypeError!
)
```

**CORRECT** — split into two actions:
```python
# 1. Edit the original message (no reply_to_message_id)
await query.edit_message_text("✅ Причина записана.")

# 2. Send a NEW message as a reply
await query.message.reply_text(
    "✍️ Напиши комментарий (или '-' если без):",
    reply_to_message_id=query.message.message_id,
)
```

### Data flow

1. User clicks reaction (review/think/skip) → `pending_feedback[chat_id] = {...}`
2. Show `reason_keyboard(action)` inline buttons
3. User selects reason → `pending_reason[chat_id] = reason_code`
4. User writes comment → `save_feedback()` → get `MAX(id) FROM feedback` → `save_reaction_detail(feedback_id, reason_code)`
5. If user skipped reason → `reason_code = NULL`

### Rule generation thresholds (soft)

For low data (3-50 reactions):
- **Positive** (review): review_count >= 3 AND review >= skip * 2 AND total reactions >= 4
- **Negative** (skip): skip_count >= 3 AND skip >= review * 2 AND total reactions >= 4

All rules created as `status=pending` — never auto-apply.

### Learning score caps

- Single rule effect: -5 to +5
- Sum total cap: -10 to +10
- Formula: `final_score = base_score + min(max(learning_score, -10), 10)`

### Safety rules

1. **NEVER** auto-apply rules — owner must confirm
2. **ALWAYS** `CREATE TABLE IF NOT EXISTS` — never break existing DB
3. **ALWAYS** check column existence before `ALTER TABLE`
4. Analytics before scoring — show data first, affect score last
5. Threshold gating: < 50 reactions = test mode only

## Analytics (Stage 2)

Three analytics functions in `ris_analytics.py` (read-only SQL):

### learning_report
- Total reactions by type (review/think/skip)
- Top models by reaction count
- Top reasons overall
- Count of reactions without reason

### learning_reasons
- Reasons grouped by reaction type (review, think, skip)
- Shows top reasons for each group separately

### config_report
- Per-model breakdown: review/think/skip counts
- Reasons per model with reaction type icons
- Sorted by total reaction count (descending)

All accessed via admin_bot 🧠 Обучение menu.

## Admin bot integration

Add 🧠 Обучение button to `main_menu_keyboard()` in `keyboards.py`. Register handler with pattern `^(learning_|config_)` in `admin_bot.py`. The `menu_learning` button must be explicitly handled in `menu.py` by delegating to `learning_callback_handler`.

## Implementation order

1. Schema migration (tables)
2. Reason UI (inline buttons)
3. Learning dataset service
4. Model analytics service
5. Reason analytics service
6. Rules table
7. Rule generator
8. Admin panel (🧠 Learning section)
9. Learning report
10. Scoring integration (LAST)
