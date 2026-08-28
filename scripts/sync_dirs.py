"""
Automated directory synchronization utility.
Mirrors C:/Users/Isra/doc-automation-saas to Downloads/doc-automation-saas and Downloads/stage2-projet.
"""
import os
import shutil
from pathlib import Path

SRC_DIR = Path("C:/Users/Isra/doc-automation-saas")
TARGET_DIRS = [
    Path("C:/Users/Isra/Downloads/doc-automation-saas"),
    Path("C:/Users/Isra/Downloads/stage2-projet"),
]

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
