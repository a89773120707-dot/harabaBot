# Secret File Audit

## FILE AUDIT

| FILE | PATH | SIZE | STATUS |
|------|------|------|--------|
| `.env` | `.env` | 94 bytes | ✅ EXISTS |
| `feedback.db` | `results/feedback.db` | 45,056 bytes | ✅ EXISTS |
| `state.json` | `data/state.json` | 707,792 bytes | ✅ EXISTS (Main) |
| `state_backup.json` | `data/state_backup.json` | 4,736 bytes | ✅ EXISTS (Old) |

## SESSION FILE USED

The code uses `data/state.json` as defined in `base.py`:
`STATE_PATH = BASE_DIR / "data" / "state.json"`

This file is used by:
- `session_manager.py`
- `check_server_session.py`
- `mobile_first_page_sampler.py` (indirectly)

## COPY COMMANDS

```bash
ssh haraba@31.177.110.7 "mkdir -p ~/harabaBot/results ~/harabaBot/data"

scp .env haraba@31.177.110.7:~/harabaBot/
scp results/feedback.db haraba@31.177.110.7:~/harabaBot/results/
scp data/state.json haraba@31.177.110.7:~/harabaBot/data/
```
