# GitHub Cleanup Report

**Date:** 2026-06-09
**Total Files Scanned:** 185

---

## 🗑️ DELETE (Trash/One-offs)
*These files are temporary checks, old tests, or unused scripts.*

### Diagnostics & Debug
- `diag_auto_ru_exact.py` ... `diag_transmission.py` (All `diag_*.py` except needed ones)
- `debug_audit.py` ... `debug_stable_key.py` (All `debug_*.py`)
- `check_audit.py` ... `check_yaml.py` (All `check_*.py` EXCEPT `check_server_session.py`)
- `analyze_legal.py` ... `analyze_legal2.py`
- `test_rp.py` ... `test_photo_scrape.py` (All random `test_*.py`)

### Old Versions & Duplicates
- `run_telegram_pipeline.py` (Replaced by `run_daily_pipeline.py`)
- `telegram_card_formatter_v1.py` (If exists, or logic is merged into main)
- `apply_all_searches_17.py` (One-time setup script)
- `apply_filters_8.py`, `apply_filters_9.py` (One-time setup)
- `run_saved_searches_8.py` (One-time setup)
- `run_save_one_8.py` (One-time setup)
- `delete_saved_search.py`, `delete_all_saved_searches.py` (One-time setup)
- `verify_saved_searches_8.py` (One-time setup)
- `build_full_config.py`, `calibrate_price_ranges_v2.py` (Config build scripts, result is the yaml)
- `config_loader_8.py`, `config_loader_9.py` (Merged into `config_loader.py`)

### Temporary/Random
- `fix_transmission.py`
- `fix_regions.py`
- `collect_*.py` (Data collection scripts, superseded by pipeline)

---

## 📦 ARCHIVE (Useful context, but not runtime)
*Scripts that explain HOW the system was built, or might be needed for debugging later, but aren't part of the daily run.*

- `test_block1.py` ... `test_block9_expander.py` (Pipeline construction tests)
- `auto_ru_evaluation_aggregator.py` (External tool, maybe needed later?)
- `dump_all_cards.py` (Manual inspection tool)
- `feedback_export.py` (Analytics tool - keep?)
- `login.py`, `login_wait.py` (Auth recovery tools - useful to keep on server?) -> *Decision: KEEP `login_wait.py` as `scripts/login.py`?*

---

## ✅ KEEP (Core Runtime & Config)
*The "Production" application.*

### Core Logic
- `run_daily_pipeline.py` (Main entrypoint)
- `telegram_feedback_bot.py` (Bot service)
- `telegram_sender.py` (Sending logic)
- `telegram_audit.py` (Quality control)
- `telegram_card_formatter.py` (Card design)

### Modules
- `feedback_store.py`, `dedup_store.py` (Database)
- `mobile_first_page_sampler.py` (Scraper)
- `photo_parser.py`, `region_parser.py`, `legal_parser.py` (Parsers)
- `price_scorer_v2.py`, `mileage_scorer.py`, `powertrain_scorer.py`, `equipment_scorer.py` (Scoring)
- `config_loader.py`, `model_matcher.py` (Config)
- `base.py`, `session_manager.py` (Infrastructure)

### Config & Data
- `config/*.yaml`
- `data/state.json`
- `.env` (GitIgnored)
- `results/feedback.db` (GitIgnored)

### Deployment Files
- `requirements.txt`
- `check_server_session.py`
- `deploy_check.py`
- `haraba_bot.service`
- `run_pipeline.sh`
- `CRON_SETUP.md`
- `PRE_DEPLOY_PLAN.md`
