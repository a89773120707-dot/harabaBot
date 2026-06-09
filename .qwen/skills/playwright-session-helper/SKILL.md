---
name: playwright-session-helper
description: Create a reusable get_authenticated_page() helper for Playwright automation that manages session lifecycle with clear error messages and graceful expiry handling.
source: auto-skill
extracted_at: '2026-06-07T08:43:09.568Z'
---

## Pattern: Reusable Playwright Session Helper

When building Playwright-based automation, create a session manager module that:

### 1. Separate concerns into files

| File | Purpose |
|------|---------|
| `base.py` | Shared constants (STATE_PATH, dirs, logging) — avoid circular imports |
| `session_manager.py` | Session lifecycle functions |
| `check_session.py` | CLI: quick file-based status check |
| `refresh_session.py` | CLI: manual re-login |
| `login.py` | CLI: first-time login |

### 2. Session status check (fast, no browser)

```python
def check_session_status() -> str:
    """Returns: "VALID" | "EXPIRED" | "MISSING" — checks state.json file only."""
    if not STATE_PATH.exists(): return "MISSING"
    state = json.load(STATE_PATH)
    if not state.get("cookies") and not state.get("origins"): return "EXPIRED"
    return "VALID"
```

### 3. The main helper — get_authenticated_page()

```python
def get_authenticated_page(headless: bool = False):
    """Open browser with saved session, return (page, context, browser).
    
    Raises FileNotFoundError if state.json is missing.
    Raises ValueError if session is expired.
    Both errors include actionable next-step instructions.
    """
    status = check_session_status()
    if status == "MISSING":
        raise FileNotFoundError("state.json missing!\nRun: python login.py")
    if status == "EXPIRED":
        raise ValueError("Session expired!\nRun: python refresh_session.py")
    
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=str(STATE_PATH))
    page = context.new_page()
    return page, context, browser
```

### 4. Usage in any module

```python
from session_manager import get_authenticated_page

page, context, browser = get_authenticated_page()
try:
    page.goto("https://example.com")
    # ... do work
finally:
    browser.close()
```

### 5. Always create a test_blockN.py for each block

```python
# test_block1.py — verify the session helper works end-to-end
from session_manager import get_authenticated_page, check_session_status

status = check_session_status()
assert status == "VALID"

page, context, browser = get_authenticated_page()
try:
    page.goto("https://example.com")
    assert page.get_by_text("Expected element").count() > 0
finally:
    browser.close()
```

### Key principles

- **Check session before opening browser** — fail fast with clear message
- **Error messages include the exact command to fix** — don't make user guess
- **Return tuple, not dict** — easy to unpack: `page, ctx, browser = ...`
- **Always close browser in finally** — prevent orphan processes
- **base.py prevents circular imports** — put constants there, not in apply_filter.py
