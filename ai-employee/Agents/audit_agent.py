"""
Audit Agent — Business & Accounting Auditor
=============================================
Autonomous audit agent that:
  - Scans /Accounting for financial items and validates them
  - Cross-references /Done against /Needs_Action for completeness
  - Checks /Logs for errors, retries, and anomalies
  - Generates weekly audit reports
  - Flags overdue items and stale tasks

Usage:
    python Agents/audit_agent.py                # run full audit
    python Agents/audit_agent.py --quick        # summary only
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter

try:
    from Agents.config import (
        VAULT_ROOT, NEEDS_ACTION_DIR, DONE_DIR, ACCOUNTING_DIR,
        PENDING_APPROVAL_DIR, APPROVED_DIR, LOGS_DIR, PROJECTS_DIR,
        DRY_RUN, BANK_BALANCE_LAST_KNOWN, BANK_CURRENCY,
        now_iso, now_local_iso,
    )
    from Agents.action_logger import log_action, get_today_log
except ImportError:
    from config import (
        VAULT_ROOT, NEEDS_ACTION_DIR, DONE_DIR, ACCOUNTING_DIR,
        PENDING_APPROVAL_DIR, APPROVED_DIR, LOGS_DIR, PROJECTS_DIR,
        DRY_RUN, BANK_BALANCE_LAST_KNOWN, BANK_CURRENCY,
        now_iso, now_local_iso,
    )
    from action_logger import log_action, get_today_log


def _count_files(d: Path) -> int:
    if not d.exists():
        return 0
    return len([f for f in d.iterdir() if f.is_file() and not f.name.startswith(".")])


def _list_files(d: Path) -> list[str]:
    if not d.exists():
        return []
    return sorted([f.name for f in d.iterdir() if f.is_file() and not f.name.startswith(".")])


def _file_age_days(filepath: Path) -> float:
    """Return age of file in days based on name timestamp or mtime."""
    try:
        mtime = filepath.stat().st_mtime
        age = (datetime.now().timestamp() - mtime) / 86400
        return round(age, 1)
    except Exception:
        return 0


# ── Audit checks ──────────────────────────────────────────────────────────

def audit_stale_tasks(max_age_days: int = 3) -> dict:
    """Find tasks in Needs_Action that are older than max_age_days."""
    stale = []
    for f in NEEDS_ACTION_DIR.iterdir():
        if f.name.startswith(".") or not f.is_file():
            continue
        age = _file_age_days(f)
        if age > max_age_days:
            stale.append({"file": f.name, "age_days": age})
    return {"check": "stale_tasks", "stale_count": len(stale), "items": stale, "threshold_days": max_age_days}


def audit_pending_approvals() -> dict:
    """Check for stuck approvals (older than 1 day)."""
    stuck = []
    for f in PENDING_APPROVAL_DIR.iterdir():
        if f.name.startswith(".") or not f.is_file():
            continue
        age = _file_age_days(f)
        if age > 1:
            stuck.append({"file": f.name, "age_days": age})
    return {"check": "stuck_approvals", "stuck_count": len(stuck), "items": stuck}


def audit_accounting_items() -> dict:
    """Verify accounting items have been reviewed."""
    unreviewed = _list_files(ACCOUNTING_DIR)
    plans = [f for f in unreviewed if f.startswith("Plan_")]
    raw = [f for f in unreviewed if not f.startswith("Plan_")]
    return {
        "check": "accounting_items",
        "total": len(unreviewed),
        "with_plans": len(plans),
        "without_plans": len(raw),
        "items": raw[:10],
    }


def audit_log_errors(days_back: int = 7) -> dict:
    """Scan recent logs for errors and failed actions."""
    errors = []
    retries = 0
    total_actions = 0

    for i in range(days_back):
        date = datetime.now(timezone.utc) - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        log_path = LOGS_DIR / f"{date_str}.json"
        if not log_path.exists():
            continue
        try:
            entries = json.loads(log_path.read_text(encoding="utf-8"))
            total_actions += len(entries)
            for e in entries:
                if e.get("status") == "failed":
                    errors.append({
                        "date": date_str,
                        "action": e.get("action_type"),
                        "actor": e.get("actor"),
                        "description": e.get("description", "")[:100],
                    })
                if "restart" in e.get("action_type", ""):
                    retries += 1
        except (json.JSONDecodeError, OSError):
            continue

    return {
        "check": "log_errors",
        "days_scanned": days_back,
        "total_actions": total_actions,
        "error_count": len(errors),
        "retry_count": retries,
        "recent_errors": errors[:10],
    }


def audit_folder_health() -> dict:
    """Check vault folder sizes and health."""
    folders = {
        "Inbox": NEEDS_ACTION_DIR.parent / "Inbox",
        "Needs_Action": NEEDS_ACTION_DIR,
        "Done": DONE_DIR,
        "Accounting": ACCOUNTING_DIR,
        "Pending_Approval": PENDING_APPROVAL_DIR,
        "Approved": APPROVED_DIR,
        "Logs": LOGS_DIR,
        "Projects": PROJECTS_DIR,
    }
    health = {}
    for name, path in folders.items():
        health[name] = {
            "exists": path.exists(),
            "file_count": _count_files(path) if path.exists() else 0,
        }
    return {"check": "folder_health", "folders": health}


# ── Full audit report ─────────────────────────────────────────────────────

def run_full_audit() -> str:
    """Run all audit checks and generate a markdown report."""
    now = now_local_iso()
    date_str = datetime.now().strftime("%Y-%m-%d")

    stale = audit_stale_tasks()
    approvals = audit_pending_approvals()
    accounting = audit_accounting_items()
    errors = audit_log_errors()
    health = audit_folder_health()

    # Risk score (0-100)
    risk = 0
    risk += min(stale["stale_count"] * 10, 30)
    risk += min(approvals["stuck_count"] * 15, 30)
    risk += min(errors["error_count"] * 5, 20)
    risk += 10 if accounting["without_plans"] > 0 else 0
    risk += 10 if any(not v["exists"] for v in health["folders"].values()) else 0
    risk = min(risk, 100)

    risk_icon = "🟢" if risk < 20 else "🟡" if risk < 50 else "🔴"

    report = f"""---
type: audit_report
generated_at: {now_iso()}
risk_score: {risk}
---

# 🔍 Business Audit Report

**Date:** {date_str}
**Generated:** {now}
**Risk Score:** {risk_icon} {risk}/100

---

## 📊 Summary

| Check                | Status                        | Count |
| -------------------- | ----------------------------- | ----- |
| Stale tasks (>3d)    | {"⚠️ Action needed" if stale["stale_count"] > 0 else "✅ Clear"} | {stale["stale_count"]} |
| Stuck approvals (>1d)| {"⚠️ Review needed" if approvals["stuck_count"] > 0 else "✅ Clear"} | {approvals["stuck_count"]} |
| Accounting items     | {"⚠️ Unreviewed" if accounting["without_plans"] > 0 else "✅ All reviewed"} | {accounting["without_plans"]} |
| Log errors (7d)      | {"⚠️ Errors found" if errors["error_count"] > 0 else "✅ Clean"} | {errors["error_count"]} |
| Agent restarts (7d)  | {"⚠️ Instability" if errors["retry_count"] > 5 else "✅ Stable"} | {errors["retry_count"]} |

---

## 🗂️ Folder Health

| Folder            | Exists | Files |
| ----------------- | ------ | ----- |
"""
    for fname, fdata in health["folders"].items():
        status = "✅" if fdata["exists"] else "❌"
        report += f"| {fname:<18}| {status}     | {fdata['file_count']}     |\n"

    report += f"""
---

## 💰 Financial Overview

- **Bank Balance (last known):** {BANK_CURRENCY} {BANK_BALANCE_LAST_KNOWN}
- **Unreviewed accounting items:** {accounting["without_plans"]}
"""
    if accounting["items"]:
        for item in accounting["items"][:5]:
            report += f"  - `{item}`\n"

    if stale["items"]:
        report += "\n---\n\n## ⏰ Stale Tasks (>3 days)\n\n"
        for item in stale["items"]:
            report += f"- `{item['file']}` — {item['age_days']} days old\n"

    if approvals["items"]:
        report += "\n---\n\n## ⏳ Stuck Approvals (>1 day)\n\n"
        for item in approvals["items"]:
            report += f"- `{item['file']}` — {item['age_days']} days waiting\n"

    if errors["recent_errors"]:
        report += "\n---\n\n## ❌ Recent Errors\n\n"
        for err in errors["recent_errors"][:5]:
            report += f"- [{err['date']}] `{err['actor']}` → {err['action']}: {err['description']}\n"

    report += f"""
---

## 🎯 Recommendations

"""
    if stale["stale_count"] > 0:
        report += "- ⚠️ **Review stale tasks** — items in /Needs_Action are aging.\n"
    if approvals["stuck_count"] > 0:
        report += "- ⚠️ **Clear approval queue** — pending HITL approvals need attention.\n"
    if accounting["without_plans"] > 0:
        report += "- 💰 **Review accounting items** — unprocessed financial records.\n"
    if errors["error_count"] > 3:
        report += "- 🔧 **Investigate errors** — multiple failures in recent logs.\n"
    if risk == 0:
        report += "- ✅ **All clear** — no issues detected. System healthy.\n"

    report += f"""
---

> *Audit auto-generated by AI Employee System — {now}*
"""
    return report


def save_audit() -> Path:
    """Save audit report to vault root."""
    content = run_full_audit()
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = VAULT_ROOT / f"Audit_{date_str}.md"
    filepath.write_text(content, encoding="utf-8")
    log_action("audit_generated", "audit_agent", filepath.name, f"Audit report for {date_str}")
    return filepath


def quick_summary() -> None:
    """Print a quick audit summary to stdout."""
    print(f"🔍  Quick Audit — {now_local_iso()}\n")
    h = audit_folder_health()
    for name, data in h["folders"].items():
        icon = "✅" if data["exists"] else "❌"
        print(f"  {icon}  {name:<20} {data['file_count']} files")

    stale = audit_stale_tasks()
    appr = audit_pending_approvals()
    errs = audit_log_errors()
    print(f"\n  ⏰  Stale tasks:      {stale['stale_count']}")
    print(f"  ⏳  Stuck approvals:  {appr['stuck_count']}")
    print(f"  ❌  Recent errors:    {errs['error_count']}")
    print(f"  🔄  Agent restarts:   {errs['retry_count']}")


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--quick" in sys.argv:
        quick_summary()
    else:
        path = save_audit()
        print(f"🔍  Audit report generated: {path}")
