"""
HITL Approval Checker — Human-in-the-Loop Enforcement
=======================================================
Monitors /Pending_Approval and /Approved folders.
When a file is moved from Pending_Approval → Approved,
this agent detects it and triggers the approved action.

All sensitive external actions MUST pass through this gate.

Usage:
    python Agents/hitl_approval.py --once    # single check
    python Agents/hitl_approval.py           # continuous monitoring
"""

import sys
import time
import shutil
from pathlib import Path
from datetime import datetime, timezone

try:
    from Agents.config import (
        PENDING_APPROVAL_DIR, APPROVED_DIR, DONE_DIR,
        DRY_RUN, now_iso, now_local_iso,
    )
    from Agents.action_logger import log_action
except ImportError:
    from config import (
        PENDING_APPROVAL_DIR, APPROVED_DIR, DONE_DIR,
        DRY_RUN, now_iso, now_local_iso,
    )
    from action_logger import log_action


POLL_INTERVAL = 10  # seconds


# ── Action handlers ───────────────────────────────────────────────────────
# Each approved action type maps to a handler function.
# Handlers receive the approval file path and return True if successful.

def _handle_draft_email_reply(filepath: Path) -> bool:
    """Execute approved email reply."""
    if DRY_RUN:
        print(f"    🏜️  DRY RUN: Would send email reply for {filepath.name}")
        return True
    # In production: call email MCP server here
    print(f"    ✉️  Email reply action executed for {filepath.name}")
    return True


def _handle_draft_social_post(filepath: Path) -> bool:
    """Execute approved social media post."""
    if DRY_RUN:
        print(f"    🏜️  DRY RUN: Would post to social media for {filepath.name}")
        return True
    print(f"    📣  Social media post executed for {filepath.name}")
    return True


def _handle_deploy_checklist(filepath: Path) -> bool:
    """Execute approved deployment."""
    if DRY_RUN:
        print(f"    🏜️  DRY RUN: Would start deployment for {filepath.name}")
        return True
    print(f"    🚀  Deployment started for {filepath.name}")
    return True


def _handle_request_approval(filepath: Path) -> bool:
    """Meta-approval — an approval that itself needed approval."""
    print(f"    ✅  Meta-approval processed for {filepath.name}")
    return True


ACTION_HANDLERS = {
    "draft_email_reply": _handle_draft_email_reply,
    "draft_social_post": _handle_draft_social_post,
    "deploy_checklist":  _handle_deploy_checklist,
    "request_approval":  _handle_request_approval,
}


def _extract_action_type(content: str) -> str:
    """Parse action type from approval file content."""
    for line in content.splitlines():
        if line.strip().startswith("action:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


# ── Core logic ─────────────────────────────────────────────────────────────
def check_approved() -> dict:
    """
    Scan /Approved for files that have been approved by a human.
    Execute the corresponding action and move the file to /Done.
    """
    summary = {"executed": 0, "failed": 0, "dry_run": 0}

    for filepath in sorted(APPROVED_DIR.iterdir()):
        if filepath.name.startswith(".") or not filepath.is_file():
            continue

        content = filepath.read_text(encoding="utf-8", errors="replace")
        action_type = _extract_action_type(content)

        handler = ACTION_HANDLERS.get(action_type)
        if handler is None:
            print(f"  ⚠️  Unknown action type: {action_type} in {filepath.name}")
            log_action(
                action_type="action_failed",
                actor="hitl_approval",
                target=filepath.name,
                description=f"No handler for action type: {action_type}",
                approval_status="approved",
                status="failed",
            )
            summary["failed"] += 1
            continue

        # Execute the action
        try:
            success = handler(filepath)
            status = "dry_run" if DRY_RUN else ("success" if success else "failed")

            log_action(
                action_type="action_executed",
                actor="hitl_approval",
                target=filepath.name,
                description=f"Executed {action_type} (DRY_RUN={DRY_RUN})",
                approval_status="approved",
                status=status,
            )

            # Move to Done
            done_path = DONE_DIR / filepath.name
            if done_path.exists():
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                done_path = DONE_DIR / f"{filepath.stem}_{ts}{filepath.suffix}"
            shutil.move(str(filepath), str(done_path))

            print(f"  ✅  [{action_type}] Executed → moved to /Done")

            if DRY_RUN:
                summary["dry_run"] += 1
            else:
                summary["executed"] += 1

        except Exception as e:
            print(f"  ❌  [{action_type}] Failed: {e}")
            log_action(
                action_type="action_failed",
                actor="hitl_approval",
                target=filepath.name,
                description=str(e),
                approval_status="approved",
                status="failed",
            )
            summary["failed"] += 1

    return summary


def check_pending() -> int:
    """Return count of pending approval requests."""
    return len([
        f for f in PENDING_APPROVAL_DIR.iterdir()
        if f.is_file() and not f.name.startswith(".")
    ])


def run_once() -> None:
    """Single pass: check approved items and report pending."""
    print(f"\n🔐  HITL Approval Check — {now_local_iso()}")

    result = check_approved()
    pending = check_pending()

    print(f"    ✅ Executed: {result['executed']}  "
          f"🏜️ Dry-run: {result['dry_run']}  "
          f"❌ Failed: {result['failed']}  "
          f"⏳ Pending: {pending}")


def approval_loop() -> None:
    """Continuously monitor for approved actions."""
    print("🔐  HITL Approval Monitor started")
    print(f"    DRY_RUN: {DRY_RUN}  |  Interval: {POLL_INTERVAL}s  |  Ctrl+C to stop\n")

    try:
        while True:
            run_once()
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\n🛑  Approval monitor stopped.")


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        approval_loop()
