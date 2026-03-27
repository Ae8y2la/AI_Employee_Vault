# 📝 AI Employee Vault — Lessons Learned

> **Version:** Platinum Tier v2.0  
> **Last Updated:** 2026-03-27  
> **Author:** Aeyla Naseer

---

## Lesson 1: File-First State Machine Design

**Pattern:** Every state change is a `.md` file move between folders.

**Why it works:**
- Files are observable — open the vault in Obsidian and see everything
- No database to corrupt or migrate
- Any sync tool (Git, OneDrive, Dropbox) works as replication
- Debugging is trivial — just look at the filesystem

**Implementation:**
```
/Inbox/ → /Needs_Action/ → /Pending_Approval/ → /Approved/ → /Done/
```

Each transition is a physical `shutil.move()`. If a process crashes mid-move, the file stays in its previous location — automatically safe.

---

## Lesson 2: The BaseWatcher ABC Pattern

**Pattern:** All perception is implemented as Agent Skills inheriting from `BaseWatcher`.

**Why it matters:**
- Uniform interface: `check_for_updates()` + `create_action_file()`
- New watchers (Slack, Telegram, RSS) take 20 lines to implement
- The `run()` loop with error handling is inherited, not rewritten

**The pattern:**
```python
class BaseWatcher(ABC):
    def __init__(self, vault_path: str, check_interval: int = 60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / 'Needs_Action'
        self.check_interval = check_interval
        
    @abstractmethod
    def check_for_updates(self) -> list: pass
    
    @abstractmethod
    def create_action_file(self, item) -> Path: pass
    
    def run(self):
        while True:
            items = self.check_for_updates()
            for item in items:
                self.create_action_file(item)
            time.sleep(self.check_interval)
```

**Key insight:** Watchers write files, not database entries. Every detection is visible in Obsidian.

---

## Lesson 3: DRY_RUN as Default Safety Net

**Pattern:** All external actions are simulated by default (`DRY_RUN=true`).

**Why it's critical:**
- First-time users can run the entire system safely
- Testing never accidentally sends real emails or payments
- Production switch is a single `.env` change: `DRY_RUN=false`

**Applies to:**
- Email sending (SMTP)
- Social media posting
- Payment/banking actions
- Calendar event creation
- Browser form submissions

---

## Lesson 4: Graceful Degradation Over Hard Failures

**Pattern:** Missing credentials = demo mode, not crashes.

**Examples:**
```python
# gmail_watcher.py
def setup(self):
    if not all([GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN]):
        self._demo_mode = True  # runs, but returns empty results
```

```python
# mcp_odoo_server.py
if not ODOO_URL:
    return {"status": "offline", "data": "Odoo not configured"}
```

**Why:** A system that crashes on missing config is useless on first install. A system that degrades gracefully is immediately useful and builds trust.

---

## Lesson 5: Ralph Wiggum Stop Hook

**Pattern:** Named reasoning loop termination condition — "I'm still doing something!"

```python
def ralph_wiggum_check() -> bool:
    """Keeps iterating until /Needs_Action/ is empty."""
    actionable = [f for f in NEEDS_ACTION_DIR.iterdir()
                  if f.is_file() and not f.name.startswith(('.', 'Plan_'))]
    return len(actionable) > 0
```

**Why it's named:** A memorable name makes the pattern instantly recognizable in code reviews and conversations. "The Ralph Wiggum check is failing" is much clearer than "the loop termination predicate."

---

## Lesson 6: Human-in-the-Loop (HITL) via File Moves

**Pattern:** Approval = moving a file from `/Pending_Approval/` to `/Approved/`.

**Why files, not buttons:**
- Works in any file manager (Obsidian, Explorer, terminal)
- No web server, no API, no authentication needed
- The approval is the file's location — observable and auditable
- Rejection = move to `/Done/` (archived without execution)

**HITL flow:**
```
reasoning_loop creates → APPROVAL_REQUIRED_Payment_Client_A.md
                         in /Pending_Approval/

human reviews in Obsidian → moves to /Approved/

hitl_approval.py detects → executes action via MCP
                         → moves to /Done/
                         → logs everything
```

---

## Lesson 7: OAuth2 Is Always Harder Than Expected

**What happened:** Getting a valid Gmail refresh token required:
1. Google Cloud Console project setup
2. OAuth2 consent screen configuration
3. Desktop app credential type (not web)
4. `http://localhost` redirect URI (no port)
5. Manual URL copy-paste flow (OOB deprecated)

**Solution:** Created `gmail_auth.py` helper that:
- Opens browser for consent
- Catches redirect on localhost
- Exchanges code for refresh token
- Auto-saves to `.env`

**Lesson:** Always build auth helper scripts. Users won't read OAuth2 docs.

---

## Lesson 8: Agent Skills as Composable Units

**Pattern:** All AI functionality is implemented as composable Agent Skills, not monolithic scripts.

**Skill categories:**
| Category | Skills | Responsibility |
|---|---|---|
| Perception | 3 watchers | Sense external changes |
| Reasoning | 4 agents | Think, plan, audit |
| Action | 5 MCP servers | Execute via protocols |
| Control | 2 agents | Approve, manage processes |

**Benefits:**
- Each skill is independently testable (`--once` flag)
- Skills can be composed: watcher → router → planner → executor
- New skills follow established patterns (BaseWatcher, MCP template)
- The orchestrator manages skill lifecycle without knowing internals

---

## Lesson 9: Claim-by-Move Prevents Double-Work

**Pattern:** When Cloud and Local agents both process the vault, use atomic file moves as locks.

```python
class ClaimManager:
    def claim(self, source_path: Path) -> Path | None:
        if self.is_claimed_by_anyone(filename):
            return None  # already taken
        shutil.move(source, self.claim_dir / filename)  # atomic claim
        return dest
```

**Why not database locks:** Files are the state machine. Using a separate locking mechanism (database, Redis) would violate the file-first principle and add a dependency. Moving a file IS the lock.

---

## Lesson 10: Stdlib-First, Libraries Second

**Core system dependencies:** Zero. Python 3.10+ stdlib only.

**Optional libraries (only for specific integrations):**
- `google-auth` + `google-api-python-client` — Gmail API only
- `playwright` — WhatsApp Web only
- `smtplib` — Already in stdlib

**Why:** The system runs on any machine with Python installed. No `pip install` needed for core functionality. Missing libraries = graceful degradation to demo mode.

---

## Summary: The Golden Rules

1. **File-first.** Every state change is a file move.
2. **Skill-based.** All AI is an Agent Skill with a standard interface.
3. **Safe by default.** DRY_RUN=true, HITL for sensitive ops.
4. **Degrade gracefully.** Demo mode > crash.
5. **Name your patterns.** "Ralph Wiggum" beats "loop_check_fn".
6. **Claim-by-move.** Files are locks.
7. **Stdlib-first.** External deps are optional.
8. **Log everything.** Every action → JSON audit trail.
9. **Observable.** If you can't see it in Obsidian, it doesn't exist.
10. **Build auth helpers.** Nobody reads OAuth2 docs.

---

> *Lessons Learned — Platinum Tier v2.0 — Created by Aeyla Naseer*
