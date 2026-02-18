"""
Email MCP Server — Model Context Protocol Server for Email Actions
====================================================================
Lightweight MCP-style server that exposes email capabilities to Claude.
Implements send_email, draft_email, and list_drafts tools.

All actions respect DRY_RUN mode and rate limiting.

MCP Config (add to ~/.config/claude-code/mcp.json):
{
  "mcpServers": {
    "email-mcp": {
      "command": "python",
      "args": ["Agents/mcp_email_server.py"],
      "cwd": "<vault_root>"
    }
  }
}

Usage:
    python Agents/mcp_email_server.py                  # start server (stdio)
    python Agents/mcp_email_server.py --test           # send test email
"""

import sys
import json
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

try:
    from Agents.config import (
        SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
        SMTP_FROM_ADDRESS, DRY_RUN, RATE_LIMIT_ACTIONS_PER_MINUTE,
        DONE_DIR, now_iso, now_local_iso,
    )
    from Agents.action_logger import log_action
except ImportError:
    from config import (
        SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
        SMTP_FROM_ADDRESS, DRY_RUN, RATE_LIMIT_ACTIONS_PER_MINUTE,
        DONE_DIR, now_iso, now_local_iso,
    )
    from action_logger import log_action


# ── Rate limiter ───────────────────────────────────────────────────────────
class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, max_per_minute: int):
        self.max_per_minute = max_per_minute
        self.timestamps: list[float] = []

    def allow(self) -> bool:
        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t < 60]
        if len(self.timestamps) >= self.max_per_minute:
            return False
        self.timestamps.append(now)
        return True

    def wait_time(self) -> float:
        if not self.timestamps:
            return 0
        return max(0, 60 - (time.time() - self.timestamps[0]))


_rate_limiter = RateLimiter(RATE_LIMIT_ACTIONS_PER_MINUTE)


# ── Email actions ──────────────────────────────────────────────────────────
def send_email(
    to: str,
    subject: str,
    body: str,
    html: bool = False,
    cc: Optional[str] = None,
) -> dict:
    """
    Send an email via SMTP.
    Returns a result dict with status and details.
    """
    # Rate limit check
    if not _rate_limiter.allow():
        wait = _rate_limiter.wait_time()
        result = {
            "status": "rate_limited",
            "message": f"Rate limit exceeded. Try again in {wait:.0f}s.",
            "timestamp": now_iso(),
        }
        log_action(
            action_type="email_rate_limited",
            actor="email_mcp",
            target=to,
            description=f"Rate limited: {subject}",
            status="failed",
        )
        return result

    # Dry run check
    if DRY_RUN:
        result = {
            "status": "dry_run",
            "message": f"DRY RUN: Would send to {to}: {subject}",
            "to": to,
            "subject": subject,
            "timestamp": now_iso(),
        }
        log_action(
            action_type="email_sent",
            actor="email_mcp",
            target=to,
            description=f"DRY RUN — {subject}",
            status="dry_run",
        )
        print(f"  🏜️  DRY RUN: Email to {to}: {subject}")
        return result

    # Validate credentials
    if not all([SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_ADDRESS]):
        result = {
            "status": "error",
            "message": "SMTP credentials not configured. Set SMTP_* vars in .env",
            "timestamp": now_iso(),
        }
        log_action(
            action_type="email_failed",
            actor="email_mcp",
            target=to,
            description="Missing SMTP credentials",
            status="failed",
        )
        return result

    # Build message
    msg = MIMEMultipart("alternative") if html else MIMEText(body)
    if html:
        msg.attach(MIMEText(body, "html"))
    msg["From"] = SMTP_FROM_ADDRESS
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc

    # Send
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            recipients = [to] + ([cc] if cc else [])
            server.sendmail(SMTP_FROM_ADDRESS, recipients, msg.as_string())

        result = {
            "status": "sent",
            "message": f"Email sent to {to}: {subject}",
            "to": to,
            "subject": subject,
            "timestamp": now_iso(),
        }
        log_action(
            action_type="email_sent",
            actor="email_mcp",
            target=to,
            description=subject,
            status="success",
        )
        print(f"  ✉️  Email sent to {to}: {subject}")
        return result

    except Exception as e:
        result = {
            "status": "error",
            "message": str(e),
            "timestamp": now_iso(),
        }
        log_action(
            action_type="email_failed",
            actor="email_mcp",
            target=to,
            description=str(e),
            status="failed",
        )
        return result


def draft_email(to: str, subject: str, body: str) -> dict:
    """
    Save an email draft as a .md file in /Done (drafts subfolder).
    Does NOT send — just creates the draft for human review.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    draft_path = DONE_DIR / f"DRAFT_email_{ts}.md"

    content = f"""---
type: email_draft
to: {to}
subject: {subject}
created_at: {now_iso()}
status: draft
---

# ✉️ Email Draft

**To:** {to}
**Subject:** {subject}
**Created:** {now_local_iso()}

---

{body}

---

> *Draft created by email_mcp — review and send manually if needed.*
"""
    draft_path.write_text(content, encoding="utf-8")

    log_action(
        action_type="email_drafted",
        actor="email_mcp",
        target=draft_path.name,
        description=f"Draft for {to}: {subject}",
    )

    return {
        "status": "drafted",
        "path": str(draft_path),
        "timestamp": now_iso(),
    }


# ── MCP Server (stdio protocol) ───────────────────────────────────────────
def handle_mcp_request(request: dict) -> dict:
    """Handle a single MCP tool call."""
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "send_email",
                    "description": "Send an email via SMTP (respects DRY_RUN and rate limits)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email address"},
                            "subject": {"type": "string", "description": "Email subject"},
                            "body": {"type": "string", "description": "Email body text"},
                            "cc": {"type": "string", "description": "CC address (optional)"},
                        },
                        "required": ["to", "subject", "body"],
                    },
                },
                {
                    "name": "draft_email",
                    "description": "Save an email draft as .md file (does NOT send)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string"},
                            "subject": {"type": "string"},
                            "body": {"type": "string"},
                        },
                        "required": ["to", "subject", "body"],
                    },
                },
            ]
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        if tool_name == "send_email":
            result = send_email(**args)
        elif tool_name == "draft_email":
            result = draft_email(**args)
        else:
            result = {"status": "error", "message": f"Unknown tool: {tool_name}"}

        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    return {"error": f"Unknown method: {method}"}


def run_mcp_server():
    """Run as stdio MCP server — reads JSON-RPC from stdin, writes to stdout."""
    print("📧  Email MCP Server started (stdio mode)", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_mcp_request(request)
            response["jsonrpc"] = "2.0"
            response["id"] = request.get("id")
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            err = {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--test" in sys.argv:
        print("📧  Email MCP — Test Mode\n")
        result = send_email(
            to="test@example.com",
            subject="AI Employee Test Email",
            body="This is a test email from the AI Employee system.",
        )
        print(json.dumps(result, indent=2))
    else:
        run_mcp_server()
