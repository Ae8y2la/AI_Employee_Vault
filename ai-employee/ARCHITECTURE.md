# 🏗️ AI Employee Vault — System Architecture

> **Version:** Platinum Tier v2.0  
> **Last Updated:** 2026-03-27  
> **Author:** Aeyla Naseer

---

## 1. Overview

The AI Employee Vault is an **Obsidian-compatible**, file-driven autonomous agent system. It monitors incoming tasks from multiple channels (email, messaging, filesystem), reasons about them, creates execution plans, and takes actions — all with human oversight.

### Design Philosophy

| Principle | Implementation |
|---|---|
| **File-first** | Every state change is a `.md` file move between folders |
| **Observable** | All state is visible in Obsidian; no hidden databases |
| **Safe by default** | DRY_RUN=true, rate limits, HITL approvals |
| **Graceful degradation** | Missing credentials = demo mode, not crashes |
| **Stdlib-first** | Core system uses only Python stdlib; external libs optional |
| **Agent Skills** | All AI functionality implemented as composable Agent Skills |

---

## 2. Architecture: Perception → Reasoning → Action

The system follows a three-layer architecture where each layer is implemented as composable Agent Skills:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR LAYER                          │
│  orchestrator.py — Process manager, watchdog, health checks        │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ manages
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
┌───────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   A. PERCEPTION   │  │    B. REASONING     │  │     C. ACTION       │
│   (The Watchers)  │  │    (Claude Code)    │  │     (The Hands)     │
├───────────────────┤  ├─────────────────────┤  ├─────────────────────┤
│ gmail_watcher     │  │ task_router.py      │  │ mcp_email_server    │
│ whatsapp_watcher  │  │ reasoning_loop.py   │  │ mcp_social_server   │
│ inbox_watcher     │  │ audit_agent.py      │  │ mcp_calendar_server │
│ (filesystem)      │  │ briefing_generator  │  │ mcp_odoo_server     │
│                   │  │                     │  │ mcp_browser_server  │
│                   │  │                     │  │ hitl_approval.py    │
└───────┬───────────┘  └──────────┬──────────┘  └──────────┬──────────┘
        │                        │                         │
        ▼                        ▼                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          VAULT (File System)                       │
├──────────┬────────────┬────────┬──────────────┬──────────┬─────────┤
│ /Inbox   │/Needs_     │ /Done  │/Pending_     │/Approved │ /Logs   │
│          │ Action     │        │ Approval     │          │         │
└──────────┴────────────┴────────┴──────────────┴──────────┴─────────┘
```

---

## 3. A. Perception (The "Watchers")

Since the system can't "listen" to the internet 24/7, lightweight Python **Sentinel Scripts** run in the background:

- **Comms Watcher (Gmail):** Monitors Gmail via OAuth2 API and saves new urgent messages as `.md` files in `/Needs_Action/`
- **Comms Watcher (WhatsApp):** Monitors WhatsApp Web via Playwright automation and saves keyword-matched messages
- **File System Watcher:** Monitors the `/Inbox/` folder for new file drops and creates metadata files

The system **wakes up immediately when you open your machine** — watchers start polling on launch.

### Core Watcher Pattern

All Watchers follow this abstract base class structure:

```python
# base_watcher.py - Template for all watchers
import time
import logging
from pathlib import Path
from abc import ABC, abstractmethod


class BaseWatcher(ABC):
    def __init__(self, vault_path: str, check_interval: int = 60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / 'Needs_Action'
        self.check_interval = check_interval
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
    def check_for_updates(self) -> list:
        '''Return list of new items to process'''
        pass
    
    @abstractmethod
    def create_action_file(self, item) -> Path:
        '''Create .md file in Needs_Action folder'''
        pass
    
    def run(self):
        self.logger.info(f'Starting {self.__class__.__name__}')
        while True:
            try:
                items = self.check_for_updates()
                for item in items:
                    self.create_action_file(item)
            except Exception as e:
                self.logger.error(f'Error: {e}')
            time.sleep(self.check_interval)
```

### Gmail Watcher Implementation

```python
# gmail_watcher.py
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from base_watcher import BaseWatcher
from datetime import datetime


class GmailWatcher(BaseWatcher):
    def __init__(self, vault_path: str, credentials_path: str):
        super().__init__(vault_path, check_interval=120)
        self.creds = Credentials.from_authorized_user_file(credentials_path)
        self.service = build('gmail', 'v1', credentials=self.creds)
        self.processed_ids = set()
        
    def check_for_updates(self) -> list:
        results = self.service.users().messages().list(
            userId='me', q='is:unread is:important'
        ).execute()
        messages = results.get('messages', [])
        return [m for m in messages if m['id'] not in self.processed_ids]
    
    def create_action_file(self, message) -> Path:
        msg = self.service.users().messages().get(
            userId='me', id=message['id']
        ).execute()
        headers = {h['name']: h['value'] for h in msg['payload']['headers']}
        
        content = f'''---
type: email
from: {headers.get('From', 'Unknown')}
subject: {headers.get('Subject', 'No Subject')}
received: {datetime.now().isoformat()}
priority: high
status: pending
---

## Email Content
{msg.get('snippet', '')}

## Suggested Actions
- [ ] Reply to sender
- [ ] Forward to relevant party
- [ ] Archive after processing
'''
        filepath = self.needs_action / f'EMAIL_{message["id"]}.md'
        filepath.write_text(content)
        self.processed_ids.add(message['id'])
        return filepath
```

### WhatsApp Watcher (Playwright-based)

> **Note:** This uses WhatsApp Web automation. Be aware of WhatsApp's terms of service.

```python
# whatsapp_watcher.py
from playwright.sync_api import sync_playwright
from base_watcher import BaseWatcher
from pathlib import Path


class WhatsAppWatcher(BaseWatcher):
    def __init__(self, vault_path: str, session_path: str):
        super().__init__(vault_path, check_interval=30)
        self.session_path = Path(session_path)
        self.keywords = ['urgent', 'asap', 'invoice', 'payment', 'help']
        
    def check_for_updates(self) -> list:
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                self.session_path, headless=True
            )
            page = browser.pages[0]
            page.goto('https://web.whatsapp.com')
            page.wait_for_selector('[data-testid="chat-list"]')
            
            unread = page.query_selector_all('[aria-label*="unread"]')
            messages = []
            for chat in unread:
                text = chat.inner_text().lower()
                if any(kw in text for kw in self.keywords):
                    messages.append({'text': text, 'chat': chat})
            browser.close()
            return messages
```

### File System Watcher (for local drops)

```python
# inbox_watcher.py (filesystem watcher)
from base_watcher import BaseWatcher
from pathlib import Path
import hashlib


class InboxWatcher(BaseWatcher):
    def __init__(self, vault_path: str):
        super().__init__(vault_path, check_interval=5)
        self.inbox = self.vault_path / 'Inbox'
        self.seen_hashes = {}
        
    def check_for_updates(self) -> list:
        new_items = []
        for entry in self.inbox.iterdir():
            if entry.name.startswith('.') or not entry.is_file():
                continue
            fhash = hashlib.md5(entry.read_bytes()).hexdigest()
            if entry.name not in self.seen_hashes or self.seen_hashes[entry.name] != fhash:
                new_items.append({'file': entry.name, 'path': str(entry), 'hash': fhash})
                self.seen_hashes[entry.name] = fhash
        return new_items
    
    def create_action_file(self, item) -> Path:
        source = Path(item['path'])
        meta_path = self.needs_action / f'FILE_{source.name}'
        meta_path.write_text(f'''---
type: file_drop
original_name: {source.name}
size: {source.stat().st_size}
---

New file dropped for processing.
''')
        return meta_path
```

### Watcher Summary

| Watcher | Source | Detection Method | Keywords | Dependencies |
|---|---|---|---|---|
| `gmail_watcher.py` | Gmail API | `is:unread is:important` | urgent, asap, deadline | `google-api-python-client` |
| `whatsapp_watcher.py` | WhatsApp Web | Playwright DOM scraping | urgent, invoice, payment | `playwright` |
| `inbox_watcher.py` | Local filesystem | File hash polling | (all files) | stdlib only |

**Key Design Decision:** Watchers write *files*, not database entries. This means:
- Every detection is visible in Obsidian
- No database to corrupt or migrate
- Any folder sync tool (OneDrive, Dropbox) works as replication

---

## 4. B. Reasoning (Claude Code / Reasoning Loop)

When the Watcher detects a change, the reasoning layer processes it:

1. **Read:** "Check /Needs_Action and /Accounting."
2. **Think:** "I see a WhatsApp message from a client asking for an invoice and a bank transaction showing a late payment fee."
3. **Plan:** Creates a `Plan.md` in Obsidian with checkboxes for the next steps.

### Task Router

```python
# task_router.py — Rule-based classifier
def classify(content: str) -> str:
    """Classify file content into a target folder."""
    # Check done-keywords first (explicit completion signal)
    for kw in ['completed', 'done', 'resolved', 'closed']:
        if kw in content.lower():
            return "Done"
    # Check action-keywords
    for kw in ['urgent', 'todo', 'action', 'review', 'approve', 'deploy']:
        if kw in content.lower():
            return "Needs_Action"
    return "Inbox"  # keep for manual triage
```

### Reasoning Loop (Plan Generator + Ralph Wiggum Stop Hook)

```python
# reasoning_loop.py
def ralph_wiggum_check() -> bool:
    """'I'm still doing something!' — keeps going until done."""
    actionable = [f for f in NEEDS_ACTION_DIR.iterdir()
                  if f.is_file() and not f.name.startswith(('.', 'Plan_'))]
    return len(actionable) > 0
```

- Reads files in `/Needs_Action/` and `/Accounting/`
- Creates structured `Plan_*.md` files with checklists
- Generates `APPROVAL_REQUIRED_*.md` in `/Pending_Approval/` for sensitive actions
- **Ralph Wiggum Stop Hook:** Continues iterating until task queue is empty

### Audit Agent

- Scans for stale tasks (>3 days), stuck approvals (>1 day)
- Checks log errors and agent restart frequency
- Generates risk-scored audit reports (0-100)

---

## 5. C. Action (The "Hands" — MCP Servers)

Model Context Protocol (MCP) servers are the system's hands for interacting with external systems. Each MCP server exposes specific capabilities that can be invoked.

### Human-in-the-Loop (HITL)

The system writes a file: `APPROVAL_REQUIRED_Payment_Client_A.md`. It will **not** execute the action until you move that file to the `/Approved` folder.

```
/Pending_Approval/APPROVAL_REQUIRED_*.md  →  [Human reviews in Obsidian]
                                          →  Moves to /Approved/
                                          →  hitl_approval.py detects
                                          →  Executes action via MCP
                                          →  Moves to /Done/
```

### Recommended MCP Servers

| Server | Capabilities | Use Case |
|---|---|---|
| `mcp_email_server.py` | `send_email`, `draft_email` | Gmail integration |
| `mcp_social_server.py` | `post_linkedin`, `post_twitter`, `post_facebook`, `post_instagram`, `draft_social` | Social media |
| `mcp_calendar_server.py` | `create_event`, `list_upcoming`, `schedule_task_reminder` | Scheduling |
| `mcp_odoo_server.py` | `get_bank_balance`, `get_unpaid_invoices`, `get_profit_loss_summary` | Accounting |
| `mcp_browser_server.py` | `navigate_and_extract`, `take_screenshot`, `fill_form` | Payment portals |
| `filesystem` (built-in) | Read, write, list files | Vault operations |

### MCP Protocol Pattern

All MCP servers follow the same stdio JSON-RPC pattern:

```
stdin (JSON-RPC) → parse → route to tool → execute → stdout (JSON-RPC)
```

### Safety Controls

| Control | Protection |
|---|---|
| **DRY_RUN** | All external actions mocked by default |
| **Rate Limiting** | Token-bucket: max 5 actions/minute |
| **HITL Approval** | Human sign-off for sends, posts, payments |
| **Credential Isolation** | `.env` files never in vault or code |

---

## 6. Data Flow — Full Task Lifecycle

```
                    ┌─────────────────┐
                    │   EXTERNAL      │
                    │  Gmail / WA /   │
                    │  Manual drop    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
             ①      │    /Inbox/      │    Raw, untriaged
                    └────────┬────────┘
                             │  task_router.py classifies
                    ┌────────▼────────┐
             ②      │ /Needs_Action/  │    Triaged, awaiting work
                    └────────┬────────┘
                             │  reasoning_loop.py reads + thinks + plans
                    ┌────────▼────────┐
             ③      │  Plan_*.md      │    Generated execution plan
                    │  created in     │    with checklist
                    │  /Needs_Action/ │
                    └────────┬────────┘
                             │  if sensitive action...
                    ┌────────▼──────────────┐
             ④      │ /Pending_Approval/    │    HITL: Needs human sign-off
                    └────────┬──────────────┘
                             │  human moves file in Obsidian
                    ┌────────▼────────┐
             ⑤      │   /Approved/    │    Human confirmed
                    └────────┬────────┘
                             │  hitl_approval.py executes via MCP
                    ┌────────▼────────┐
             ⑥      │    /Done/       │    Completed & archived
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   /Logs/        │    JSON audit trail
                    │   YYYY-MM-DD    │
                    └─────────────────┘
```

---

## 7. Cloud + Local Split Architecture (Platinum Tier)

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLOUD VM (24/7)                           │
│  ☁️ cloud_agent.py — Email triage, social drafts, acct drafts   │
│  🔄 sync_manager.py — Git-based vault sync                      │
│  📧 gmail_watcher.py — Email monitoring                         │
│  🧠 reasoning_loop.py — Plan generation                         │
├──────────────────────────────────────────────────────────────────┤
│                   ↕️ Git Sync (vault .md files only)              │
│                   🔒 Secrets (.env, tokens) NEVER sync           │
├──────────────────────────────────────────────────────────────────┤
│                      LOCAL MACHINE (on-demand)                   │
│  🏠 local_agent.py — Approvals + final execution                │
│  📱 whatsapp_watcher.py — WhatsApp (LOCAL-ONLY)                 │
│  ✅ hitl_approval.py — Human-in-the-loop                        │
└──────────────────────────────────────────────────────────────────┘
```

### Security Matrix

| Resource | Cloud VM | Local Machine |
|---|---|---|
| Gmail API (read-only) | ✅ | ✅ |
| WhatsApp session | ❌ NEVER | ✅ Local-only |
| Banking credentials | ❌ NEVER | ✅ Local-only |
| Email sending | ❌ Draft only | ✅ With HITL |
| Social posting | ❌ Draft only | ✅ With HITL |
| Odoo posting | ❌ Draft only | ✅ With HITL |

### Claim-by-Move Rule

Prevents double-work between Cloud and Local agents:

```
1. Agent checks: is file claimed by anyone?
   → /In_Progress/cloud_agent/{file}?
   → /In_Progress/local_agent/{file}?

2. If unclaimed: MOVE file to /In_Progress/{my_name}/
   (atomic claim)

3. Process the file

4. Release: MOVE to destination (/Done, /Pending_Approval)

5. Stale claims (>4h): auto-abandoned back to source
```

---

## 8. Security Architecture (8 Layers of Defense)

```
┌─────────────────────────────────────────────────────────────┐
│                    DEFENSE IN DEPTH                         │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: DRY_RUN=true          All external actions mocked │
│ Layer 2: Rate Limiting         5 actions/minute max        │
│ Layer 3: HITL Approval         Human sign-off required     │
│ Layer 4: .env Credentials      Never in vault or code      │
│ Layer 5: .gitignore            .env, credentials.json out  │
│ Layer 6: Cloud/Local Split     Banking = local-only        │
│ Layer 7: Watchdog Limits       Max 5 restarts per agent    │
│ Layer 8: Audit Logging         Every action → JSON log     │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Agent Skills Reference

All AI functionality is implemented as **Agent Skills**:

### Perception Skills (3)
| Skill | Agent | Input | Output |
|---|---|---|---|
| Email Monitoring | `gmail_watcher.py` | Gmail API | `EMAIL_{id}.md` in `/Needs_Action/` |
| Message Monitoring | `whatsapp_watcher.py` | WhatsApp Web | `WHATSAPP_{ts}.md` in `/Needs_Action/` |
| File Watching | `inbox_watcher.py` | Filesystem | Detection log + metadata |

### Reasoning Skills (4)
| Skill | Agent | Input | Output |
|---|---|---|---|
| Task Classification | `task_router.py` | `/Inbox/*.md` | Files moved to `/Needs_Action/` or `/Done/` |
| Plan Generation | `reasoning_loop.py` | `/Needs_Action/*.md` | `Plan_*.md` with checklists |
| Audit Analysis | `audit_agent.py` | All vault folders | `Audit_YYYY-MM-DD.md` |
| CEO Briefing | `briefing_generator.py` | Logs + vault state | `Briefing_YYYY-MM-DD.md` |

### Action Skills (5 MCP Servers)
| Skill | Agent | Capabilities |
|---|---|---|
| Email Actions | `mcp_email_server.py` | `send_email`, `draft_email` |
| Social Publishing | `mcp_social_server.py` | LinkedIn, Twitter/X, Facebook, Instagram |
| Calendar Management | `mcp_calendar_server.py` | `create_event`, `list_upcoming` |
| Accounting | `mcp_odoo_server.py` | Balance, invoices, P&L |
| Browser Automation | `mcp_browser_server.py` | Navigate, screenshot, fill forms |

### Control Skills (2)
| Skill | Agent | Function |
|---|---|---|
| HITL Approval | `hitl_approval.py` | Human-in-the-loop gate |
| Process Management | `orchestrator.py` | Watchdog, health checks, auto-restart |

---

## 10. Extensibility Points

### Adding a New Watcher

```python
from base_watcher import BaseWatcher

class SlackWatcher(BaseWatcher):
    def __init__(self, vault_path: str):
        super().__init__(vault_path, check_interval=30)
    
    def check_for_updates(self) -> list:
        # Your polling logic here
        return [{'title': '...', 'body': '...', 'source': '...', 'priority': 'normal'}]
    
    def create_action_file(self, item) -> Path:
        filepath = self.needs_action / f'SLACK_{item["title"]}.md'
        filepath.write_text(f'---\ntype: slack\n---\n\n{item["body"]}')
        return filepath
```

### Adding a New MCP Tool

```python
# Add to any MCP server's tool list and handler map:
TOOLS.append({"name": "new_tool", "description": "...", "inputSchema": {...}})
TOOL_MAP["new_tool"] = your_function
```

### Adding a New Agent to Orchestrator

```python
# Add to AGENTS list in orchestrator.py:
{"name": "slack_watcher", "script": "slack_watcher.py",
 "group": "watcher", "required": False}
```

---

## 11. File Naming Conventions

| Pattern | Location | Created By |
|---|---|---|
| `EMAIL_{id}.md` | `/Needs_Action/` | gmail_watcher |
| `WHATSAPP_{ts}_{contact}.md` | `/Needs_Action/` | whatsapp_watcher |
| `FILE_{name}.md` | `/Needs_Action/` | inbox_watcher |
| `Plan_*.md` | `/Needs_Action/` | reasoning_loop |
| `APPROVAL_REQUIRED_*.md` | `/Pending_Approval/` | reasoning_loop |
| `DRAFT_REPLY_*.md` | `/Pending_Approval/email/` | cloud_agent |
| `DRAFT_SOCIAL_*.md` | `/Pending_Approval/social/` | cloud_agent |
| `YYYY-MM-DD.json` | `/Logs/` | action_logger |
| `Briefing_YYYY-MM-DD.md` | vault root | briefing_generator |
| `Audit_YYYY-MM-DD.md` | vault root | audit_agent |

---

> *Architecture document — Platinum Tier v2.0 — Created by Aeyla Naseer*
