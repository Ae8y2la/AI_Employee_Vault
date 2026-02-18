"""
Cloud Agent — Always-On Cloud Executive (Platinum Tier)
=========================================================
Runs 24/7 on a Cloud VM. Handles:
  - Email triage + draft replies (NEVER sends — Local approves)
  - Social media draft creation + scheduling
  - Accounting draft actions (read-only, draft invoices)
  - Calendar event creation (draft-only for sensitive)
  - Writes signals/updates for Local agent

SECURITY: Cloud NEVER handles:
  - WhatsApp sessions
  - Banking credentials / payments
  - Final send/post/deploy actions

Usage:
    python Agents/cloud_agent.py                # start cloud agent
    python Agents/cloud_agent.py --once         # single pass
    python Agents/cloud_agent.py --status       # show cloud status
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime, timezone

try:
    from Agents.config import (
        VAULT_ROOT, NEEDS_ACTION_DIR, PENDING_APPROVAL_DIR, PLANS_DIR,
        UPDATES_DIR, SIGNALS_DIR, DONE_DIR, DOMAINS,
        DRY_RUN, AGENT_MODE, now_iso, now_local_iso,
    )
    from Agents.action_logger import log_action
    from Agents.claim_manager import ClaimManager
except ImportError:
    from config import (
        VAULT_ROOT, NEEDS_ACTION_DIR, PENDING_APPROVAL_DIR, PLANS_DIR,
        UPDATES_DIR, SIGNALS_DIR, DONE_DIR, DOMAINS,
        DRY_RUN, AGENT_MODE, now_iso, now_local_iso,
    )
    from action_logger import log_action
    from claim_manager import ClaimManager


CLOUD_DOMAINS = ["email", "social", "accounting", "calendar"]
LOOP_INTERVAL = 30  # seconds
claim = ClaimManager("cloud_agent")


# ── Domain handlers ────────────────────────────────────────────────────────

def handle_email_task(filepath: Path) -> dict:
    """Triage email and create draft reply."""
    content = filepath.read_text(encoding="utf-8")

    # Determine priority
    priority = "normal"
    for kw in ["urgent", "asap", "important", "deadline"]:
        if kw in content.lower():
            priority = "high"
            break

    # Create draft reply in Pending_Approval
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    draft_name = f"DRAFT_REPLY_{ts}_{filepath.stem}.md"
    draft_path = PENDING_APPROVAL_DIR / "email" / draft_name

    draft_content = f"""---
type: email_draft_reply
source_file: {filepath.name}
priority: {priority}
created_by: cloud_agent
created_at: {now_iso()}
status: pending_local_approval
action: send_email
---

# ✉️ Draft Reply — Needs Local Approval

**Original:** `{filepath.name}`
**Priority:** {priority}
**Created by:** Cloud Agent
**Action required:** Local agent must review and approve sending

---

## 📧 Proposed Reply

> [Cloud Agent has triaged this email and prepared a draft response.]
> [Local agent: review, edit if needed, then move to /Approved/email/]

---

## 📎 Original Content

{content[:1000]}

---

> *Draft by cloud_agent — awaiting Local approval*
"""
    draft_path.write_text(draft_content, encoding="utf-8")
    log_action("email_draft", "cloud_agent", draft_name,
               f"Draft reply for {filepath.name} (priority: {priority})")
    return {"action": "email_draft", "priority": priority, "draft": draft_name}


def handle_social_task(filepath: Path) -> dict:
    """Create social media post draft."""
    content = filepath.read_text(encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    draft_name = f"DRAFT_SOCIAL_{ts}_{filepath.stem}.md"
    draft_path = PENDING_APPROVAL_DIR / "social" / draft_name

    draft_content = f"""---
type: social_draft
source_file: {filepath.name}
created_by: cloud_agent
created_at: {now_iso()}
status: pending_local_approval
action: post_social
---

# 📣 Social Media Draft — Needs Local Approval

**Source:** `{filepath.name}`
**Created by:** Cloud Agent
**Action required:** Local agent must approve before posting

---

## 📝 Proposed Post

> [Cloud Agent has drafted a social media post based on this task.]
> [Local agent: review, choose platform, then move to /Approved/social/]

---

## 📎 Source Content

{content[:800]}

---

> *Draft by cloud_agent — awaiting Local approval*
"""
    draft_path.write_text(draft_content, encoding="utf-8")
    log_action("social_draft", "cloud_agent", draft_name,
               f"Social draft for {filepath.name}")
    return {"action": "social_draft", "draft": draft_name}


def handle_accounting_task(filepath: Path) -> dict:
    """Create accounting draft (read-only, never posts)."""
    content = filepath.read_text(encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    draft_name = f"DRAFT_ACCOUNTING_{ts}_{filepath.stem}.md"
    draft_path = PENDING_APPROVAL_DIR / "accounting" / draft_name

    draft_content = f"""---
type: accounting_draft
source_file: {filepath.name}
created_by: cloud_agent
created_at: {now_iso()}
status: pending_local_approval
action: accounting_review
---

# 💰 Accounting Draft — Needs Local Approval

**Source:** `{filepath.name}`
**Created by:** Cloud Agent (draft-only, no financial mutations)
**Action required:** Local agent must review and approve

---

## 📊 Accounting Analysis

> [Cloud Agent has analyzed this accounting item.]
> [Local agent: verify amounts, approve posting to Odoo.]

---

## 📎 Source Content

{content[:800]}

---

> *Draft by cloud_agent — LOCAL approval required for any financial action*
"""
    draft_path.write_text(draft_content, encoding="utf-8")
    log_action("accounting_draft", "cloud_agent", draft_name,
               f"Accounting draft for {filepath.name}")
    return {"action": "accounting_draft", "draft": draft_name}


def handle_calendar_task(filepath: Path) -> dict:
    """Create calendar event draft."""
    content = filepath.read_text(encoding="utf-8")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    plan_name = f"Plan_calendar_{ts}_{filepath.stem}.md"
    plan_path = PLANS_DIR / "calendar" / plan_name

    plan_content = f"""---
type: calendar_plan
source_file: {filepath.name}
created_by: cloud_agent
created_at: {now_iso()}
status: planned
---

# 📅 Calendar Plan

**Source:** `{filepath.name}`

## Proposed Actions
- [ ] Create calendar event
- [ ] Send invitations (requires Local approval)
- [ ] Log completion

## Source Content

{content[:800]}
"""
    plan_path.write_text(plan_content, encoding="utf-8")
    log_action("calendar_plan", "cloud_agent", plan_name,
               f"Calendar plan for {filepath.name}")
    return {"action": "calendar_plan", "plan": plan_name}


DOMAIN_HANDLERS = {
    "email": handle_email_task,
    "social": handle_social_task,
    "accounting": handle_accounting_task,
    "calendar": handle_calendar_task,
}


# ── Signal writer ──────────────────────────────────────────────────────────

def write_signal(signal_type: str, data: dict) -> Path:
    """Write a signal file for the Local agent to pick up."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    signal_path = SIGNALS_DIR / f"{signal_type}_{ts}.json"
    signal = {
        "type": signal_type,
        "timestamp": now_iso(),
        "agent": "cloud_agent",
        "data": data,
    }
    signal_path.write_text(json.dumps(signal, indent=2), encoding="utf-8")
    return signal_path


def write_update(title: str, content: str) -> Path:
    """Write an update file for Local to merge into Dashboard.md."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    update_path = UPDATES_DIR / f"update_{ts}.md"
    update_content = f"""---
type: dashboard_update
created_by: cloud_agent
created_at: {now_iso()}
---

## {title}

{content}
"""
    update_path.write_text(update_content, encoding="utf-8")
    return update_path


# ── Main loop ──────────────────────────────────────────────────────────────

def process_domain(domain: str) -> int:
    """Process all tasks in a domain's Needs_Action folder."""
    domain_dir = NEEDS_ACTION_DIR / domain
    if not domain_dir.exists():
        return 0

    handler = DOMAIN_HANDLERS.get(domain)
    if not handler:
        return 0

    count = 0
    for f in domain_dir.iterdir():
        if f.name.startswith(".") or not f.is_file():
            continue

        # Claim the task
        claimed = claim.claim(f)
        if claimed is None:
            continue  # already claimed by another agent

        try:
            result = handler(claimed)
            # Release to Done after creating draft/plan
            claim.release_to_done(claimed)
            count += 1
            print(f"  ☁️  [{domain}] {result['action']}: {f.name}")
        except Exception as e:
            # On error, release back to Needs_Action
            claim.release(claimed, domain_dir)
            log_action("cloud_error", "cloud_agent", f.name, str(e), status="failed")
            print(f"  ❌  [{domain}] Error: {f.name} — {e}")

    return count


def process_general() -> int:
    """Process general (non-domain) Needs_Action items."""
    general_dir = NEEDS_ACTION_DIR / "general"
    if not general_dir.exists():
        return 0

    count = 0
    for f in general_dir.iterdir():
        if f.name.startswith(".") or not f.is_file():
            continue

        claimed = claim.claim(f)
        if claimed is None:
            continue

        # For general tasks, create a plan
        content = claimed.read_text(encoding="utf-8")
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        plan_name = f"Plan_general_{ts}_{claimed.stem}.md"
        plan_path = PLANS_DIR / "general" / plan_name
        plan_path.write_text(f"""---
type: general_plan
source: {claimed.name}
created_by: cloud_agent
created_at: {now_iso()}
---

# 📋 Plan: {claimed.stem}

## Steps
- [ ] Review content
- [ ] Take appropriate action
- [ ] Move to /Done

## Source Content

{content[:1000]}
""", encoding="utf-8")
        claim.release_to_done(claimed)
        count += 1
        print(f"  ☁️  [general] Plan created: {plan_name}")

    return count


def run_once() -> int:
    """Single processing pass across all domains."""
    total = 0
    for domain in CLOUD_DOMAINS:
        total += process_domain(domain)
    total += process_general()

    # Abandon stale claims (older than 4 hours)
    claim.abandon_stale(NEEDS_ACTION_DIR, max_age_hours=4)

    return total


def cloud_loop() -> None:
    """Continuous cloud agent loop."""
    print(f"\n☁️  Cloud Agent — Started ({now_local_iso()})")
    print(f"    Mode: {AGENT_MODE} | DRY_RUN: {DRY_RUN}")
    print(f"    Domains: {', '.join(CLOUD_DOMAINS)}")
    print(f"    Loop interval: {LOOP_INTERVAL}s\n")

    # Signal that cloud is online
    write_signal("cloud_online", {"mode": AGENT_MODE, "domains": CLOUD_DOMAINS})

    iteration = 0
    while True:
        iteration += 1
        processed = run_once()
        if processed > 0:
            print(f"  ☁️  Iteration {iteration}: processed {processed} tasks")
            write_update("Cloud Processing", f"Processed {processed} tasks at {now_local_iso()}")
        time.sleep(LOOP_INTERVAL)


def show_status() -> None:
    """Show cloud agent status."""
    print(f"\n☁️  Cloud Agent Status — {now_local_iso()}")
    print(f"    Mode: {AGENT_MODE}")
    print(f"    DRY_RUN: {DRY_RUN}")
    print(f"\n    Domain Queues:")
    for domain in CLOUD_DOMAINS + ["general"]:
        d = NEEDS_ACTION_DIR / domain
        count = len([f for f in d.iterdir() if f.is_file() and not f.name.startswith(".")]) if d.exists() else 0
        print(f"      {domain:<15} {count} pending")
    print(f"\n    In Progress:")
    for f in claim.list_claimed():
        print(f"      ⏳ {f.name}")
    if not claim.list_claimed():
        print(f"      (none)")


if __name__ == "__main__":
    if "--status" in sys.argv:
        show_status()
    elif "--once" in sys.argv:
        processed = run_once()
        print(f"☁️  Cloud Agent: processed {processed} tasks")
    else:
        cloud_loop()
