# inbox_watcher.py (filesystem_watcher)
"""
File System Watcher — Drop Folder Monitor (Perception Layer)
================================================================
Watches the ai-employee/Inbox/ folder for new file drops.
When a new file is detected, it creates a metadata .md file and
triggers downstream processing.

Part of the Perception → Reasoning → Action architecture:
- Perception: Polls filesystem for new/changed files via hash detection
- Handoff: Logs detections for task_router to classify
- Can also be used as a local drop folder for documents

Usage:
    python Agents/inbox_watcher.py              # continuous monitoring
    python Agents/inbox_watcher.py --once       # single scan, no loop
"""

import os
import sys
import time
import json
import hashlib
import shutil
from pathlib import Path
from datetime import datetime, timezone

try:
    from Agents.config import VAULT_ROOT, NEEDS_ACTION_DIR, INBOX_DIR, DRY_RUN, now_iso, now_local_iso
    from Agents.base_watcher import BaseWatcher
    from Agents.action_logger import log_action
except ImportError:
    from config import VAULT_ROOT, NEEDS_ACTION_DIR, INBOX_DIR, DRY_RUN, now_iso, now_local_iso
    from base_watcher import BaseWatcher
    from action_logger import log_action


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WATCH_LOG = VAULT_ROOT / "Agents" / "watcher_log.json"
POLL_INTERVAL_SECONDS = 5


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


# ── FileSystem Watcher ─────────────────────────────────────────────────────
class InboxWatcher(BaseWatcher):
    """
    Watches the /Inbox/ folder for new or modified files.
    Uses content hashing to detect changes between polls.
    When a new file is detected, logs the event and optionally
    creates a metadata file.
    """

    def __init__(self, vault_path: str = None, check_interval: int = POLL_INTERVAL_SECONDS):
        super().__init__(vault_path or str(VAULT_ROOT), check_interval=check_interval)
        self.inbox_dir = self.vault_path / "Inbox"
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    def check_for_updates(self) -> list:
        """
        Scan the Inbox folder and return a list of new or changed files
        since the last scan.
        """
        seen = _load_seen()
        new_items = []

        if not self.inbox_dir.exists():
            return []

        for entry in sorted(self.inbox_dir.iterdir()):
            if entry.name.startswith("."):
                continue  # skip hidden files like .gitkeep
            if not entry.is_file():
                continue

            fhash = _file_hash(entry)
            key = entry.name

            if key not in seen or seen[key]["hash"] != fhash:
                record = {
                    "title": entry.stem,
                    "body": f"New file dropped: {entry.name} ({entry.stat().st_size} bytes)",
                    "source": f"filesystem:{entry.name}",
                    "priority": "normal",
                    "type": "file_drop",
                    "file": entry.name,
                    "path": str(entry),
                    "hash": fhash,
                    "size": entry.stat().st_size,
                    "status": "new" if key not in seen else "modified",
                }
                new_items.append(record)
                seen[key] = {"hash": fhash, "detected_at": datetime.now(timezone.utc).isoformat()}

        _save_seen(seen)
        return new_items

    def create_action_file(self, item) -> Path:
        """
        Create a metadata .md file for the dropped file.
        The original file stays in /Inbox/ for task_router to process.
        """
        source_path = Path(item["path"])
        original_name = item.get("file", "unknown")
        status = item.get("status", "new")

        log_action(
            action_type="file_detected",
            actor="inbox_watcher",
            target=original_name,
            description=f"{status.upper()}: {original_name} ({item.get('size', 0)} bytes)",
            status="success",
        )

        # Return the original file path — task_router will handle routing
        return source_path


# ── Standalone entry point (backward compat) ──────────────────────────────
def scan_inbox() -> list[dict]:
    """Legacy function: scan and return new/changed files."""
    watcher = InboxWatcher()
    return watcher.check_for_updates()


def run_once() -> None:
    """Execute a single scan and print results."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Scanning Inbox: {INBOX_DIR}")
    watcher = InboxWatcher()
    items = watcher.check_for_updates()
    if items:
        for item in items:
            print(f"  📥  {item['status'].upper()}: {item['file']}")
            watcher.create_action_file(item)
    else:
        print("  ✅  No new or changed files in Inbox.")


def watch_loop() -> None:
    """Continuously poll the Inbox folder."""
    watcher = InboxWatcher()
    watcher.run()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        watch_loop()
