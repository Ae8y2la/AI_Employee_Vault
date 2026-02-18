"""
Inbox Watcher Agent — File System Monitor
==========================================
Watches the ai-employee/Inbox/ folder for new .md files.
When a new file is detected, it logs the event and (optionally)
triggers downstream processing (e.g., task_router).

Bronze Tier: Functional file-system watcher. No full classification loop.

Usage:
    python Agents/inbox_watcher.py
    (or)  python Agents/inbox_watcher.py --once   # single scan, no loop
"""

import os
import sys
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VAULT_ROOT = Path(__file__).resolve().parent.parent          # ai-employee/
INBOX_DIR = VAULT_ROOT / "Inbox"
WATCH_LOG = VAULT_ROOT / "Agents" / "watcher_log.json"
POLL_INTERVAL_SECONDS = 5                                     # seconds between scans


def _file_hash(path: Path) -> str:
    """Return a short content hash for change detection."""
    return hashlib.md5(path.read_bytes()).hexdigest()


def _load_seen() -> dict:
    """Load the set of previously seen files from the log."""
    if WATCH_LOG.exists():
        try:
            return json.loads(WATCH_LOG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_seen(seen: dict) -> None:
    """Persist the seen-files record."""
    WATCH_LOG.write_text(json.dumps(seen, indent=2), encoding="utf-8")


def scan_inbox() -> list[dict]:
    """
    Scan the Inbox folder and return a list of *new or changed* files
    since the last scan.
    """
    seen = _load_seen()
    new_items = []

    for entry in sorted(INBOX_DIR.iterdir()):
        if entry.name.startswith("."):
            continue  # skip hidden files like .gitkeep
        if not entry.is_file():
            continue

        fhash = _file_hash(entry)
        key = entry.name

        if key not in seen or seen[key]["hash"] != fhash:
            record = {
                "file": entry.name,
                "path": str(entry),
                "hash": fhash,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "status": "new" if key not in seen else "modified",
            }
            new_items.append(record)
            seen[key] = {"hash": fhash, "detected_at": record["detected_at"]}

    _save_seen(seen)
    return new_items


def run_once() -> None:
    """Execute a single scan and print results."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Scanning Inbox: {INBOX_DIR}")
    items = scan_inbox()
    if items:
        for item in items:
            print(f"  📥  {item['status'].upper()}: {item['file']}")
    else:
        print("  ✅  No new or changed files in Inbox.")


def watch_loop() -> None:
    """Continuously poll the Inbox folder."""
    print(f"👁️  Inbox Watcher started — monitoring {INBOX_DIR}")
    print(f"    Poll interval: {POLL_INTERVAL_SECONDS}s  |  Press Ctrl+C to stop\n")
    try:
        while True:
            run_once()
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\n🛑  Watcher stopped by user.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        watch_loop()
