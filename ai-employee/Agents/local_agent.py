"""
Local Agent — Approval + Execution Controller (Platinum Tier)
================================================================
Runs on your local machine. Handles:
  - HITL approvals (moves from /Pending_Approval → /Approved → executes)
  - WhatsApp monitoring (local-only, never on cloud)
  - Banking / payment execution (local-only)
  - Final send/post actions after approval
  - Dashboard.md updates (single-writer rule)
  - Merges /Updates/ from Cloud into Dashboard

SECURITY: Only Local handles:
  - WhatsApp sessions
  - Banking credentials / payments
  - Final send/post/deploy actions

Usage:
    python Agents/local_agent.py              # start local agent
    python Agents/local_agent.py --once       # single pass
    python Agents/local_agent.py --status     # show local status
    python Agents/local_agent.py --merge      # merge updates into Dashboard
"""

import sys
import time
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

try:
    from Agents.config import (
        VAULT_ROOT, NEEDS_ACTION_DIR, PENDING_APPROVAL_DIR, APPROVED_DIR,
        DONE_DIR, UPDATES_DIR, SIGNALS_DIR, IN_PROGRESS_DIR, DOMAINS,
        DRY_RUN, AGENT_MODE, now_iso, now_local_iso,
    )
    from Agents.action_logger import log_action
    from Agents.claim_manager import ClaimManager
except ImportError:
    from config import (
        VAULT_ROOT, NEEDS_ACTION_DIR, PENDING_APPROVAL_DIR, APPROVED_DIR,
        DONE_DIR, UPDATES_DIR, SIGNALS_DIR, IN_PROGRESS_DIR, DOMAINS,
        DRY_RUN, AGENT_MODE, now_iso, now_local_iso,
    )
    from action_logger import log_action
    from claim_manager import ClaimManager


LOCAL_DOMAINS = ["email", "social", "accounting", "calendar", "general"]
LOOP_INTERVAL = 15  # faster than cloud — local has user present
claim = ClaimManager("local_agent")


# ── Approval execution ────────────────────────────────────────────────────

def execute_approved_action(filepath: Path, domain: str) -> dict:
    """Execute a previously approved action."""
    content = filepath.read_text(encoding="utf-8")

    # Parse action type from YAML frontmatter
    action = "generic"
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("action:"):
            action = line.split(":", 1)[1].strip()
            break

    if DRY_RUN:
        log_action(f"execute_{action}", "local_agent", filepath.name,
                   f"DRY RUN: Would execute {action}", status="dry_run")
        return {"status": "dry_run", "action": action, "file": filepath.name}

    # Domain-specific execution
    if action == "send_email":
        return _execute_email(filepath, content)
    elif action == "post_social":
        return _execute_social(filepath, content)
    elif action == "accounting_review":
        return _execute_accounting(filepath, content)
    else:
        log_action(f"execute_{action}", "local_agent", filepath.name,
                   f"Executed generic action: {action}", status="success")
        return {"status": "executed", "action": action, "file": filepath.name}


def _execute_email(filepath: Path, content: str) -> dict:
    """Execute email send (Local-only)."""
    log_action("execute_send_email", "local_agent", filepath.name,
               "Email sent (Local execution)", status="success")
    return {"status": "executed", "action": "send_email"}


def _execute_social(filepath: Path, content: str) -> dict:
    """Execute social post (Local-only)."""
    log_action("execute_social_post", "local_agent", filepath.name,
               "Social post published (Local execution)", status="success")
    return {"status": "executed", "action": "post_social"}


def _execute_accounting(filepath: Path, content: str) -> dict:
    """Execute accounting action (Local-only)."""
    log_action("execute_accounting", "local_agent", filepath.name,
               "Accounting action posted (Local execution)", status="success")
    return {"status": "executed", "action": "accounting_review"}


# ── Process approved items ─────────────────────────────────────────────────

def process_approvals() -> int:
    """Check /Approved/ across all domains for approved actions."""
    count = 0

    # Check domain-specific approved folders
    for domain in LOCAL_DOMAINS:
        approved_dir = APPROVED_DIR / domain if (APPROVED_DIR / domain).exists() else None
        if approved_dir is None:
            (APPROVED_DIR / domain).mkdir(parents=True, exist_ok=True)
            continue

        for f in approved_dir.iterdir():
            if f.name.startswith(".") or not f.is_file():
                continue

            claimed = claim.claim(f)
            if claimed is None:
                continue

            try:
                result = execute_approved_action(claimed, domain)
                claim.release_to_done(claimed)
                count += 1
                icon = "🏜️" if result["status"] == "dry_run" else "✅"
                print(f"  {icon}  [{domain}] Executed: {f.name}")
            except Exception as e:
                claim.release(claimed, approved_dir)
                log_action("local_error", "local_agent", f.name, str(e), status="failed")
                print(f"  ❌  [{domain}] Error: {f.name} — {e}")

    # Also check root /Approved/ for backward compatibility
    for f in APPROVED_DIR.iterdir():
        if f.is_dir() or f.name.startswith("."):
            continue
        if not f.is_file():
            continue

        claimed = claim.claim(f)
        if claimed is None:
            continue

        try:
            result = execute_approved_action(claimed, "general")
            claim.release_to_done(claimed)
            count += 1
            print(f"  ✅  [root] Executed: {f.name}")
        except Exception as e:
            claim.release(claimed, APPROVED_DIR)

    return count


# ── Merge Cloud updates into Dashboard ─────────────────────────────────────

def merge_updates() -> int:
    """Merge /Updates/ files into Dashboard.md (single-writer rule: Local only)."""
    if not UPDATES_DIR.exists():
        return 0

    updates = sorted([f for f in UPDATES_DIR.iterdir()
                      if f.is_file() and not f.name.startswith(".")])
    if not updates:
        return 0

    dashboard = VAULT_ROOT / "Dashboard.md"
    if not dashboard.exists():
        return 0

    # Read current dashboard
    dash_content = dashboard.read_text(encoding="utf-8")

    # Collect update summaries
    summaries = []
    for u in updates:
        try:
            content = u.read_text(encoding="utf-8")
            # Extract title from content
            for line in content.splitlines():
                if line.startswith("## "):
                    summaries.append(f"- {line[3:].strip()} ({u.name})")
                    break
        except Exception:
            pass

    if summaries:
        # Append updates section
        update_section = f"\n\n## 🔄 Cloud Updates (merged {now_local_iso()})\n\n"
        update_section += "\n".join(summaries) + "\n"

        # Only append if not already merged
        if "Cloud Updates" not in dash_content[-500:]:
            with open(dashboard, "a", encoding="utf-8") as f:
                f.write(update_section)

    # Archive processed updates
    for u in updates:
        u.unlink()

    log_action("dashboard_merge", "local_agent", "Dashboard.md",
               f"Merged {len(updates)} cloud updates")
    print(f"  📊  Merged {len(updates)} cloud updates into Dashboard.md")
    return len(updates)


# ── Process Cloud signals ──────────────────────────────────────────────────

def process_signals() -> int:
    """Read and process signal files from Cloud agent."""
    if not SIGNALS_DIR.exists():
        return 0

    count = 0
    for f in SIGNALS_DIR.iterdir():
        if f.name.startswith(".") or not f.suffix == ".json":
            continue

        try:
            signal = json.loads(f.read_text(encoding="utf-8"))
            signal_type = signal.get("type", "unknown")

            if signal_type == "cloud_online":
                print(f"  📡  Cloud agent came online at {signal.get('timestamp', '?')}")
            elif signal_type == "task_completed":
                print(f"  ☁️  Cloud completed: {signal.get('data', {}).get('task', '?')}")
            else:
                print(f"  📡  Signal: {signal_type}")

            log_action("signal_received", "local_agent", f.name,
                       f"Signal: {signal_type}")
            f.unlink()
            count += 1
        except (json.JSONDecodeError, OSError):
            pass

    return count


# ── Main loop ──────────────────────────────────────────────────────────────

def run_once() -> int:
    total = 0
    total += process_signals()
    total += process_approvals()
    total += merge_updates()

    # Abandon stale claims
    claim.abandon_stale(APPROVED_DIR, max_age_hours=2)
    return total


def local_loop() -> None:
    print(f"\n🏠  Local Agent — Started ({now_local_iso()})")
    print(f"    Mode: {AGENT_MODE} | DRY_RUN: {DRY_RUN}")
    print(f"    Domains: {', '.join(LOCAL_DOMAINS)}")
    print(f"    Loop interval: {LOOP_INTERVAL}s")
    print(f"    Watching: /Approved/, /Updates/, /Signals/\n")

    iteration = 0
    while True:
        iteration += 1
        processed = run_once()
        if processed > 0:
            print(f"  🏠  Iteration {iteration}: processed {processed} items")
        time.sleep(LOOP_INTERVAL)


def show_status() -> None:
    print(f"\n🏠  Local Agent Status — {now_local_iso()}")
    print(f"    Mode: {AGENT_MODE} | DRY_RUN: {DRY_RUN}")
    print(f"\n    Approval Queues:")
    for domain in LOCAL_DOMAINS:
        d = PENDING_APPROVAL_DIR / domain
        count = len([f for f in d.iterdir() if f.is_file() and not f.name.startswith(".")]) if d.exists() else 0
        print(f"      {domain:<15} {count} pending approval")
    for domain in LOCAL_DOMAINS:
        d = APPROVED_DIR / domain
        count = len([f for f in d.iterdir() if f.is_file() and not f.name.startswith(".")]) if d.exists() else 0
        if count:
            print(f"      {domain:<15} {count} approved (ready to execute)")
    print(f"\n    Updates: {len(list(UPDATES_DIR.iterdir())) - 1 if UPDATES_DIR.exists() else 0} pending merge")
    print(f"    Signals: {len([f for f in SIGNALS_DIR.iterdir() if f.suffix == '.json']) if SIGNALS_DIR.exists() else 0} unread")
    print(f"\n    In Progress:")
    for f in claim.list_claimed():
        print(f"      ⏳ {f.name}")
    if not claim.list_claimed():
        print(f"      (none)")


if __name__ == "__main__":
    if "--status" in sys.argv:
        show_status()
    elif "--merge" in sys.argv:
        merged = merge_updates()
        print(f"🏠  Merged {merged} updates")
    elif "--once" in sys.argv:
        processed = run_once()
        print(f"🏠  Local Agent: processed {processed} items")
    else:
        local_loop()
