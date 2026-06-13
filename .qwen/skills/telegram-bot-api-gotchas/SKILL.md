---
name: telegram-bot-api-gotchas
description: Common pitfalls when working with python-telegram-bot v20+ API — edit_message_text vs reply_text, context passing, and callback handler patterns
source: auto-skill
extracted_at: '2026-06-11T18:28:00.660Z'
---

# Telegram Bot API Gotchas (python-telegram-bot v20+)

## CRITICAL: edit_message_text does NOT accept reply_to_message_id

`edit_message_text()` CANNOT use `reply_to_message_id`. Only `reply_text()` and `send_message()` support it.

**WRONG — will crash with `TypeError: edit_message_text() got an unexpected keyword argument 'reply_to_message_id'`:**
```python
await query.edit_message_text(
    "Text here",
    reply_to_message_id=query.message.message_id,  # ❌ CRASH
)
```

**RIGHT — split into edit + reply:**
```python
await query.edit_message_text("✅ Cause saved.")
await query.message.reply_text(
    "✍️ Write a comment:",
    reply_to_message_id=query.message.message_id,  # ✅ OK
)
```

## Helper functions need explicit context parameter

Inside `main()`, handler functions receive `context: ContextTypes.DEFAULT_TYPE`, but helper functions defined inside `main()` CANNOT access `context` from closure if they're called before `context` is in scope, or if the reference is stale.

**WRONG:**
```python
def _save_feedback(chat_id, pf):
    user = context.bot.get_chat(chat_id)  # ❌ NameError: context not defined
```

**RIGHT — pass context explicitly:**
```python
def _save_feedback(chat_id, pf, ctx):
    user = ctx.bot.get_chat(chat_id)  # ✅ OK

# Call:
_save_feedback(chat_id, pf, context)
```

## context.bot.get_chat() is async in v20 — use update.effective_user

In python-telegram-bot v20, `context.bot.get_chat(chat_id)` returns a **coroutine**, not a Chat object. Calling it synchronously gives:

```
AttributeError: 'coroutine' object has no attribute 'id'
```

**WRONG — async method called synchronously:**
```python
def _save_feedback(chat_id, pf, context):
    user = context.bot.get_chat(chat_id)  # ❌ Returns coroutine!
    user_id = user.id  # AttributeError
```

**RIGHT — use update.effective_user (synchronous):**
```python
def _save_feedback(chat_id, pf, user):
    # user is already a User object from update.effective_user
    user_id = user.id  # ✅ OK

# In handler:
_save_feedback(chat_id, pf, update.effective_user)
```

## Callback handler registration order matters

When using `CallbackQueryHandler` with pattern filters, register more specific patterns FIRST:
```python
# More specific patterns first
app.add_handler(CallbackQueryHandler(reason_handler, pattern="^reason:"))
app.add_handler(CallbackQueryHandler(button_handler))  # Generic, catches rest
```

If the generic handler is registered first, it may consume callbacks before the specific one sees them.

## Debugging callback errors

When a callback button shows no response in Telegram:
1. Check `journalctl -u haraba-feedback-bot` on VPS for stack traces
2. Wrap handler in try/except and show error in Telegram:
   ```python
   try:
       # handler logic
   except Exception as e:
       log.error(f"Handler ERROR: {e}", exc_info=True)
       await query.edit_message_text(f"❌ Error: {e}")
   ```
3. Check that `callback_data` patterns match what the button sends
4. Verify imports inside handlers (they may differ from module-level imports)
