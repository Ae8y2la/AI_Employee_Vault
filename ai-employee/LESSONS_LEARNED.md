# 📝 Lessons Learned — AI Employee Vault

> **Version:** Gold Tier v1.0  
> **Date:** 2026-02-18  
> **Context:** Built incrementally from Bronze → Silver → Gold tier

---

## 1. Architecture Decisions That Paid Off

### 1.1 File-First State Machine
**Decision:** Use folder moves as state transitions instead of a database.

**Why it worked:**
- Every state is **visible in Obsidian** — no hidden state
- Debugging = opening a folder
- No database migrations, no schema versioning
- OneDrive/Git sync gives us free replication and history
- Non-technical users can participate (just move files between folders)

**Trade-off:** Folder operations aren't atomic. We mitigate this with timestamped filenames and collision detection.

---

### 1.2 DRY_RUN by Default
**Decision:** Ship with `DRY_RUN=true` — all external actions are simulated.

**Why it works:**
- Zero risk during development and testing
- Every agent can be tested end-to-end without API keys
- Logs show exactly what *would* happen in production
- Gradual onboarding: test → configure → enable

**Lesson:** Always default to the safest mode. Making users opt-in to danger (set `DRY_RUN=false`) is much better than opt-out.

---

### 1.3 Graceful Degradation
**Decision:** If credentials are missing, run in demo/offline mode — never crash.

**Example:**
```python
# gmail_watcher.py
if not GMAIL_CLIENT_ID:
    print("  ⚠️ Gmail credentials not set — running in demo mode")
    return [{"title": "Demo email", ...}]
```

**Why it works:**
- System starts immediately on first run, before any configuration
- Individual agent failures don't take down the whole system
- Watchdog restarts crashed agents (up to 5 times, then standby)
- Users see the system working before investing in API setup

---

### 1.4 Stdlib-First Dependencies
**Decision:** Core system uses only Python standard library. External libraries required only for specific watchers.

**Result:**
- `config.py` — custom `.env` loader (no `python-dotenv`)
- `action_logger.py` — JSON logging (no `structlog`)
- `mcp_*_server.py` — HTTP via `urllib.request` (no `requests`)
- `mcp_odoo_server.py` — XML-RPC via `xmlrpc.client` (stdlib)

**Why:** Reduces installation friction. `pip install` is only needed for Gmail/WhatsApp watchers and Browser MCP.

---

## 2. Patterns That Emerged

### 2.1 The Ralph Wiggum Stop Hook
**Problem:** How does the reasoning loop know when to stop?

**Solution:** Named after Ralph's habit of continuing long after others have stopped — the loop checks if there's still work to do:

```python
def ralph_wiggum_check() -> bool:
    actionable_files = [f for f in NEEDS_ACTION_DIR.iterdir()
                        if f.is_file() and not f.name.startswith((".", "Plan_"))]
    return len(actionable_files) > 0
```

**Lesson:** An explicit stopping condition prevents both premature termination and infinite loops. Name your patterns — it makes them memorable and easier to discuss.

---

### 2.2 Template Method for Watchers
**Problem:** Multiple watchers share 80% of their logic (polling, file creation, logging).

**Solution:** `BaseWatcher` abstract class:
```
BaseWatcher (abstract)
  ├── poll_interval, logging, .md creation ← shared
  ├── poll() ← abstract, each watcher implements
  └── name ← abstract property
```

**Lesson:** When you see duplicate code across agents, extract a base class. But keep the abstract interface small — just `poll()` and `name`.

---

### 2.3 MCP Server Pattern
**Problem:** Multiple action domains (email, social, calendar, finance, browser) with similar safety requirements.

**Solution:** Every MCP server follows the same structure:
1. Rate limiter (shared token-bucket class)
2. DRY_RUN check before any external call
3. Action logging (every call, success or failure)
4. Stdio JSON-RPC interface
5. `--test` flag for quick verification

**Lesson:** Consistency in interfaces makes the system predictable. A developer who understands one MCP server immediately understands all five.

---

### 2.4 HITL as File Movement
**Problem:** How to implement human approval without building a UI?

**Solution:** Approval = moving a file from `/Pending_Approval/` to `/Approved/`.

**Why it's elegant:**
- Works in any file manager, Obsidian, or command line
- No web server or API needed
- Audit trail is implicit (file modification timestamps)
- Works offline

**Lesson:** The simplest possible interface for human interaction is often a file operation.

---

## 3. Things That Were Harder Than Expected

### 3.1 OAuth2 Token Exchange
**Challenge:** Google's OAuth2 flow requires a local HTTP server to catch the redirect, a browser for consent, and precise redirect URI matching.

**What we learned:**
- Desktop app credentials use `http://localhost` (no port) as redirect URI
- The `google_auth_oauthlib` library's `run_local_server` picks its own port
- If the port doesn't match the redirect URI exactly, the flow fails silently
- Manual code-paste approach is more reliable for automated systems

**Recommendation:** For unattended systems, use a Service Account instead of OAuth2 user consent.

---

### 3.2 Process Management on Windows
**Challenge:** Subprocess management, signal handling, and graceful shutdown differ between Windows and Unix.

**What we learned:**
- `subprocess.CREATE_NO_WINDOW` is Windows-specific — need conditional flag
- `SIGTERM` doesn't exist on Windows — must use `process.terminate()`
- `signal.SIGINT` works on Windows but handlers are limited
- Process stderr reading can block — use non-blocking patterns

**Mitigation:** The orchestrator uses `poll()` instead of `wait()`, with timeout-based graceful shutdown.

---

### 3.3 Rate Limiting Across Multiple Agents
**Challenge:** Each MCP server has its own rate limiter, but they all share the same external API quotas.

**What we learned:**
- Per-server rate limits are simple but not globally coordinated
- For true global rate limiting, you'd need a shared lock file or IPC
- At Gold Tier scale (5 actions/minute default), per-server limits are sufficient

**Future improvement:** Centralized rate limiter via a shared JSON file.

---

## 4. What We'd Do Differently

### 4.1 Use YAML Frontmatter More Consistently
Some early files didn't have frontmatter, making them harder to parse programmatically. **Lesson:** Every `.md` file should start with `---` YAML frontmatter containing `type`, `created_at`, and `status`.

### 4.2 Add a Message Bus
Currently, agents communicate only through files. A lightweight pub/sub (even via a JSON file) would enable:
- Real-time notifications between agents
- Event-driven processing instead of polling
- Faster response times

### 4.3 Schema Validation
We parse `.md` files with manual string parsing. Adding a simple schema validator for frontmatter would catch errors earlier.

### 4.4 Test Suite
The system uses manual `--test` and `--once` flags for testing. A proper `pytest` suite with fixture files would improve reliability.

---

## 5. Performance Characteristics

| Metric | Value | Notes |
|---|---|---|
| Startup time | ~5s | Staggered agent launch |
| Task detection latency | 30s max | Watcher poll interval |
| Plan generation | <1s | File read + write |
| HITL approval | Human-dependent | File move in Obsidian |
| Log write | <10ms | JSON append |
| Memory (orchestrator) | ~50MB | 5 Python subprocesses |
| Disk usage (logs) | ~5KB/day | Grows with activity |

---

## 6. Technology Stack Summary

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.10+ | Cross-platform, stdlib-rich |
| State | Filesystem (`.md` files) | Observable, sync-friendly |
| Config | `.env` + custom loader | No dependencies |
| Logging | JSON files | Machine-readable, greppable |
| External APIs | `urllib.request`, `xmlrpc.client` | stdlib |
| Process mgmt | `subprocess` | stdlib |
| Browser automation | Playwright | WhatsApp, Browser MCP |
| Google APIs | `google-api-python-client` | Gmail, Calendar |
| Interface | Obsidian, File Manager | Zero-install for users |
| MCP Protocol | JSON-RPC over stdio | Claude Code compatible |

---

## 7. Key Takeaways

1. **Files are underrated as a state machine.** Moving files between folders is observable, debuggable, and sync-friendly.

2. **Safety defaults save you.** DRY_RUN=true, rate limits, and HITL together mean the system can't do damage even if there's a bug.

3. **Graceful degradation > hard requirements.** Demo mode when unconfigured beats "please install 15 packages first."

4. **Name your patterns.** "Ralph Wiggum Stop Hook" is easier to discuss and remember than "task queue depletion check."

5. **Consistency in interfaces compounds.** Once you know one MCP server, you know all five.

6. **Start with the folder structure.** The vault layout was decided first, and everything else followed from it.

---

> *Lessons learned auto-documented by AI Employee System — Gold Tier v1.0*
