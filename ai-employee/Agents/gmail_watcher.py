"""
Gmail Watcher — Monitors Gmail for Urgent / Unread Messages
=============================================================
Uses the Gmail API (OAuth2) to poll for new unread messages.
Creates .md action files in /Needs_Action for each urgent message.

Prerequisites:
    pip install google-auth google-auth-oauthlib google-api-python-client

Setup:
    1. Create OAuth2 credentials in Google Cloud Console.
    2. Set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN in .env
    3. Run:  python Agents/gmail_watcher.py --once       (single scan)
             python Agents/gmail_watcher.py              (continuous)
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

try:
    from Agents.config import (
        GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN,
        GMAIL_USER_EMAIL, DRY_RUN, AGENTS_DIR, now_iso,
    )
    from Agents.base_watcher import BaseWatcher
    from Agents.action_logger import log_action
except ImportError:
    from config import (
        GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN,
        GMAIL_USER_EMAIL, DRY_RUN, AGENTS_DIR, now_iso,
    )
    from base_watcher import BaseWatcher
    from action_logger import log_action


# ── Seen-messages persistence ──────────────────────────────────────────────
SEEN_FILE = AGENTS_DIR / "gmail_seen.json"

def _load_seen_ids() -> set[str]:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()

def _save_seen_ids(ids: set[str]) -> None:
    SEEN_FILE.write_text(json.dumps(list(ids)), encoding="utf-8")


# ── Priority detection ─────────────────────────────────────────────────────
URGENT_KEYWORDS = [
    "urgent", "asap", "critical", "emergency", "deadline",
    "overdue", "immediately", "action required",
]

def _detect_priority(subject: str, snippet: str) -> str:
    text = (subject + " " + snippet).lower()
    for kw in URGENT_KEYWORDS:
        if kw in text:
            return "urgent"
    return "normal"


# ── Gmail Watcher ──────────────────────────────────────────────────────────
class GmailWatcher(BaseWatcher):
    """Polls Gmail for unread messages and creates action files."""

    POLL_INTERVAL = 60  # 1 minute between checks

    @property
    def name(self) -> str:
        return "gmail_watcher"

    def setup(self) -> None:
        """Verify credentials are available."""
        if not all([GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN]):
            print(
                "⚠️  Gmail credentials not configured.\n"
                "   Set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN in .env\n"
                "   Running in DEMO mode — will simulate empty inbox.\n"
            )
            self._demo_mode = True
        else:
            self._demo_mode = False

    def _get_gmail_service(self):
        """Build Gmail API service using OAuth2 refresh token."""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials(
                token=None,
                refresh_token=GMAIL_REFRESH_TOKEN,
                client_id=GMAIL_CLIENT_ID,
                client_secret=GMAIL_CLIENT_SECRET,
                token_uri="https://oauth2.googleapis.com/token",
            )
            return build("gmail", "v1", credentials=creds)
        except ImportError:
            print(
                "⚠️  google-auth / google-api-python-client not installed.\n"
                "   Run: pip install google-auth google-auth-oauthlib google-api-python-client"
            )
            return None

    def poll(self) -> list[dict]:
        """Check Gmail for unread messages."""
        if getattr(self, "_demo_mode", True):
            return []  # safe fallback

        service = self._get_gmail_service()
        if service is None:
            return []

        seen_ids = _load_seen_ids()
        new_items = []

        try:
            results = service.users().messages().list(
                userId="me", q="is:unread", maxResults=10
            ).execute()

            messages = results.get("messages", [])
            for msg_stub in messages:
                msg_id = msg_stub["id"]
                if msg_id in seen_ids:
                    continue

                msg = service.users().messages().get(
                    userId="me", id=msg_id, format="metadata",
                    metadataHeaders=["Subject", "From"],
                ).execute()

                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                subject = headers.get("Subject", "(no subject)")
                sender = headers.get("From", "unknown")
                snippet = msg.get("snippet", "")

                priority = _detect_priority(subject, snippet)

                new_items.append({
                    "title": subject,
                    "body": f"**Snippet:** {snippet}",
                    "source": sender,
                    "priority": priority,
                    "gmail_id": msg_id,
                })

                seen_ids.add(msg_id)

            _save_seen_ids(seen_ids)

        except Exception as e:
            print(f"  ⚠️  Gmail API error: {e}")
            log_action(
                action_type="watcher_error",
                actor=self.name,
                target="gmail_api",
                description=str(e),
                status="failed",
            )

        return new_items


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    watcher = GmailWatcher()
    watcher.setup()
    if "--once" in sys.argv:
        watcher.run_once()
    else:
        watcher.watch_loop()
