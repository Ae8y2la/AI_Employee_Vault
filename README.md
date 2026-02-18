# 🤖 AI Employee Vault

> **An autonomous, file-driven AI assistant system built on Obsidian — from inbox to execution, with human oversight at every step.**

[![Tier](https://img.shields.io/badge/Tier-⚡%20Platinum-blueviolet?style=for-the-badge)]()
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)]()
[![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge)]()

---

## 👤 Created By

**Aeyla Naseer**  
📧 GitHub: [@Ae8y2la](https://github.com/Ae8y2la)

---

## 🧠 What Is This?

The **AI Employee Vault** is a fully autonomous AI agent system that operates as your personal digital employee. It monitors your email, messages, and files — triages incoming work, generates execution plans, drafts replies, and takes action — all while keeping a human in the loop for sensitive decisions.

Built entirely on **Obsidian-compatible markdown files**, every state change is a file move between folders. No hidden databases, no black boxes — just folders you can see, browse, and control.

### 💡 The Core Idea

```
📧 Email arrives → 🤖 AI triages → 📋 Plan created → 👤 Human approves → ⚡ AI executes → ✅ Done
```

---

## ⚡ Tier Progression

| Tier | Features |
|---|---|
| 🥉 **Bronze** | Vault structure, base watchers, inbox monitoring |
| 🥈 **Silver** | Reasoning loop, HITL approvals, task routing, MCP email |
| 🥇 **Gold** | 5 MCP servers, auditing, CEO briefings, social media, Odoo accounting |
| ⚡ **Platinum** | Cloud + Local split architecture, claim-by-move, Git sync, cloud deployment |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     CLOUD VM (24/7 Always-On)                    │
│  ☁️  cloud_agent — Email triage, social drafts, accounting       │
│  🔄  sync_manager — Git-based vault synchronization              │
│  📧  gmail_watcher — Email monitoring via Gmail API              │
│  🧠  reasoning_loop — Plan generation + Ralph Wiggum Stop Hook   │
├──────────────────────────────────────────────────────────────────┤
│                    ↕️  Git Sync (vault only)                      │
│                    🔒  Secrets NEVER sync                        │
├──────────────────────────────────────────────────────────────────┤
│                     LOCAL MACHINE (On-Demand)                    │
│  🏠  local_agent — Approvals + final execution                   │
│  📱  whatsapp_watcher — WhatsApp monitoring (LOCAL-ONLY)         │
│  ✅  hitl_approval — Human-in-the-loop gate                      │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
External Source ──▶ /Inbox/ ──▶ /Needs_Action/ ──▶ Plan_*.md
                                                      │
                                     ┌────────────────┘
                                     ▼
                              /Pending_Approval/
                                     │
                              👤 Human approves
                                     │
                                     ▼
                               /Approved/ ──▶ AI Executes ──▶ /Done/ ✅
```

---

## 📂 Project Structure

```
AI_Employee_Vault/
├── ai-employee/
│   ├── Agents/                    # 🤖 All AI logic (24 scripts)
│   │   ├── config.py              # Central configuration
│   │   ├── orchestrator.py        # Process manager (multi-mode)
│   │   ├── cloud_agent.py         # ☁️  Cloud executive (Platinum)
│   │   ├── local_agent.py         # 🏠  Local controller (Platinum)
│   │   ├── claim_manager.py       # 🔒  Claim-by-move anti-collision
│   │   ├── sync_manager.py        # 🔄  Git-based vault sync
│   │   ├── inbox_watcher.py       # 📥  File system watcher
│   │   ├── gmail_watcher.py       # 📧  Gmail API watcher
│   │   ├── whatsapp_watcher.py    # 📱  WhatsApp Web watcher
│   │   ├── task_router.py         # 🔀  Rule-based classifier
│   │   ├── reasoning_loop.py      # 🧠  Plan generator
│   │   ├── hitl_approval.py       # ✅  Human approval gate
│   │   ├── audit_agent.py         # 📋  Autonomous auditor
│   │   ├── briefing_generator.py  # 📊  CEO briefings
│   │   ├── mcp_email_server.py    # 📧  Email MCP
│   │   ├── mcp_social_server.py   # 📣  Social media MCP
│   │   ├── mcp_calendar_server.py # 📅  Calendar MCP
│   │   ├── mcp_odoo_server.py     # 💰  Accounting MCP
│   │   ├── mcp_browser_server.py  # 🌐  Browser automation MCP
│   │   └── deploy_cloud.sh        # 🚀  Cloud VM deployment
│   │
│   ├── Inbox/                     # Raw incoming items
│   ├── Needs_Action/              # Triaged tasks (by domain)
│   │   ├── email/
│   │   ├── social/
│   │   ├── accounting/
│   │   ├── calendar/
│   │   └── general/
│   ├── Plans/                     # Execution plans (by domain)
│   ├── Pending_Approval/          # Awaiting human sign-off
│   ├── In_Progress/               # Claimed tasks (anti-collision)
│   │   ├── cloud_agent/
│   │   └── local_agent/
│   ├── Approved/                  # Human-approved actions
│   ├── Done/                      # Completed & archived
│   ├── Accounting/                # Financial records
│   ├── Logs/                      # Daily JSON audit logs
│   ├── Updates/                   # Cloud → Local updates
│   ├── Signals/                   # Cloud → Local signals
│   │
│   ├── Dashboard.md               # System status dashboard
│   ├── ARCHITECTURE.md            # Technical architecture doc
│   ├── LESSONS_LEARNED.md         # Development lessons
│   └── Company_Handbook.md        # Company context
│
├── .gitignore                     # Protects secrets
└── README.md                      # This file
```

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/Ae8y2la/AI_Employee_Vault.git
cd AI_Employee_Vault/ai-employee
```

### 2. Set up environment
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\Activate.ps1  # Windows

# Install dependencies
pip install google-auth google-auth-oauthlib google-api-python-client playwright
```

### 3. Configure credentials
```bash
cp .env.template .env
# Edit .env with your API keys and credentials
```

### 4. Run the system
```bash
# Standalone mode (all agents on one machine)
python Agents/orchestrator.py

# Or split mode:
python Agents/orchestrator.py --cloud    # On cloud VM
python Agents/orchestrator.py --local    # On local machine

# Minimal mode (core agents only)
python Agents/orchestrator.py --minimal
```

### 5. Test the pipeline
Drop any `.md` file into the `Inbox/` folder and watch it flow through the system!

---

## 🤖 Agent Skills (15 Total)

### Perception (3 skills)
| Skill | Agent | Description |
|---|---|---|
| Email Monitoring | `gmail_watcher.py` | Gmail API polling for priority emails |
| Message Monitoring | `whatsapp_watcher.py` | WhatsApp Web scraping via Playwright |
| File Watching | `inbox_watcher.py` | Local filesystem polling with hash detection |

### Reasoning (3 skills)
| Skill | Agent | Description |
|---|---|---|
| Task Classification | `task_router.py` | Keyword-based rule engine for routing |
| Plan Generation | `reasoning_loop.py` | Creates Plan_*.md with checklists |
| Audit Analysis | `audit_agent.py` | Risk-scored vault health audits |

### Action (5 skills — via MCP servers)
| Skill | Agent | Description |
|---|---|---|
| Email Actions | `mcp_email_server.py` | Send/draft emails via SMTP |
| Social Publishing | `mcp_social_server.py` | LinkedIn, Twitter/X, Facebook, Instagram |
| Calendar Management | `mcp_calendar_server.py` | Google Calendar events & reminders |
| Accounting | `mcp_odoo_server.py` | Odoo ERP integration (invoices, P&L) |
| Browser Automation | `mcp_browser_server.py` | Playwright-based web automation |

### Control (2 skills)
| Skill | Agent | Description |
|---|---|---|
| HITL Approval | `hitl_approval.py` | Human-in-the-loop approval gate |
| Process Management | `orchestrator.py` | Watchdog, health checks, auto-restart |

### Reporting (2 skills)
| Skill | Agent | Description |
|---|---|---|
| Daily Briefing | `briefing_generator.py` | Financial + task summary for CEO |
| Weekly Briefing | `briefing_generator.py` | 7-day aggregation and trends |

---

## 🔐 Security

The AI Employee is designed with **8 layers of defense**:

| Layer | Protection |
|---|---|
| 1. **DRY_RUN** | All external actions simulated by default |
| 2. **Rate Limiting** | Max 5 actions/minute across all agents |
| 3. **HITL Approval** | Human sign-off required for sensitive ops |
| 4. **Credential Isolation** | `.env` files never committed or synced |
| 5. **Cloud/Local Split** | Banking & WhatsApp = local-only |
| 6. **Claim-by-Move** | Prevents double-work between agents |
| 7. **Watchdog Limits** | Max 5 restarts per crashed agent |
| 8. **Audit Logging** | Every action → JSON audit trail |

---

## 🌐 Cloud Deployment

Deploy the always-on Cloud Agent to a VM (Oracle Cloud Free Tier works):

```bash
# On your cloud VM:
scp Agents/deploy_cloud.sh user@your-vm:~/
ssh user@your-vm 'chmod +x deploy_cloud.sh && ./deploy_cloud.sh'
```

This creates `systemd` services for:
- `ai-employee-cloud` — Cloud Agent (24/7)
- `ai-employee-sync` — Vault Git Sync

---

## 📊 Key Design Decisions

1. **File-First State Machine** — Every state change is a `.md` file move between folders. Observable, debuggable, and Obsidian-compatible.

2. **Graceful Degradation** — Missing credentials = demo mode, not crashes. The system runs immediately on first setup.

3. **Ralph Wiggum Stop Hook** — The reasoning loop continues processing until the task queue is empty. Named for clarity and memorability.

4. **Stdlib-First** — Core system uses only Python standard library. External libraries required only for specific integrations.

5. **Draft-Only Cloud** — Cloud never sends, posts, or pays. All execution requires local human approval.

---

## 📝 Documentation

| Document | Description |
|---|---|
| [`ARCHITECTURE.md`](ai-employee/ARCHITECTURE.md) | Full system architecture with diagrams |
| [`LESSONS_LEARNED.md`](ai-employee/LESSONS_LEARNED.md) | 7 key lessons from development |
| [`Agents/README.md`](ai-employee/Agents/README.md) | Complete Agent Skills reference |
| [`Dashboard.md`](ai-employee/Dashboard.md) | Live system status dashboard |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

Built with:
- **Python 3.10+** — Core language
- **Obsidian** — Vault interface
- **Google APIs** — Gmail & Calendar integration
- **MCP Protocol** — Agent-tool communication
- **Playwright** — Browser automation

---

<p align="center">
  <b>Built with ❤️ by Aeyla Naseer</b><br>
  <i>AI Employee Vault — Your autonomous digital workforce</i>
</p>
