"""deploy_check.py — Финальная проверка перед запуском на сервере."""
import os
import sys
from pathlib import Path

def check_file(path, required=True):
    exists = Path(path).exists()
    status = "✅" if exists else ("❌" if required else "⚠️")
    print(f"{status} {path}")
    if required and not exists:
        return False
    return True

def main():
    print("=== DEPLOY CHECKLIST ===\n")
    all_ok = True

    # Core files
    all_ok &= check_file("telegram_feedback_bot.py")
    all_ok &= check_file("run_daily_pipeline.py")
    all_ok &= check_file("telegram_sender.py")
    
    # Configs
    all_ok &= check_file("config/awd_liquid_full_config.yaml")
    all_ok &= check_file(".env")
    
    # Data
    all_ok &= check_file("data/state.json")
    all_ok &= check_file("results/feedback.db")
    
    # Server scripts
    all_ok &= check_file("haraba_bot.service")
    all_ok &= check_file("run_pipeline.sh")
    all_ok &= check_file("requirements.txt")
    all_ok &= check_file("check_server_session.py")

    print("\n=== RESULT ===")
    if all_ok:
        print("✅ All checks passed. Ready for deployment.")
        return 0
    else:
        print("❌ Some checks failed. Fix before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
