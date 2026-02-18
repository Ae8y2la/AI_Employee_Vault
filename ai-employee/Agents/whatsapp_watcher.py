"""
WhatsApp Watcher — Monitors WhatsApp Web for Keyword Messages
================================================================
Uses Playwright to monitor WhatsApp Web for messages containing
actionable keywords (urgent, invoice, payment, help, etc.).

Prerequisites:
    pip install playwright
    python -m playwright install chromium

Setup:
    1. Run once to scan QR code:  python Agents/whatsapp_watcher.py --setup
    2. After QR scan, set WHATSAPP_SESSION_SAVED=true in .env
    3. Run:  python Agents/whatsapp_watcher.py --once    (single scan)
             python Agents/whatsapp_watcher.py           (continuous)

Note: First run opens a visible browser for QR scanning. Subsequent runs
      use saved session data and can run headless.
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime, timezone

try:
    from Agents.config import DRY_RUN, AGENTS_DIR, now_iso
    from Agents.base_watcher import BaseWatcher
    from Agents.action_logger import log_action
except ImportError:
    from config import DRY_RUN, AGENTS_DIR, now_iso
    from base_watcher import BaseWatcher
    from action_logger import log_action


# ── Configuration ──────────────────────────────────────────────────────────
SESSION_DIR = AGENTS_DIR / "whatsapp_session"
SEEN_FILE = AGENTS_DIR / "whatsapp_seen.json"

ACTION_KEYWORDS = [
    "urgent", "invoice", "payment", "help", "asap",
    "deadline", "overdue", "action required", "emergency",
    "transfer", "receipt", "approved", "rejected",
]

PRIORITY_KEYWORDS = {
    "urgent": "urgent",
    "emergency": "urgent",
    "asap": "urgent",
    "deadline": "urgent",
    "overdue": "urgent",
    "invoice": "normal",
    "payment": "normal",
    "help": "normal",
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
    for kw, priority in PRIORITY_KEYWORDS.items():
        if kw in lower:
            return priority
    return "normal"


def _has_keywords(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in ACTION_KEYWORDS)


# ── WhatsApp Watcher ──────────────────────────────────────────────────────
class WhatsAppWatcher(BaseWatcher):
    """
    Monitors WhatsApp Web via Playwright for actionable messages.
    """

    POLL_INTERVAL = 45  # seconds between scans

    @property
    def name(self) -> str:
        return "whatsapp_watcher"

    def setup(self) -> None:
        """Check Playwright availability."""
        self._browser = None
        self._context = None
        self._page = None
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
        """Launch Playwright browser with persistent context."""
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        SESSION_DIR.mkdir(parents=True, exist_ok=True)

        self._context = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        self._page.goto("https://web.whatsapp.com", timeout=60000)

        # Wait for chats to load (or QR code page)
        try:
            self._page.wait_for_selector(
                'div[aria-label="Chat list"], canvas[aria-label="Scan this QR code to link a device!"]',
                timeout=30000,
            )
        except Exception:
            print("  ⏳  Waiting for WhatsApp Web to load...")

    def _extract_unread_messages(self) -> list[dict]:
        """Scrape unread messages from WhatsApp Web."""
        messages = []

        try:
            # Find unread chat indicators
            unread_chats = self._page.query_selector_all(
                'span[aria-label*="unread message"]'
            )

            for badge in unread_chats[:10]:  # limit to 10 chats per scan
                try:
                    # Navigate to the parent chat element and click
                    chat_el = badge.evaluate_handle(
                        "el => el.closest('[data-testid=\"cell-frame-container\"]')"
                    )
                    if not chat_el:
                        continue

                    # Get contact name
                    name_el = chat_el.as_element().query_selector(
                        'span[dir="auto"][title]'
                    )
                    contact = name_el.get_attribute("title") if name_el else "Unknown"

                    # Get preview text
                    preview_el = chat_el.as_element().query_selector(
                        'span[dir="ltr"].ggj6brxn, span[dir="ltr"]'
                    )
                    preview = preview_el.inner_text() if preview_el else ""

                    # Only capture messages with actionable keywords
                    if _has_keywords(preview) or _has_keywords(contact):
                        msg_hash = f"{contact}:{preview[:50]}:{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
                        messages.append({
                            "title": f"WhatsApp from {contact}",
                            "body": preview,
                            "source": f"whatsapp:{contact}",
                            "priority": _detect_priority(preview),
                            "hash": msg_hash,
                        })
                except Exception:
                    continue  # skip individual chat errors

        except Exception as e:
            print(f"  ⚠️  WhatsApp scrape error: {e}")
            log_action(
                action_type="watcher_error",
                actor=self.name,
                target="whatsapp_web",
                description=str(e),
                status="failed",
            )

        return messages

    def poll(self) -> list[dict]:
        """Check WhatsApp Web for new actionable messages."""
        if not self._playwright_available:
            return []

        if self._page is None:
            try:
                self._launch_browser(headless=True)
            except Exception as e:
                print(f"  ⚠️  Failed to launch browser: {e}")
                return []

        seen = _load_seen()
        raw_messages = self._extract_unread_messages()

        new_items = []
        for msg in raw_messages:
            if msg["hash"] not in seen:
                new_items.append(msg)
                seen.add(msg["hash"])

        _save_seen(seen)
        return new_items

    def teardown(self) -> None:
        """Close browser resources."""
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
        if hasattr(self, "_pw") and self._pw:
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
            watcher.watch_loop()
