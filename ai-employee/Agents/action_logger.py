"""
Action Logger — Structured JSON Logging
=========================================
Logs all AI actions with timestamps, type, actor, target, and approval status.
Writes daily log files to /Logs/YYYY-MM-DD.json.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from Agents.config import LOGS_DIR, now_iso
except ImportError:
    from config import LOGS_DIR, now_iso


def _today_log_path() -> Path:
    """Return path to today's log file."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return LOGS_DIR / f"{date_str}.json"


def _load_log(path: Path) -> list[dict]:
    """Load existing log entries from file."""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def log_action(
    action_type: str,
    actor: str,
    target: str,
    description: str,
    approval_status: str = "N/A",
    status: str = "success",
    metadata: Optional[dict] = None,
) -> dict:
    """
    Log a single action to today's log file.

    Parameters
    ----------
    action_type : str
        e.g. 'watcher_detection', 'plan_created', 'email_sent',
             'approval_requested', 'task_routed'
    actor : str
        e.g. 'gmail_watcher', 'reasoning_loop', 'email_mcp'
    target : str
        e.g. filename, email address, task identifier
    description : str
        Human-readable summary of the action
    approval_status : str
        'auto_approved', 'pending', 'approved', 'rejected', 'N/A'
    status : str
        'success', 'failed', 'dry_run', 'queued'
    metadata : dict, optional
        Any extra structured data
    """
    entry = {
        "timestamp": now_iso(),
        "action_type": action_type,
        "actor": actor,
        "target": target,
        "description": description,
        "approval_status": approval_status,
        "status": status,
    }
    if metadata:
        entry["metadata"] = metadata

    log_path = _today_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entries = _load_log(log_path)
    entries.append(entry)
    log_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    return entry


def get_today_log() -> list[dict]:
    """Return all log entries for today."""
    return _load_log(_today_log_path())


def get_log_for_date(date_str: str) -> list[dict]:
    """Return all log entries for a given date (YYYY-MM-DD)."""
    return _load_log(LOGS_DIR / f"{date_str}.json")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Quick test
    log_action(
        action_type="test",
        actor="action_logger",
        target="self",
        description="Logger self-test — this entry confirms logging works.",
        status="success",
    )
    print(f"✅  Test entry written to {_today_log_path()}")
    print(json.dumps(get_today_log(), indent=2))
