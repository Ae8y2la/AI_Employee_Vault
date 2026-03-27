# gmail_watcher.py
"""
Gmail Watcher — Comms Watcher for Email (Perception Layer)
============================================================
Monitors Gmail via OAuth2 API for unread important messages and saves
new urgent messages as .md files in /Needs_Action/.

Part of the Perception → Reasoning → Action architecture:
- Perception: This watcher polls Gmail for 'is:unread is:important'
- Handoff: Creates EMAIL_{id}.md in /Needs_Action for Claude to process
- Wakes up immediately when machine starts

Prerequisites:
    pip install google-auth google-auth-oauthlib google-api-python-client

Setup:
    1. Create OAuth2 credentials in Google Cloud Console
    2. Save to Agents/credentials.json
    3. Run: python Agents/gmail_auth.py (one-time token setup)
    4. Or set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN in .env
    5. Run: python Agents/gmail_watcher.py           (continuous)
           python Agents/gmail_watcher.py --once    (single scan)
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone

try:
    from Agents.config import (
        GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN,
        GMAIL_USER_EMAIL, DRY_RUN, AGENTS_DIR, NEEDS_ACTION_DIR, VAULT_ROOT,
        now_iso, now_local_iso,
    )
    from Agents.base_watcher import BaseWatcher
    from Agents.action_logger import log_action
except ImportError:
    from config import (
        GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN,
        GMAIL_USER_EMAIL, DRY_RUN, AGENTS_DIR, NEEDS_ACTION_DIR, VAULT_ROOT,
        now_iso, now_local_iso,
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


# ── Gmail Watcher ──────────────────────────────────────────────────────────
class GmailWatcher(BaseWatcher):
    """
    Polls Gmail for unread important/urgent messages.
    Uses google.oauth2.credentials + googleapiclient for API access.
    Falls back to demo mode if credentials are not configured.
    """

    def __init__(self, vault_path: str = None, credentials_path: str = None):
        super().__init__(vault_path or str(VAULT_ROOT), check_interval=120)
        self.credentials_path = credentials_path or str(AGENTS_DIR / "credentials.json")
        self.processed_ids = _load_seen_ids()
        self.creds = None
        self.service = None
        self._demo_mode = True

    def setup(self) -> None:
        """Initialize Google API credentials and build service."""
        # Try credentials.json (standard Google format) first
        creds_file = Path(self.credentials_path)
        if creds_file.exists():
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build

                # Load token.json if it exists (from gmail_auth.py)
                token_file = AGENTS_DIR / "token.json"
                if token_file.exists():
                    self.creds = Credentials.from_authorized_user_file(
                        str(token_file),
                        scopes=[
                            'https://www.googleapis.com/auth/gmail.readonly',
                            'https://www.googleapis.com/auth/gmail.modify',
                        ]
                    )
                    self.service = build('gmail', 'v1', credentials=self.creds)
                    self._demo_mode = False
                    print("  ✅  Gmail: Authenticated via token.json")
                    return
            except Exception as e:
                print(f"  ⚠️  Gmail: token.json auth failed: {e}")

        # Fall back to .env refresh token
        if all([GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN]):
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build

                self.creds = Credentials(
                    token=None,
                    refresh_token=GMAIL_REFRESH_TOKEN,
                    client_id=GMAIL_CLIENT_ID,
                    client_secret=GMAIL_CLIENT_SECRET,
                    token_uri="https://oauth2.googleapis.com/token",
                )
                self.service = build('gmail', 'v1', credentials=self.creds)
                self._demo_mode = False
                print("  ✅  Gmail: Authenticated via .env refresh token")
                return
            except ImportError:
                print(
                    "⚠️  google-auth / google-api-python-client not installed.\n"
                    "   Run: pip install google-auth google-auth-oauthlib google-api-python-client"
                )
            except Exception as e:
                print(f"  ⚠️  Gmail: .env auth failed: {e}")

        print(
            "⚠️  Gmail credentials not configured.\n"
            "   Set up via: python Agents/gmail_auth.py\n"
            "   Or set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN in .env\n"
            "   Running in DEMO mode — will simulate empty inbox.\n"
        )
        self._demo_mode = True

    def check_for_updates(self) -> list:
        """
        Check Gmail for unread important messages.
        Returns list of new message dicts not yet processed.
        """
        if self._demo_mode or self.service is None:
            return []

        try:
            results = self.service.users().messages().list(
                userId='me', q='is:unread is:important', maxResults=10
            ).execute()
            messages = results.get('messages', [])
            return [m for m in messages if m['id'] not in self.processed_ids]
        except Exception as e:
            self.logger.error(f"Gmail API list error: {e}")
            log_action(
                action_type="watcher_error",
                actor="gmail_watcher",
                target="gmail_api",
                description=str(e),
                status="failed",
            )
            return []

    def create_action_file(self, message) -> Path:
        """
        Fetch full message details and create EMAIL_{id}.md in /Needs_Action/.
        """
        msg_id = message['id']

        try:
            msg = self.service.users().messages().get(
                userId='me', id=msg_id, format='metadata',
                metadataHeaders=['Subject', 'From'],
            ).execute()

            # Extract headers
            headers = {h['name']: h['value']
                       for h in msg.get('payload', {}).get('headers', [])}

            sender = headers.get('From', 'Unknown')
            subject = headers.get('Subject', 'No Subject')
            snippet = msg.get('snippet', '')
            received = datetime.now().isoformat()

            # Detect priority from content
            priority = 'normal'
            urgent_kws = ['urgent', 'asap', 'critical', 'emergency',
                          'deadline', 'overdue', 'immediately', 'action required']
            text = (subject + ' ' + snippet).lower()
            for kw in urgent_kws:
                if kw in text:
                    priority = 'high'
                    break

            content = f'''---
type: email
from: {sender}
subject: {subject}
received: {received}
priority: {priority}
status: pending
---

# ✉️ {subject}

**From:** {sender}
**Priority:** {priority}
**Received:** {received}

---

## Email Content

{snippet}

---

## Suggested Actions
- [ ] Reply to sender
- [ ] Forward to relevant party
- [ ] Archive after processing
'''
            filepath = self.needs_action / f'EMAIL_{msg_id}.md'
            filepath.write_text(content, encoding='utf-8')

            self.processed_ids.add(msg_id)
            _save_seen_ids(self.processed_ids)

            log_action(
                action_type="email_detected",
                actor="gmail_watcher",
                target=filepath.name,
                description=f"Email from {sender}: {subject}",
                status="success",
            )
            return filepath

        except Exception as e:
            self.logger.error(f"Gmail fetch error for {msg_id}: {e}")
            # Create a fallback file
            filepath = self.needs_action / f'EMAIL_{msg_id}.md'
            filepath.write_text(f"---\ntype: email\nstatus: fetch_error\n---\n\n# Email {msg_id}\n\nFailed to fetch: {e}\n", encoding='utf-8')
            self.processed_ids.add(msg_id)
            _save_seen_ids(self.processed_ids)
            return filepath


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    watcher = GmailWatcher()
    watcher.setup()
    if "--once" in sys.argv:
        watcher.run_once()
    else:
        watcher.run()
