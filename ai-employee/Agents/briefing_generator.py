"""
Briefing Generator — Daily + Weekly CEO Briefings (Gold Tier)
================================================================
Generates structured briefings from vault data:
  - Pending action items, approvals, completed tasks
  - Bank balances, financial summary
  - Active projects
  - System health
  - Weekly aggregation on Mondays

Usage:
    python Agents/briefing_generator.py                # daily briefing
    python Agents/briefing_generator.py --weekly       # weekly CEO briefing
    python Agents/briefing_generator.py --schedule     # Windows Task Scheduler
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    from Agents.config import (
        VAULT_ROOT, NEEDS_ACTION_DIR, DONE_DIR, ACCOUNTING_DIR,
        PENDING_APPROVAL_DIR, APPROVED_DIR, LOGS_DIR, PROJECTS_DIR,
        DRY_RUN, BANK_BALANCE_LAST_KNOWN, BANK_CURRENCY, BANK_NAME,
        now_iso, now_local_iso,
    )
    from Agents.action_logger import log_action, get_today_log
except ImportError:
    from config import (
        VAULT_ROOT, NEEDS_ACTION_DIR, DONE_DIR, ACCOUNTING_DIR,
        PENDING_APPROVAL_DIR, APPROVED_DIR, LOGS_DIR, PROJECTS_DIR,
        DRY_RUN, BANK_BALANCE_LAST_KNOWN, BANK_CURRENCY, BANK_NAME,
        now_iso, now_local_iso,
    )
    from action_logger import log_action, get_today_log


def _count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return len([f for f in directory.iterdir() if f.is_file() and not f.name.startswith(".")])


def _list_files(directory: Path, max_items: int = 10) -> list[str]:
    if not directory.exists():
        return []
    return sorted([f.name for f in directory.iterdir() if f.is_file() and not f.name.startswith(".")], reverse=True)[:max_items]


def _weekly_log_summary(days: int = 7) -> dict:
    """Aggregate log entries over multiple days."""
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    total = 0

    for i in range(days):
        date = datetime.now(timezone.utc) - timedelta(days=i)
        log_path = LOGS_DIR / f"{date.strftime('%Y-%m-%d')}.json"
        if not log_path.exists():
            continue
        try:
            entries = json.loads(log_path.read_text(encoding="utf-8"))
            total += len(entries)
            for e in entries:
                t = e.get("action_type", "unknown")
                s = e.get("status", "unknown")
                by_type[t] = by_type.get(t, 0) + 1
                by_status[s] = by_status.get(s, 0) + 1
        except (json.JSONDecodeError, OSError):
            continue

    return {"total": total, "by_type": by_type, "by_status": by_status}


def _today_log_summary() -> str:
    entries = get_today_log()
    if not entries:
        return "No actions logged today."
    by_type: dict[str, int] = {}
    for e in entries:
        t = e.get("action_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    return "\n".join(f"- `{t}`: {c}" for t, c in sorted(by_type.items()))


def generate_daily_briefing() -> str:
    now = now_local_iso()
    date_str = datetime.now().strftime("%A, %B %d, %Y")

    na = _count_files(NEEDS_ACTION_DIR)
    done = _count_files(DONE_DIR)
    pending = _count_files(PENDING_APPROVAL_DIR)
    approved = _count_files(APPROVED_DIR)
    accounting = _count_files(ACCOUNTING_DIR)
    projects = _count_files(PROJECTS_DIR)

    na_files = _list_files(NEEDS_ACTION_DIR)
    pending_files = _list_files(PENDING_APPROVAL_DIR)
    log_summary = _today_log_summary()

    briefing = f"""---
type: briefing
frequency: daily
generated_at: {now_iso()}
---

# ☕ CEO Daily Briefing

**Date:** {date_str}
**Generated:** {now}
**Mode:** {'🏜️ DRY RUN' if DRY_RUN else '🟢 LIVE'}

---

## 💰 Financial Dashboard

| Metric              | Value                            |
| ------------------- | -------------------------------- |
| Bank ({BANK_NAME or 'N/A'})  | {BANK_CURRENCY} {BANK_BALANCE_LAST_KNOWN} |
| Accounting Items    | {accounting}                     |
| Pending Invoices    | _(connect Odoo for live data)_   |

## 📊 Task Overview

| Queue               | Count |
| ------------------- | ----- |
| 🔴 Needs Action      | {na}     |
| ⏳ Pending Approval   | {pending}     |
| ✅ Approved (ready)   | {approved}     |
| 📦 Done (completed)   | {done}     |
| 📁 Active Projects    | {projects}     |

## 🔴 Items Requiring Attention

"""
    if na_files:
        for f in na_files:
            briefing += f"- [ ] `{f}`\n"
    else:
        briefing += "_All clear — no items pending!_ ✅\n"

    briefing += "\n## ⏳ Pending Approvals\n\n"
    if pending_files:
        for f in pending_files:
            briefing += f"- ⚠️ `{f}`\n"
    else:
        briefing += "_No pending approvals._ ✅\n"

    briefing += f"""
## 📋 Today's Activity

{log_summary}

## 🤖 System Status

- **Orchestrator:** {'Active' if not DRY_RUN else 'DRY RUN mode'}
- **Watchers:** Gmail + WhatsApp + Filesystem
- **MCP Servers:** Email, Social, Calendar, Browser, Odoo
- **HITL Gate:** Active
- **Audit Agent:** Available

---

> *Briefing by AI Employee System — {now}*
"""
    return briefing


def generate_weekly_briefing() -> str:
    """Generate comprehensive weekly CEO briefing."""
    now = now_local_iso()
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%B %d")
    week_end = datetime.now().strftime("%B %d, %Y")
    weekly_stats = _weekly_log_summary(7)

    na = _count_files(NEEDS_ACTION_DIR)
    done = _count_files(DONE_DIR)
    pending = _count_files(PENDING_APPROVAL_DIR)
    accounting = _count_files(ACCOUNTING_DIR)
    projects = _count_files(PROJECTS_DIR)

    briefing = f"""---
type: briefing
frequency: weekly
generated_at: {now_iso()}
period: {week_start} - {week_end}
---

# 📅 Weekly CEO Briefing

**Period:** {week_start} — {week_end}
**Generated:** {now}

---

## 📊 Week at a Glance

| Metric                     | Value  |
| -------------------------- | ------ |
| Total AI actions (7d)      | {weekly_stats['total']}     |
| Tasks completed            | {done}     |
| Tasks still pending        | {na}     |
| Approvals waiting          | {pending}     |
| Accounting items           | {accounting}     |
| Active projects            | {projects}     |

## 💰 Financial Summary

| Metric              | Value                            |
| ------------------- | -------------------------------- |
| Bank ({BANK_NAME or 'N/A'})  | {BANK_CURRENCY} {BANK_BALANCE_LAST_KNOWN} |
| Accounting Items    | {accounting}                     |
| _(Connect Odoo for full P&L, invoices, receivables)_ |

## 📈 Activity Breakdown (7 Days)

### By Action Type
"""
    if weekly_stats["by_type"]:
        for t, c in sorted(weekly_stats["by_type"].items(), key=lambda x: -x[1]):
            briefing += f"- `{t}`: {c}\n"
    else:
        briefing += "_No logged actions this week._\n"

    briefing += "\n### By Status\n"
    if weekly_stats["by_status"]:
        for s, c in sorted(weekly_stats["by_status"].items(), key=lambda x: -x[1]):
            icon = {"success": "✅", "dry_run": "🏜️", "failed": "❌", "queued": "⏳"}.get(s, "❓")
            briefing += f"- {icon} `{s}`: {c}\n"
    else:
        briefing += "_No status data._\n"

    briefing += f"""
## 🎯 Priorities for Next Week

- [ ] Review any stale tasks in /Needs_Action
- [ ] Clear pending approvals
- [ ] Review accounting items
- [ ] Run audit: `python Agents/audit_agent.py`

## 🤖 System Health

- Total logged actions: {weekly_stats['total']}
- Errors: {weekly_stats['by_status'].get('failed', 0)}
- Dry-run actions: {weekly_stats['by_status'].get('dry_run', 0)}
- Success rate: {(weekly_stats['by_status'].get('success', 0) / max(weekly_stats['total'], 1) * 100):.0f}%

---

> *Weekly briefing by AI Employee System — {now}*
"""
    return briefing


def save_briefing(weekly: bool = False) -> Path:
    if weekly:
        content = generate_weekly_briefing()
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = VAULT_ROOT / f"Weekly_Briefing_{date_str}.md"
    else:
        content = generate_daily_briefing()
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = VAULT_ROOT / f"Briefing_{date_str}.md"

    filepath.write_text(content, encoding="utf-8")
    btype = "weekly" if weekly else "daily"
    log_action("briefing_generated", "briefing_generator", filepath.name, f"{btype.title()} briefing for {date_str}")
    return filepath


def schedule_windows_task() -> None:
    """Register Windows Task Scheduler jobs."""
    python_exe = sys.executable
    script = str(Path(__file__).resolve())

    tasks = [
        {"name": "AIEmployee_DailyBriefing", "args": "", "time": "07:00", "schedule": "DAILY"},
        {"name": "AIEmployee_WeeklyBriefing", "args": "--weekly", "time": "07:30", "schedule": "WEEKLY", "day": "MON"},
        {"name": "AIEmployee_DailyAudit", "args": "", "time": "18:00", "schedule": "DAILY",
         "script_override": str((Path(__file__).parent / "audit_agent.py").resolve())},
    ]

    for task in tasks:
        s = task.get("script_override", script)
        a = task["args"]
        cmd = (
            f'schtasks /Create /F /TN "{task["name"]}" '
            f'/TR "\"{python_exe}\" \"{s}\" {a}" '
            f'/SC {task["schedule"]} /ST {task["time"]} '
        )
        if task["schedule"] == "WEEKLY":
            cmd += f'/D {task.get("day", "MON")} '
        cmd += "/RL HIGHEST"

        print(f"  📅  {task['name']}: {task['schedule']} at {task['time']}")
        if DRY_RUN:
            print(f"      🏜️ DRY RUN — not registered")
        else:
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                print(f"      {'✅ Registered' if result.returncode == 0 else '❌ Failed'}")
            except Exception as e:
                print(f"      ❌ Error: {e}")


if __name__ == "__main__":
    if "--schedule" in sys.argv:
        print("📅  Scheduling Briefings & Audits\n")
        schedule_windows_task()
    elif "--weekly" in sys.argv:
        path = save_briefing(weekly=True)
        print(f"📅  Weekly CEO Briefing: {path}")
    else:
        path = save_briefing(weekly=False)
        print(f"☕  Daily CEO Briefing: {path}")
