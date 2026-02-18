"""
Task Router Agent — Core Reasoning Skill
=========================================
Reads files from the Inbox, applies simple keyword-based classification,
and moves them to the appropriate folder (Needs_Action or Done).

Bronze Tier: Rule-based routing only. No LLM calls.

Usage:
    python Agents/task_router.py
"""

import shutil
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
VAULT_ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = VAULT_ROOT / "Inbox"
NEEDS_ACTION_DIR = VAULT_ROOT / "Needs_Action"
DONE_DIR = VAULT_ROOT / "Done"

# Simple keyword rules — extend as needed
ACTION_KEYWORDS = [
    "urgent", "todo", "action", "review", "approve",
    "fix", "deploy", "respond", "follow up", "deadline",
    "request", "task", "assign", "escalate", "priority",
]

DONE_KEYWORDS = [
    "completed", "done", "resolved", "closed", "archived",
    "shipped", "merged", "finished",
]


def classify(content: str) -> str:
    """
    Classify file content into a target folder.
    Returns one of: 'Needs_Action', 'Done', or 'Inbox' (keep in place).
    """
    lower = content.lower()

    # Check done-keywords first (explicit completion signal)
    for kw in DONE_KEYWORDS:
        if kw in lower:
            return "Done"

    # Check action-keywords
    for kw in ACTION_KEYWORDS:
        if kw in lower:
            return "Needs_Action"

    # Default: leave in Inbox for manual triage
    return "Inbox"


def route_inbox() -> list[dict]:
    """
    Scan Inbox, classify each file, and move it to the target folder.
    Returns a log of actions taken.
    """
    actions = []

    for entry in sorted(INBOX_DIR.iterdir()):
        if entry.name.startswith(".") or not entry.is_file():
            continue

        content = entry.read_text(encoding="utf-8", errors="replace")
        target = classify(content)

        if target == "Inbox":
            actions.append({
                "file": entry.name,
                "action": "kept",
                "destination": "Inbox",
                "reason": "No matching keywords",
            })
            continue

        dest_dir = NEEDS_ACTION_DIR if target == "Needs_Action" else DONE_DIR
        dest_path = dest_dir / entry.name

        # Avoid overwriting — append timestamp if collision
        if dest_path.exists():
            stem = dest_path.stem
            suffix = dest_path.suffix
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            dest_path = dest_dir / f"{stem}_{ts}{suffix}"

        shutil.move(str(entry), str(dest_path))

        actions.append({
            "file": entry.name,
            "action": "moved",
            "destination": str(dest_path),
            "reason": f"Matched '{target}' keywords",
        })

    return actions


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"🔀  Task Router — scanning {INBOX_DIR}\n")
    results = route_inbox()

    if not results:
        print("  📭  Inbox is empty — nothing to route.")
    else:
        for r in results:
            icon = "📦" if r["action"] == "moved" else "📌"
            print(f"  {icon}  {r['file']} → {r['destination']}  ({r['reason']})")

    print(f"\n✅  Routing complete. {len(results)} file(s) processed.")
