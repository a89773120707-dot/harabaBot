"""
move_files.py — Скрипт для перемещения файлов мусора в _trash и _archive.
"""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
TRASH = ROOT / "_trash"
ARCHIVE = ROOT / "_archive"

# Ensure dirs exist
TRASH.mkdir(exist_ok=True)
ARCHIVE.mkdir(exist_ok=True)

moved_files = []

def move_file(filename, category, folder):
    src = ROOT / filename
    if src.exists():
        dest = folder / filename
        shutil.move(str(src), str(dest))
        moved_files.append(f"[{category}] {filename}")
        return True
    return False

# DELETE -> _trash
delete_patterns = [
    "analyze_legal*.py",
    "apply_*.py",
    "auto_ru_evaluation_*.py",
    "build_full_config.py",
    "calibrate_price_ranges_v2.py",
    "check_*.py",
    "cleanup_duplicates.py",
    "collect_*.py",
    "connect_9_searches*.py",
    "data_audit.py",
    "debug_*.py",
    "deep_data_audit.py",
    "delete_*.py",
    "diag_*.py",
    "dry_run_margin_8.py",
    "dump_*.py",
    "enrich_seller_descriptions.py",
    "extract_cards_playwright.py",
    "extract_full_description.py",
    "fix_*.py",
    "generate_test_cards.py",
    "login.py",
    "parse_detail_specs.py",
    "print_final_report.py",
    "qa_check_9.py",
    "refresh_seller_descriptions.py",
    "refresh_session*.py",
    "registry_*.py",
    "reject_engine.py",
    "remove_duplicates.py",
    "reparse_regions.py",
    "resample_legal.py",
    "resave_sample.py",
    "run_saved_searches_*.py",
    "run_save_one_8.py",
    "run_telegram_pipeline.py",
    "saved_search_helper_*.py",
    "save_hyundai_yaml.py",
    "search_expander_*.py",
    "summarize_results.py",
    "update_yaml_block9.py",
    "verify_saved_searches_8.py",
    "verify_transmission*.py",
    "test_check_search_exists.py",
    "test_dedup_v2.py",
    "test_feedback_cols.py",
    "test_feedback_integrity.py",
    "test_one_car.py",
    "test_open_haraba.py",
    "test_photo_1card.py",
    "test_photo_debug.py",
    "test_photo_parser.py",
    "test_photo_scrape.py",
    "test_popup_all.py",
    "test_rp.py",
    "test_save_sportage.py",
    "find_*.py",
    "prepare_*.py"
]

# Manual list of specific files to trash based on report
specific_trash = [
    "analyze_legal.py",
    "analyze_legal2.py",
    "apply_all_searches.py",
    "apply_all_searches_17.py",
    "apply_filters_8.py",
    "apply_filters_9.py",
    "auto_ru_evaluation_aggregator.py",
    "auto_ru_evaluation_parser.py",
    "build_full_config.py",
    "calibrate_price_ranges_v2.py",
    "check_all_filters_8.py",
    "check_and_apply_all_searches.py",
    "check_audit.py",
    "check_audit2.py",
    "check_audit_result.py",
    "check_cfg.py",
    "check_config_8.py",
    "check_db.py",
    "check_db_final.py",
    "check_description_data.py",
    "check_duplicates.py",
    "check_expert_rules.py",
    "check_fb2.py",
    "check_feedback.py",
    "check_haraba_auth.py",
    "check_legal.py",
    "check_raw.py",
    "check_raw2.py",
    "check_reactions.py",
    "check_reactions_new.py",
    "check_sent.py",
    "check_session.py",
    "check_url_match.py",
    "check_yaml.py",
    "cleanup_duplicates.py",
    "clear_and_check.py",
    "collect_evaluations.py",
    "collect_evaluations_8r.py",
    "collect_grand_santa_fe.py",
    "collect_santa_fe.py",
    "connect_9_searches.py",
    "connect_9_searches_v2.py",
    "data_audit.py",
    "debug_audit.py",
    "debug_audit2.py",
    "debug_dedup_state.py",
    "debug_rp.py",
    "debug_stable_key.py",
    "deep_data_audit.py",
    "delete_all_saved_searches.py",
    "delete_saved_search.py",
    "diag_auto_ru_exact.py",
    "diag_auto_ru_search.py",
    "diag_detail_auth.py",
    "diag_detail_page.py",
    "diag_full_description.py",
    "diag_legal_filter.py",
    "diag_my_searches.py",
    "diag_my_searches2.py",
    "diag_photo_loading.py",
    "diag_regions.py",
    "diag_save_dialog.py",
    "diag_save_search.py",
    "diag_seller_description.py",
    "diag_transmission.py",
    "dry_run_margin_8.py",
    "dump_all_cards.py",
    "dump_cards_8r.py",
    "dump_cards_new_url.py",
    "enrich_seller_descriptions.py",
    "extract_cards_playwright.py",
    "extract_full_description.py",
    "find_cards_structure.py",
    "find_card_data.py",
    "find_card_full_structure.py",
    "fix_regions.py",
    "fix_review_urls.py",
    "fix_transmission.py",
    "generate_test_cards.py",
    "login.py",
    "parse_detail_specs.py",
    "pipeline_searches_check.py",
    "print_final_report.py",
    "qa_check_9.py",
    "refresh_seller_descriptions.py",
    "refresh_session.py",
    "refresh_session_mobile.py",
    "registry_8.py",
    "registry_9.py",
    "reject_engine.py",
    "remove_duplicates.py",
    "reparse_regions.py",
    "resample_legal.py",
    "resave_sample.py",
    "run_telegram_pipeline.py",
    "run_saved_searches_8.py",
    "run_saved_searches_9.py",
    "run_save_one_8.py",
    "saved_search_helper_8.py",
    "saved_search_helper_9.py",
    "save_hyundai_yaml.py",
    "search_expander_8.py",
    "search_expander_9.py",
    "summarize_results.py",
    "update_yaml_block9.py",
    "verify_saved_searches_8.py",
    "verify_transmission.py",
    "verify_transmission2.py",
    "check_feedback.py",
    "check_reactions.py",
    "check_reactions_new.py"
]

# ARCHIVE -> _archive
archive_files = [
    "test_block1.py",
    "test_block2.py",
    "test_block3.py",
    "test_block4.py",
    "test_block5.py",
    "test_block6.py",
    "test_block7.py",
    "test_block8.py",
    "test_block9.py",
    "test_block9_expander.py",
    "test_block9_loader.py",
    "test_block9_registry.py",
    "login_wait.py" # Keep for auth recovery
]

# KEEP (Specific exceptions from patterns)
keep_files = [
    "check_server_session.py",
    "test_formatter_v2.py"
]

print("=== MOVING TO TRASH ===")
for f in specific_trash:
    if f in keep_files:
        continue
    move_file(f, "TRASH", TRASH)

print("=== MOVING TO ARCHIVE ===")
for f in archive_files:
    move_file(f, "ARCHIVE", ARCHIVE)

# Save report
with open("results/files_moved_report.md", "w", encoding="utf-8") as report:
    report.write("# Files Moved Report\n\n")
    report.write("## Trash\n")
    for f in [m for m in moved_files if "TRASH" in m]:
        report.write(f"- {f.split('] ')[1]}\n")
    report.write(f"\nTotal Trash: {sum(1 for m in moved_files if 'TRASH' in m)}\n")
    
    report.write("\n## Archive\n")
    for f in [m for m in moved_files if "ARCHIVE" in m]:
        report.write(f"- {f.split('] ')[1]}\n")
    report.write(f"\nTotal Archive: {sum(1 for m in moved_files if 'ARCHIVE' in m)}\n")

print(f"\nTotal moved: {len(moved_files)}")
print("Report saved to results/files_moved_report.md")
