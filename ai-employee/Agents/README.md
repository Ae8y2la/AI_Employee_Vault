# 🤖 Agent Skills Reference — Gold Tier

> All AI functionality is implemented as **Agent Skills** — modular, testable,
> documented capabilities that agents can invoke autonomously.

---

## Skill Categories

| Category | Skills | Agents |
|---|---|---|
| 👁️ **Perception** | Email Monitoring, Message Monitoring, File Watching | gmail_watcher, whatsapp_watcher, inbox_watcher |
| 🧠 **Reasoning** | Task Classification, Plan Generation, Audit Analysis | task_router, reasoning_loop, audit_agent |
| ⚡ **Action** | Email, Social Media, Calendar, Accounting, Browser | 5 MCP servers |
| 🔐 **Control** | HITL Approval, Rate Limiting, Process Management | hitl_approval, orchestrator |
| 📊 **Reporting** | Daily Briefing, Weekly Briefing, Audit Report | briefing_generator, audit_agent |

---

## Perception Skills

### SKILL: Email Monitoring
- **Agent:** `gmail_watcher.py`
- **Input:** Gmail API credentials (OAuth2)
- **Output:** `.md` files in `/Needs_Action/` with email content
- **Detection:** Unread messages with priority keywords (urgent, important, asap, invoice, payment)
- **Fallback:** Demo mode generates sample data when credentials missing
- **Config:** `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`

```bash
# Test
python Agents/gmail_watcher.py --once

# Continuous
python Agents/gmail_watcher.py
```

### SKILL: Message Monitoring
- **Agent:** `whatsapp_watcher.py`
- **Input:** WhatsApp Web browser session
- **Output:** `.md` files in `/Needs_Action/` with message content
- **Detection:** Messages containing keywords: urgent, invoice, payment, help, deadline, overdue
- **Fallback:** Demo mode when Playwright not installed
- **Config:** `WHATSAPP_SESSION_SAVED`

```bash
# First-time setup (scan QR)
python Agents/whatsapp_watcher.py --setup

# Continuous
python Agents/whatsapp_watcher.py
```

### SKILL: File Watching
- **Agent:** `inbox_watcher.py`
- **Input:** `/Inbox/` directory
- **Output:** Detects new/modified `.md` files via hash comparison
- **Method:** Polling every 30 seconds with SHA-256 change detection
- **Config:** None (zero-config)

```bash
python Agents/inbox_watcher.py --once
```

---

## Reasoning Skills

### SKILL: Task Classification
- **Agent:** `task_router.py`
- **Input:** Files in `/Inbox/`
- **Output:** Files moved to `/Needs_Action/` (actionable) or `/Done/` (informational)
- **Method:** Keyword-based rule engine
- **Categories:** task, invoice, communication, report, meeting

```bash
python Agents/task_router.py
```

### SKILL: Plan Generation
- **Agent:** `reasoning_loop.py`
- **Input:** Files in `/Needs_Action/`
- **Output:** `Plan_*.md` files with YAML frontmatter, checklists, embedded source
- **Method:** Extracts priority/source from YAML, generates step-by-step plan
- **Loop Control:** Ralph Wiggum Stop Hook — continues until queue empty
- **HITL Trigger:** Creates `APPROVAL_REQUIRED_*.md` in `/Pending_Approval/` for sensitive actions

```bash
# Single pass
python Agents/reasoning_loop.py --once

# Continuous (with Stop Hook)
python Agents/reasoning_loop.py
```

### SKILL: Audit Analysis
- **Agent:** `audit_agent.py`
- **Input:** All vault folders + `/Logs/`
- **Output:** `Audit_YYYY-MM-DD.md` with risk score and recommendations
- **Checks:**
  - Stale tasks (>3 days in `/Needs_Action/`)
  - Stuck approvals (>1 day in `/Pending_Approval/`)
  - Log errors and agent restart frequency
  - Accounting items without plans
  - Folder health (existence, file counts)
- **Risk Score:** 0-100 (🟢 <20, 🟡 <50, 🔴 ≥50)

```bash
# Full audit report
python Agents/audit_agent.py

# Quick summary
python Agents/audit_agent.py --quick
```

---

## Action Skills (MCP Servers)

### SKILL: Email Actions
- **Agent:** `mcp_email_server.py`
- **Tools:**
  - `send_email(to, subject, body)` — Send via SMTP
  - `draft_email(to, subject, body)` — Save as `.md` draft
- **Safety:** DRY_RUN check, rate limit, action logging
- **Protocol:** JSON-RPC over stdio

### SKILL: Social Media Publishing
- **Agent:** `mcp_social_server.py`
- **Tools:**
  - `post_linkedin(text, visibility)` — LinkedIn UGC API
  - `post_twitter(text)` — X/Twitter API v2
  - `post_facebook(message)` — Facebook Graph API
  - `post_instagram(caption, image_url)` — Instagram Graph API
  - `draft_social(platform, text)` — Save draft to vault
- **Safety:** DRY_RUN, rate limit, HITL approval for posts

### SKILL: Calendar Management
- **Agent:** `mcp_calendar_server.py`
- **Tools:**
  - `create_event(summary, start_time, end_time)` — Create Google Calendar event
  - `list_upcoming(max_results)` — List upcoming events
  - `schedule_task_reminder(task, when)` — Schedule reminder (supports `+1h`, `+1d` relative time)
- **Safety:** DRY_RUN, sample data in demo mode

### SKILL: Accounting & Finance
- **Agent:** `mcp_odoo_server.py`
- **Tools:**
  - `get_bank_balance()` — Bank account balance (Odoo or `.env` fallback)
  - `get_unpaid_invoices(type, limit)` — List unpaid invoices
  - `get_profit_loss_summary()` — Revenue vs expenses
  - `create_accounting_note(title, content)` — Save note to `/Accounting/`
- **Integration:** Odoo ERP via XML-RPC
- **Fallback:** Sample data when offline or DRY_RUN

### SKILL: Browser Automation
- **Agent:** `mcp_browser_server.py`
- **Tools:**
  - `navigate_and_extract(url, selector)` — Navigate + extract text
  - `take_screenshot(url, output_name)` — Capture page screenshot
  - `fill_form(url, fields, submit_selector)` — Fill and submit forms
- **Engine:** Playwright (headless Chromium)
- **Safety:** DRY_RUN, action logging

---

## Control Skills

### SKILL: Human-in-the-Loop Approval
- **Agent:** `hitl_approval.py`
- **Workflow:**
  1. Agent creates `APPROVAL_REQUIRED_*.md` in `/Pending_Approval/`
  2. Human reviews in Obsidian
  3. Human moves file to `/Approved/`
  4. `hitl_approval.py` detects, executes action, moves to `/Done/`
- **Supported Actions:** email, social_post, deploy, financial, generic

### SKILL: Process Management
- **Agent:** `orchestrator.py`
- **Capabilities:**
  - Launch all agents as subprocesses
  - Watchdog health check every 30s
  - Auto-restart on crash (max 5 attempts per agent)
  - Crash diagnosis from stderr capture
  - Graceful shutdown on Ctrl+C
  - `--minimal` mode (core agents only)

---

## Reporting Skills

### SKILL: Daily CEO Briefing
- **Agent:** `briefing_generator.py`
- **Output:** `Briefing_YYYY-MM-DD.md`
- **Content:** Financial dashboard, task queue, pending approvals, today's activity, system status

```bash
python Agents/briefing_generator.py
```

### SKILL: Weekly CEO Briefing
- **Agent:** `briefing_generator.py --weekly`
- **Output:** `Weekly_Briefing_YYYY-MM-DD.md`
- **Content:** 7-day aggregation, activity breakdown by type/status, success rate, priorities

```bash
python Agents/briefing_generator.py --weekly
```

### SKILL: Structured Logging
- **Agent:** `action_logger.py`
- **Output:** `/Logs/YYYY-MM-DD.json`
- **Fields:** timestamp, action_type, actor, target, description, approval_status, status

---

## Skill Composition

Skills can be composed to form complete workflows:

```
Email Monitoring ──▶ Task Classification ──▶ Plan Generation
        │                                          │
        │                 ┌────────────────────────┘
        │                 ▼
        │         HITL Approval ──▶ Email Actions
        │                         Social Publishing
        │                         Calendar Management
        │
        └──▶ Daily Briefing ──▶ Structured Logging
```

### Example: Invoice Processing Pipeline
```
1. [Email Monitoring]  →  Detects invoice email
2. [Task Classification]  →  Tags as "invoice", moves to /Needs_Action
3. [Plan Generation]  →  Creates Plan with: review, record, approve, pay
4. [Accounting]  →  Creates note in /Accounting
5. [HITL Approval]  →  Awaits human confirmation
6. [Email Actions]  →  Sends confirmation reply
7. [Structured Logging]  →  Records all steps
```

---

## Adding New Skills

### Checklist for New Skills

- [ ] Implement in `/Agents/` directory
- [ ] Respect `DRY_RUN` flag for external actions
- [ ] Use `action_logger.log_action()` for all operations
- [ ] Add `--test` or `--once` flag for testing
- [ ] Handle missing credentials gracefully (demo/offline mode)
- [ ] Add to orchestrator's `AGENTS_FULL` list if it's a continuous agent
- [ ] Add MCP tool definitions if it's an action skill
- [ ] Update `Dashboard.md` file tree
- [ ] Document in this file

### Skill Template
```python
"""
New Skill — Description
=========================
Usage:
    python Agents/new_skill.py          # continuous
    python Agents/new_skill.py --once   # single pass
    python Agents/new_skill.py --test   # test mode
"""

from config import DRY_RUN, now_iso
from action_logger import log_action

def execute():
    if DRY_RUN:
        log_action("new_skill", "new_agent", "target", "DRY RUN", status="dry_run")
        return {"status": "dry_run"}
    # ... real implementation ...
    log_action("new_skill", "new_agent", "target", "executed", status="success")

if __name__ == "__main__":
    execute()
```

---

> *Agent Skills Reference — AI Employee System Gold Tier v1.0*
