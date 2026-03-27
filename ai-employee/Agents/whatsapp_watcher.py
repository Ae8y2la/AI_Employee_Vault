# whatsapp_watcher.py
"""
WhatsApp Watcher — Comms Watcher (Playwright-based, Perception Layer)
========================================================================
Monitors WhatsApp Web via Playwright browser automation for messages
containing actionable keywords (urgent, invoice, payment, help, etc.)

Note: This uses WhatsApp Web automation. Be aware of WhatsApp's terms of service.

Part of the Perception → Reasoning → Action architecture:
- Perception: Scrapes WhatsApp Web for unread keyword matches
- Handoff: Creates .md files in /Needs_Action for Claude to process
- LOCAL-ONLY: WhatsApp session data never stored on Cloud

Prerequisites:
    pip install playwright
    python -m playwright install chromium

Setup:
    1. First run (QR scan):  python Agents/whatsapp_watcher.py --setup
    2. After QR scan, set WHATSAPP_SESSION_SAVED=true in .env
    3. Run:  python Agents/whatsapp_watcher.py --once    (single scan)
             python Agents/whatsapp_watcher.py           (continuous)
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone

try:
    from Agents.config import DRY_RUN, AGENTS_DIR, VAULT_ROOT, NEEDS_ACTION_DIR, now_iso, now_local_iso
    from Agents.base_watcher import BaseWatcher
    from Agents.action_logger import log_action
except ImportError:
    from config import DRY_RUN, AGENTS_DIR, VAULT_ROOT, NEEDS_ACTION_DIR, now_iso, now_local_iso
    from base_watcher import BaseWatcher
    from action_logger import log_action


# ── Configuration ──────────────────────────────────────────────────────────
SESSION_DIR = AGENTS_DIR / "whatsapp_session"
SEEN_FILE = AGENTS_DIR / "whatsapp_seen.json"

# Keywords that trigger action file creation
KEYWORDS = ['urgent', 'asap', 'invoice', 'payment', 'help',
            'deadline', 'overdue', 'action required', 'emergency',
            'transfer', 'receipt', 'approved', 'rejected']

PRIORITY_MAP = {
    'urgent': 'urgent', 'emergency': 'urgent', 'asap': 'urgent',
    'deadline': 'urgent', 'overdue': 'urgent',
    'invoice': 'normal', 'payment': 'normal', 'help': 'normal',
    'transfer': 'normal', 'receipt': 'normal',
    'approved': 'normal', 'rejected': 'normal',
}


def _load_seen() -> set[str]:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()


def _save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(json.dumps(list(seen)), encoding="utf-8")


def _detect_priority(text: str) -> str:
    lower = text.lower()
    for kw, priority in PRIORITY_MAP.items():
        if kw in lower:
            return priority
    return "normal"


# ── WhatsApp Watcher ──────────────────────────────────────────────────────
class WhatsAppWatcher(BaseWatcher):
    """
    Monitors WhatsApp Web via Playwright for messages containing
    actionable keywords. Uses persistent browser context to maintain
    the WhatsApp Web session across restarts.
    """

    def __init__(self, vault_path: str = None, session_path: str = None):
        super().__init__(vault_path or str(VAULT_ROOT), check_interval=30)
        self.session_path = Path(session_path) if session_path else SESSION_DIR
        self.keywords = KEYWORDS
        self._pw = None
        self._browser = None
        self._page = None
        self._playwright_available = False
        self._seen = _load_seen()

    def setup(self) -> None:
        """Check Playwright availability."""
        try:
            import playwright  # noqa: F401
            self._playwright_available = True
        except ImportError:
            print(
                "⚠️  Playwright not installed.\n"
                "   Run: pip install playwright && python -m playwright install chromium\n"
                "   Running in DEMO mode — no messages will be scanned.\n"
            )
            self._playwright_available = False

    def _launch_browser(self, headless: bool = True):
        """Launch Playwright browser with persistent context for WhatsApp Web."""
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self.session_path.mkdir(parents=True, exist_ok=True)

        self._browser = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.session_path),
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._page = self._browser.pages[0] if self._browser.pages else self._browser.new_page()
        self._page.goto('https://web.whatsapp.com', timeout=60000)

        # Wait for chat list to load (or QR code page)
        try:
            self._page.wait_for_selector(
                '[data-testid="chat-list"], canvas[aria-label*="Scan"]',
                timeout=30000,
            )
        except Exception:
            print("  ⏳  Waiting for WhatsApp Web to load...")

    def check_for_updates(self) -> list:
        """
        Check WhatsApp Web for unread messages containing keywords.
        Returns list of message dicts with keyword matches.
        """
        if not self._playwright_available:
            return []

        if self._page is None:
            try:
                self._launch_browser(headless=True)
            except Exception as e:
                print(f"  ⚠️  Failed to launch browser: {e}")
                return []

        messages = []
        try:
            # Find unread message indicators
            unread = self._page.query_selector_all('[aria-label*="unread"]')

            for chat in unread[:10]:  # limit to 10 chats per scan
                try:
                    text = chat.inner_text().lower()

                    # Only capture messages with actionable keywords
                    if any(kw in text for kw in self.keywords):
                        # Extract contact name if possible
                        name_el = chat.query_selector('span[dir="auto"][title]')
                        contact = name_el.get_attribute("title") if name_el else "Unknown"

                        # Preview text
                        preview_el = chat.query_selector('span[dir="ltr"]')
                        preview = preview_el.inner_text() if preview_el else text[:200]

                        msg_hash = f"{contact}:{preview[:50]}:{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"

                        if msg_hash not in self._seen:
                            messages.append({
                                'title': f'WhatsApp from {contact}',
                                'body': preview,
                                'source': f'whatsapp:{contact}',
                                'priority': _detect_priority(preview),
                                'type': 'whatsapp_message',
                                'hash': msg_hash,
                                'contact': contact,
                            })
                except Exception:
                    continue  # skip individual chat errors

        except Exception as e:
            self.logger.error(f"WhatsApp scrape error: {e}")
            log_action(
                action_type="watcher_error",
                actor="whatsapp_watcher",
                target="whatsapp_web",
                description=str(e),
                status="failed",
            )

        return messages

    def create_action_file(self, item) -> Path:
        """Create .md file in Needs_Action for a WhatsApp message."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        contact = item.get('contact', 'Unknown')
        safe_contact = "".join(c if c.isalnum() or c in " _-" else "_" for c in contact)[:30]
        filename = f"WHATSAPP_{ts}_{safe_contact}.md"
        filepath = self.needs_action / filename

        priority = item.get('priority', 'normal')
        priority_icon = {"urgent": "🔴", "normal": "🟡", "low": "🟢"}.get(priority, "⚪")

        content = f"""---
type: whatsapp_message
from: {item.get('source', 'unknown')}
contact: {contact}
received: {now_iso()}
priority: {priority}
status: pending
---

# {priority_icon} WhatsApp Message from {contact}

**From:** {item.get('source', 'unknown')}
**Priority:** {priority}
**Time:** {now_local_iso()}

---

## Message Content

{item.get('body', '(no content)')}

---

## Suggested Actions
- [ ] Reply to sender
- [ ] Forward to relevant party
- [ ] Archive after processing

---

> *Auto-generated by whatsapp_watcher*
"""
        filepath.write_text(content, encoding="utf-8")

        # Track as seen
        self._seen.add(item.get('hash', ''))
        _save_seen(self._seen)

        log_action(
            action_type="whatsapp_detected",
            actor="whatsapp_watcher",
            target=filename,
            description=f"WhatsApp from {contact}: {item.get('body', '')[:50]}",
            status="success",
        )
        return filepath

    def teardown(self) -> None:
        """Close browser resources."""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass


# ── Interactive setup ──────────────────────────────────────────────────────
def run_setup():
    """Launch visible browser for QR code scanning."""
    print("📱  WhatsApp Web Setup — QR Code Scan")
    print("   A browser window will open. Scan the QR code with your phone.")
    print("   After scanning, close the browser or press Ctrl+C.\n")

    watcher = WhatsAppWatcher()
    watcher.setup()

    if not watcher._playwright_available:
        return

    watcher._launch_browser(headless=False)
    print("✅  Session saved! Set WHATSAPP_SESSION_SAVED=true in .env")
    input("   Press Enter to close browser...")
    watcher.teardown()


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--setup" in sys.argv:
        run_setup()
    else:
        watcher = WhatsAppWatcher()
        watcher.setup()
        if "--once" in sys.argv:
            watcher.run_once()
        else:
            watcher.run()
