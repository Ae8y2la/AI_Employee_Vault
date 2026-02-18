# 🏗️ AI Employee Vault — System Architecture

> **Version:** Gold Tier v1.0  
> **Last Updated:** 2026-02-18  
> **Author:** AI Employee System (auto-generated)

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

---

## 2. Layered Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR LAYER                          │
│  orchestrator.py — Process manager, watchdog, health checks        │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ manages
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
┌───────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  PERCEPTION   │  │     REASONING       │  │      ACTION         │
│  (Watchers)   │  │     (Brain)         │  │      (MCP)          │
├───────────────┤  ├─────────────────────┤  ├─────────────────────┤
│ gmail_watcher │  │ reasoning_loop.py   │  │ mcp_email_server    │
│ whatsapp_     │  │ task_router.py      │  │ mcp_social_server   │
│   watcher     │  │ audit_agent.py      │  │ mcp_calendar_server │
│ inbox_watcher │  │ briefing_generator  │  │ mcp_odoo_server     │
└───────┬───────┘  └──────────┬──────────┘  │ mcp_browser_server  │
        │                     │             └──────────┬──────────┘
        ▼                     ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          VAULT (File System)                       │
├──────────┬────────────┬────────┬──────────────┬──────────┬─────────┤
│ /Inbox   │/Needs_Action│ /Done │/Pending_     │/Approved │ /Logs   │
│          │            │        │ Approval     │          │         │
└──────────┴────────────┴────────┴──────────────┴──────────┴─────────┘
```

---

## 3. Data Flow — Lifecycle of a Task

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
                             │  reasoning_loop.py reads
                    ┌────────▼────────┐
             ③      │  Plan_*.md      │    Generated execution plan
                    │  created in     │    with checklist
                    │  /Needs_Action/ │
                    └────────┬────────┘
                             │  if sensitive action...
                    ┌────────▼──────────────┐
             ④      │ /Pending_Approval/    │    Needs human sign-off
                    └────────┬──────────────┘
                             │  human moves file
                    ┌────────▼────────┐
             ⑤      │   /Approved/    │    Human confirmed
                    └────────┬────────┘
                             │  hitl_approval.py executes
                    ┌────────▼────────┐
             ⑥      │    /Done/       │    Completed & archived
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   /Logs/        │    JSON audit trail
                    │   YYYY-MM-DD    │
                    └─────────────────┘
```

### State Transitions

| From | To | Trigger | Agent |
|---|---|---|---|
| External | `/Inbox/` | New email/message/file | `gmail_watcher`, `whatsapp_watcher`, manual |
| `/Inbox/` | `/Needs_Action/` | Keyword classification | `task_router.py` |
| `/Needs_Action/` | `Plan_*.md` created | Reasoning + planning | `reasoning_loop.py` |
| `/Needs_Action/` | `/Pending_Approval/` | Sensitive action detected | `reasoning_loop.py` |
| `/Pending_Approval/` | `/Approved/` | **Human moves file** | Manual (HITL) |
| `/Approved/` | `/Done/` | Action executed | `hitl_approval.py` |
| `/Needs_Action/` | `/Done/` | Non-sensitive task completed | `reasoning_loop.py` |

---

## 4. Component Deep Dive

### 4.1 Perception Layer (Watchers)

All watchers inherit from `BaseWatcher` (Template Method pattern):

```python
class BaseWatcher(ABC):
    POLL_INTERVAL: int = 30

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def poll(self) -> list[dict]: ...

    def create_action_file(self, item: dict) -> Path:
        # Creates .md in /Needs_Action with YAML frontmatter
```

| Watcher | Source | Detection Method | Dependencies |
|---|---|---|---|
| `inbox_watcher.py` | Local filesystem | File hash polling | stdlib |
| `gmail_watcher.py` | Gmail API | Unread + keyword filter | `google-api-python-client` |
| `whatsapp_watcher.py` | WhatsApp Web | Playwright DOM scraping | `playwright` |

**Key Design Decision:** Watchers write *files*, not database entries. This means:
- Every detection is visible in Obsidian
- No database to corrupt or migrate
- Any folder sync tool (OneDrive, Dropbox) works as replication

### 4.2 Reasoning Layer

**`task_router.py`** — Rule-based classifier
- Keyword matching against predefined categories
- Moves files from `/Inbox/` → `/Needs_Action/` or `/Done/`
- Handles filename collisions with timestamps

**`reasoning_loop.py`** — Plan generator
- Reads files in `/Needs_Action/`
- Extracts YAML frontmatter for metadata (priority, source, type)
- Creates `Plan_*.md` files with actionable checklists
- **Ralph Wiggum Stop Hook:** Continues looping until `/Needs_Action/` is empty

```python
def ralph_wiggum_check() -> bool:
    """'I'm still doing something!' — keeps going until done."""
    actionable = [f for f in NEEDS_ACTION_DIR.iterdir()
                  if f.is_file() and not f.name.startswith((".", "Plan_"))]
    return len(actionable) > 0
```

**`audit_agent.py`** — Business auditor
- Scans for stale tasks (>3 days), stuck approvals (>1 day)
- Checks log errors and agent restart frequency
- Generates risk-scored audit reports (0-100)

**`briefing_generator.py`** — CEO briefings
- Daily: task queue, financials, activity summary
- Weekly: 7-day aggregation, success rates, priorities

### 4.3 Action Layer (MCP Servers)

All MCP servers follow the same pattern:

```
stdin (JSON-RPC) → parse → route to tool → execute → stdout (JSON-RPC)
```

| Server | Tools | Safety |
|---|---|---|
| `mcp_email_server.py` | `send_email`, `draft_email` | DRY_RUN, rate limit |
| `mcp_social_server.py` | `post_linkedin`, `post_twitter`, `post_facebook`, `post_instagram`, `draft_social` | DRY_RUN, HITL for posts |
| `mcp_calendar_server.py` | `create_event`, `list_upcoming`, `schedule_task_reminder` | DRY_RUN |
| `mcp_odoo_server.py` | `get_bank_balance`, `get_unpaid_invoices`, `get_profit_loss_summary`, `create_accounting_note` | DRY_RUN, offline fallback |
| `mcp_browser_server.py` | `navigate_and_extract`, `take_screenshot`, `fill_form` | DRY_RUN, headless |

### 4.4 Security Layer

**HITL Approval Gate (`hitl_approval.py`):**
```
/Pending_Approval/APPROVAL_REQUIRED_*.md  →  [Human reviews]
                                          →  Moves to /Approved/
                                          →  hitl_approval.py detects
                                          →  Executes action
                                          →  Moves to /Done/
```

**Rate Limiter (token bucket):**
```python
class RateLimiter:
    def allow(self) -> bool:
        # Max N actions per minute, sliding window
```

### 4.5 Infrastructure

**`orchestrator.py`** — Process manager
- Launches agents as subprocesses
- Watchdog health check every 30s
- Auto-restart on crash (up to 5 attempts)
- Crash diagnosis from stderr
- Graceful shutdown on Ctrl+C

**`action_logger.py`** — Audit trail
- Daily JSON files: `/Logs/YYYY-MM-DD.json`
- Every action: timestamp, type, actor, target, status, approval

**`config.py`** — Central configuration
- Loads `.env` file (no `python-dotenv` dependency)
- All paths, credentials, operational settings
- Never overrides existing environment variables

---

## 5. Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DEFENSE IN DEPTH                         │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: DRY_RUN=true          All external actions mocked │
│ Layer 2: Rate Limiting         5 actions/minute max        │
│ Layer 3: HITL Approval         Human sign-off required     │
│ Layer 4: .env Credentials      Never in vault or code      │
│ Layer 5: .gitignore            .env, credentials.json out  │
│ Layer 6: Watchdog Limits       Max 5 restarts per agent    │
│ Layer 7: Graceful Degradation  Queue on failure, don't crash│
│ Layer 8: Audit Logging         Every action → JSON log     │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. File Naming Conventions

| Pattern | Location | Created By |
|---|---|---|
| `*.md` | `/Inbox/` | External / manual |
| `*.md` | `/Needs_Action/` | task_router, watchers |
| `Plan_*.md` | `/Needs_Action/` | reasoning_loop |
| `APPROVAL_REQUIRED_*.md` | `/Pending_Approval/` | reasoning_loop |
| `YYYY-MM-DD.json` | `/Logs/` | action_logger |
| `Briefing_YYYY-MM-DD.md` | vault root | briefing_generator |
| `Weekly_Briefing_*.md` | vault root | briefing_generator |
| `Audit_YYYY-MM-DD.md` | vault root | audit_agent |

---

## 7. Extensibility Points

### Adding a New Watcher
```python
from base_watcher import BaseWatcher

class SlackWatcher(BaseWatcher):
    @property
    def name(self) -> str:
        return "slack_watcher"

    def poll(self) -> list[dict]:
        # Your polling logic here
        return [{"title": "...", "content": "...", "priority": "normal"}]
```

### Adding a New MCP Tool
Add to any MCP server's `TOOLS` list and `TOOL_MAP` dict:
```python
TOOLS.append({"name": "new_tool", "description": "...", "inputSchema": {...}})
TOOL_MAP["new_tool"] = your_function
```

### Adding a New Agent to Orchestrator
Add entry to `AGENTS_FULL` in `orchestrator.py`:
```python
{"name": "slack_watcher", "script": "slack_watcher.py",
 "description": "Slack channel monitor", "required": False, "group": "watcher"}
```

---

> *Architecture document auto-generated by AI Employee System — Gold Tier v1.0*
