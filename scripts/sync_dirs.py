"""
Automated directory synchronization utility.
Mirrors the project root to sibling directories under ~/Downloads.
Paths are derived from the script's own location — no hard-coded usernames.
"""
import os
import shutil
from pathlib import Path

# Derive default source from script location
SRC_DIR = Path(os.getenv("SYNC_SRC_DIR", str(Path(__file__).resolve().parent.parent)))

# Target directories taken from argv or environment variable
import sys
if len(sys.argv) > 1:
    TARGET_DIRS = [Path(p) for p in sys.argv[1:]]
elif os.getenv("SYNC_TARGET_DIRS"):
    TARGET_DIRS = [Path(p.strip()) for p in os.getenv("SYNC_TARGET_DIRS").split(",") if p.strip()]
else:
    TARGET_DIRS = []

EXCLUDE_DIRS = {"venv", "__pycache__", ".pytest_cache", ".git"}
EXCLUDE_FILES = {"test_doc_automation.db"}


def sync():
    if not SRC_DIR.exists():
        print(f"Source directory '{SRC_DIR}' does not exist.")
        return

    for target in TARGET_DIRS:
        target.mkdir(parents=True, exist_ok=True)
        print(f"Syncing {SRC_DIR} -> {target}...")

        for root, dirs, files in os.walk(SRC_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            rel_path = Path(root).relative_to(SRC_DIR)
            target_root = target / rel_path
            target_root.mkdir(parents=True, exist_ok=True)

            for file in files:
                if file in EXCLUDE_FILES or file.endswith(".db"):
                    continue
                src_file = Path(root) / file
                target_file = target_root / file
                shutil.copy2(src_file, target_file)

        print(f"[OK] Sync complete for {target}")


if __name__ == "__main__":
    sync()
