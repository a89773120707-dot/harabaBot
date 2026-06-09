"""check_server_session.py — Проверка сессии Haraba на сервере."""
import sys
from pathlib import Path
from session_manager import check_session_status

def main():
    status = check_session_status()
    print(f"Session status: {status}")
    if status == "VALID":
        print("✅ Session is valid. Ready to run.")
        return 0
    else:
        print("❌ Session is invalid. Please re-login.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
