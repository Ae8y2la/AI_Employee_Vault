# 🏢 AI Employee Dashboard — Platinum Tier

> **Status:** ⚡ PLATINUM — Cloud + Local Split Architecture  
> **Mode:** `AGENT_MODE` configurable (cloud / local / standalone)  
> **Last Updated:** 2026-02-18T20:08:52+05:00  
> **DRY_RUN:** true (safe mode)

---

## 🏗️ Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CLOUD VM (24/7)                              │
│  ☁️ cloud_agent.py — Email triage, social drafts, accounting drafts │
│  🔄 sync_manager.py — Git-based vault sync                         │
│  📥 inbox_watcher.py — File detection                              │
│  📧 gmail_watcher.py — Email monitoring                            │
│  🔀 task_router.py — Classification                                │
│  🧠 reasoning_loop.py — Plan generation                            │
│  📋 audit_agent.py — Autonomous auditor                            │
├──────────────────────────────────────────────────────────────────────┤
│                   ↕️ Git Sync (vault files only)                     │
│                   🔒 Secrets NEVER sync                              │
├──────────────────────────────────────────────────────────────────────┤
│                      LOCAL MACHINE (on-demand)                      │
│  🏠 local_agent.py — Approvals + final execution                   │
│  🔄 sync_manager.py — Git-based vault sync                         │
│  📱 whatsapp_watcher.py — WhatsApp (LOCAL-ONLY)                    │
│  ✅ hitl_approval.py — Human-in-the-loop                            │
│  📥 inbox_watcher.py — File detection                              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 📊 System Status

| Component | Status | Mode |
|---|---|---|
| ☁️ Cloud Agent | 🟡 Ready | Draft-only |
| 🏠 Local Agent | 🟡 Ready | Approval + execute |
| 🔄 Sync Manager | 🟡 Ready | Git-based |
| 📥 Inbox Watcher | 🟢 Active | Polling 30s |
| 🔀 Task Router | 🟢 Active | Keyword rules |
| 🧠 Reasoning Loop | 🟢 Active | Ralph Wiggum Hook |
| ✅ HITL Approval | 🟢 Active | File-move gate |
| 📧 Gmail Watcher | 🟡 Needs credentials | OAuth2 |
| 📱 WhatsApp | 🔴 Local-only setup | Playwright |
| 📋 Audit Agent | 🟢 Active | Risk-scored |
| 📊 Briefing Gen | 🟢 Active | Daily + Weekly |

---

## 🔐 Security Matrix — Cloud vs Local

| Resource | Cloud VM | Local Machine |
|---|---|---|
| Gmail API tokens | ✅ Read-only | ✅ Full access |
| WhatsApp session | ❌ NEVER | ✅ Local-only |
| Banking credentials | ❌ NEVER | ✅ Local-only |
| Payment execution | ❌ NEVER | ✅ With HITL |
| Social media posting | ❌ Draft only | ✅ With HITL |
| Email sending | ❌ Draft only | ✅ With HITL |
| Odoo posting | ❌ Draft only | ✅ With HITL |
| Vault .md files | ✅ Read/write | ✅ Read/write |
| .env file | 🔒 Cloud-only | 🔒 Local-only |
| credentials.json | 🔒 Cloud-only | 🔒 Local-only |

---

## 📂 Domain-Specific Folders (Platinum)

```
Needs_Action/
├── email/          ← Cloud triages, creates drafts
├── social/         ← Cloud creates post drafts  
├── accounting/     ← Cloud creates accounting drafts
├── calendar/       ← Cloud creates event plans
└── general/        ← General tasks

Plans/
├── email/          ← Email action plans
├── social/         ← Social campaigns
├── accounting/     ← Financial plans
├── calendar/       ← Event plans
└── general/        ← General plans

Pending_Approval/
├── email/          ← Draft replies → Local approves → sends
├── social/         ← Draft posts → Local approves → publishes
├── accounting/     ← Draft entries → Local approves → posts
├── calendar/       ← Event proposals → Local approves → creates
└── general/        ← General approvals

In_Progress/
├── cloud_agent/    ← Tasks claimed by Cloud
└── local_agent/    ← Tasks claimed by Local

Updates/             ← Cloud writes status updates here
Signals/             ← Cloud→Local signals (JSON)
```

---

## 🔄 Data Flow — Platinum Split

```
📧 Email arrives                  ☁️  CLOUD VM
    │                             (always-on, 24/7)
    ▼
┌──────────────┐
│ gmail_watcher │──▶ /Needs_Action/email/
└──────────────┘           │
                           ▼
                    ┌──────────────┐
                    │ cloud_agent  │──▶ /Pending_Approval/email/
                    └──────────────┘     DRAFT_REPLY_*.md
                           │
                    ┌──────┴──────┐
                    │  Git Sync   │
                    └──────┬──────┘
                           │
                           ▼           🏠  LOCAL MACHINE
                    ┌──────────────┐    (when user is present)
                    │ User reviews │
                    │ in Obsidian  │
                    └──────┬───────┘
                           │ moves to /Approved/email/
                           ▼
                    ┌──────────────┐
                    │ local_agent  │──▶ Executes send_email via MCP
                    └──────────────┘     Moves to /Done/
                           │
                    ┌──────┴──────┐
                    │  Git Sync   │──▶ Cloud sees completion
                    └─────────────┘
```

---

## 🛡️ Claim-by-Move Rule

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

## 📦 Complete File Tree

```
ai-employee/
├── .env                          # 🔒 Secrets (never synced)
├── .env.template                 # Template for new deployments
├── ARCHITECTURE.md               # System architecture doc
├── LESSONS_LEARNED.md            # Development lessons
├── Dashboard.md                  # This file (Local single-writer)
├── Company_Handbook.md           # Company context
├── mcp_config.json               # Claude Code MCP config
│
├── Agents/                       # All AI logic
│   ├── README.md                 # Agent Skills reference
│   ├── config.py                 # Central configuration
│   ├── action_logger.py          # Structured JSON logging
│   ├── base_watcher.py           # Abstract watcher template
│   ├── claim_manager.py          # ⭐ Claim-by-move (Platinum)
│   │
│   ├── cloud_agent.py            # ⭐ Cloud executive (Platinum)
│   ├── local_agent.py            # ⭐ Local controller (Platinum)
│   ├── sync_manager.py           # ⭐ Git sync (Platinum)
│   ├── deploy_cloud.sh           # ⭐ Cloud VM deploy (Platinum)
│   │
│   ├── inbox_watcher.py          # File system watcher
│   ├── gmail_watcher.py          # Gmail API watcher
│   ├── whatsapp_watcher.py       # WhatsApp watcher (LOCAL-ONLY)
│   ├── task_router.py            # Rule-based classifier
│   ├── reasoning_loop.py         # Plan generator + Ralph Wiggum
│   ├── hitl_approval.py          # Human approval gate
│   ├── audit_agent.py            # Autonomous auditor
│   ├── briefing_generator.py     # CEO briefings
│   ├── orchestrator.py           # Process manager (multi-mode)
│   │
│   ├── mcp_email_server.py       # Email MCP
│   ├── mcp_social_server.py      # Social media MCP
│   ├── mcp_calendar_server.py    # Calendar MCP
│   ├── mcp_odoo_server.py        # Accounting MCP
│   ├── mcp_browser_server.py     # Browser MCP
│   │
│   ├── gmail_auth.py             # OAuth2 setup helper
│   ├── credentials.json          # 🔒 OAuth2 creds (never synced)
│   └── token.json                # 🔒 OAuth2 token (never synced)
│
├── Inbox/                        # Raw incoming items
├── Needs_Action/                 # Triaged tasks
│   ├── email/
│   ├── social/
│   ├── accounting/
│   ├── calendar/
│   └── general/
├── Plans/                        # ⭐ Domain-specific plans
│   ├── email/
│   ├── social/
│   ├── accounting/
│   ├── calendar/
│   └── general/
├── Pending_Approval/             # Awaiting human review
│   ├── email/
│   ├── social/
│   ├── accounting/
│   ├── calendar/
│   └── general/
├── In_Progress/                  # ⭐ Claimed tasks
│   ├── cloud_agent/
│   └── local_agent/
├── Approved/                     # Human-approved tasks
├── Done/                         # Completed & archived
├── Accounting/                   # Financial records
├── Projects/                     # Project files
├── Updates/                      # ⭐ Cloud→Local updates
├── Signals/                      # ⭐ Cloud→Local signals
└── Logs/                         # Daily JSON audit logs
```

---

## 🚀 Quick Commands

### Standalone Mode (Gold Tier Compatible)
```bash
python Agents/orchestrator.py              # all agents
python Agents/orchestrator.py --minimal    # core agents only
```

### Platinum Split Mode
```bash
# On Cloud VM:
python Agents/orchestrator.py --cloud      # cloud agents

# On Local Machine:
python Agents/orchestrator.py --local      # local agents
```

### Individual Agents
```bash
python Agents/cloud_agent.py --status      # cloud status
python Agents/local_agent.py --status      # local status
python Agents/sync_manager.py --status     # sync status
python Agents/sync_manager.py --sync       # manual sync
python Agents/audit_agent.py              # run audit
python Agents/briefing_generator.py       # daily briefing
```

### Cloud Deployment
```bash
scp Agents/deploy_cloud.sh user@vm:~/
ssh user@vm 'chmod +x deploy_cloud.sh && ./deploy_cloud.sh'
```

---

## 📈 Tier Progression

| Tier | Features | Status |
|---|---|---|
| 🥉 Bronze | Vault structure, base watchers, inbox monitor | ✅ Complete |
| 🥈 Silver | Reasoning loop, HITL, MCP email, task router | ✅ Complete |
| 🥇 Gold | 5 MCP servers, audit, briefings, social, Odoo | ✅ Complete |
| ⚡ **Platinum** | Cloud+Local split, claim-by-move, git sync, Odoo deploy | ✅ **Active** |

---

> *Dashboard.md — single-writer: Local agent only | Updated 2026-02-18*
