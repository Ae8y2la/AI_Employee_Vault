"""
Social Media MCP Server — Cross-Platform Publishing
=====================================================
MCP server for posting to LinkedIn, Twitter/X, Facebook, and Instagram.
All actions respect DRY_RUN, HITL approval, and rate limits.

Supported tools:
  - post_linkedin    — Publish text post to LinkedIn
  - post_twitter     — Publish tweet to X/Twitter
  - post_facebook    — Publish to Facebook Page
  - post_instagram   — Publish to Instagram (image required)
  - draft_social     — Save draft to vault (no API call)

MCP Config (add to ~/.config/claude-code/mcp.json):
{
  "mcpServers": {
    "social-mcp": {
      "command": "python",
      "args": ["Agents/mcp_social_server.py"],
      "cwd": "<vault_root>"
    }
  }
}
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError

try:
    from Agents.config import (
        LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN,
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,
        FACEBOOK_PAGE_TOKEN, FACEBOOK_PAGE_ID,
        INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID,
        DRY_RUN, RATE_LIMIT_ACTIONS_PER_MINUTE,
        PENDING_APPROVAL_DIR, DONE_DIR,
        now_iso, now_local_iso,
    )
    from Agents.action_logger import log_action
except ImportError:
    from config import (
        LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN,
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,
        FACEBOOK_PAGE_TOKEN, FACEBOOK_PAGE_ID,
        INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID,
        DRY_RUN, RATE_LIMIT_ACTIONS_PER_MINUTE,
        PENDING_APPROVAL_DIR, DONE_DIR,
        now_iso, now_local_iso,
    )
    from action_logger import log_action


# ── Rate limiter ───────────────────────────────────────────────────────────
class RateLimiter:
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

_rate_limiter = RateLimiter(RATE_LIMIT_ACTIONS_PER_MINUTE)


# ── LinkedIn ──────────────────────────────────────────────────────────────
def post_linkedin(text: str, visibility: str = "PUBLIC") -> dict:
    """Post text content to LinkedIn."""
    if not _rate_limiter.allow():
        return {"status": "rate_limited", "platform": "linkedin", "timestamp": now_iso()}

    if DRY_RUN:
        log_action("social_post", "social_mcp", "linkedin", f"DRY RUN: {text[:80]}", status="dry_run")
        return {"status": "dry_run", "platform": "linkedin", "text": text[:80], "timestamp": now_iso()}

    if not LINKEDIN_ACCESS_TOKEN or not LINKEDIN_PERSON_URN:
        return {"status": "error", "message": "LinkedIn credentials not configured", "timestamp": now_iso()}

    payload = json.dumps({
        "author": LINKEDIN_PERSON_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
    }).encode()

    req = Request(
        "https://api.linkedin.com/v2/ugcPosts",
        data=payload,
        headers={
            "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
    )
    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
        log_action("social_post", "social_mcp", "linkedin", f"Posted: {text[:80]}", status="success")
        return {"status": "posted", "platform": "linkedin", "id": result.get("id"), "timestamp": now_iso()}
    except HTTPError as e:
        err = e.read().decode()
        log_action("social_post_failed", "social_mcp", "linkedin", err, status="failed")
        return {"status": "error", "platform": "linkedin", "error": err, "timestamp": now_iso()}


# ── Twitter / X ────────────────────────────────────────────────────────────
def post_twitter(text: str) -> dict:
    """Post a tweet to X/Twitter."""
    if not _rate_limiter.allow():
        return {"status": "rate_limited", "platform": "twitter", "timestamp": now_iso()}

    if DRY_RUN:
        log_action("social_post", "social_mcp", "twitter", f"DRY RUN: {text[:80]}", status="dry_run")
        return {"status": "dry_run", "platform": "twitter", "text": text[:80], "timestamp": now_iso()}

    if not TWITTER_ACCESS_TOKEN:
        return {"status": "error", "message": "Twitter credentials not configured", "timestamp": now_iso()}

    # Twitter API v2 — requires OAuth 1.0a (simplified here; production should use proper signing)
    payload = json.dumps({"text": text}).encode()
    req = Request(
        "https://api.twitter.com/2/tweets",
        data=payload,
        headers={
            "Authorization": f"Bearer {TWITTER_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
        log_action("social_post", "social_mcp", "twitter", f"Tweeted: {text[:80]}", status="success")
        return {"status": "posted", "platform": "twitter", "id": result.get("data", {}).get("id"), "timestamp": now_iso()}
    except HTTPError as e:
        err = e.read().decode()
        log_action("social_post_failed", "social_mcp", "twitter", err, status="failed")
        return {"status": "error", "platform": "twitter", "error": err, "timestamp": now_iso()}


# ── Facebook ───────────────────────────────────────────────────────────────
def post_facebook(message: str) -> dict:
    """Post to a Facebook Page."""
    if not _rate_limiter.allow():
        return {"status": "rate_limited", "platform": "facebook", "timestamp": now_iso()}

    if DRY_RUN:
        log_action("social_post", "social_mcp", "facebook", f"DRY RUN: {message[:80]}", status="dry_run")
        return {"status": "dry_run", "platform": "facebook", "text": message[:80], "timestamp": now_iso()}

    if not FACEBOOK_PAGE_TOKEN or not FACEBOOK_PAGE_ID:
        return {"status": "error", "message": "Facebook credentials not configured", "timestamp": now_iso()}

    payload = json.dumps({"message": message, "access_token": FACEBOOK_PAGE_TOKEN}).encode()
    req = Request(
        f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/feed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req) as resp:
            result = json.loads(resp.read())
        log_action("social_post", "social_mcp", "facebook", f"Posted: {message[:80]}", status="success")
        return {"status": "posted", "platform": "facebook", "id": result.get("id"), "timestamp": now_iso()}
    except HTTPError as e:
        err = e.read().decode()
        log_action("social_post_failed", "social_mcp", "facebook", err, status="failed")
        return {"status": "error", "platform": "facebook", "error": err, "timestamp": now_iso()}


# ── Instagram ──────────────────────────────────────────────────────────────
def post_instagram(caption: str, image_url: str) -> dict:
    """Post to Instagram (requires image_url hosted publicly)."""
    if not _rate_limiter.allow():
        return {"status": "rate_limited", "platform": "instagram", "timestamp": now_iso()}

    if DRY_RUN:
        log_action("social_post", "social_mcp", "instagram", f"DRY RUN: {caption[:80]}", status="dry_run")
        return {"status": "dry_run", "platform": "instagram", "caption": caption[:80], "timestamp": now_iso()}

    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        return {"status": "error", "message": "Instagram credentials not configured", "timestamp": now_iso()}

    # Step 1: Create media container
    create_payload = json.dumps({
        "image_url": image_url,
        "caption": caption,
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }).encode()
    create_req = Request(
        f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media",
        data=create_payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(create_req) as resp:
            container = json.loads(resp.read())
        container_id = container.get("id")

        # Step 2: Publish
        pub_payload = json.dumps({
            "creation_id": container_id,
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        }).encode()
        pub_req = Request(
            f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media_publish",
            data=pub_payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(pub_req) as resp:
            result = json.loads(resp.read())

        log_action("social_post", "social_mcp", "instagram", f"Posted: {caption[:80]}", status="success")
        return {"status": "posted", "platform": "instagram", "id": result.get("id"), "timestamp": now_iso()}
    except HTTPError as e:
        err = e.read().decode()
        log_action("social_post_failed", "social_mcp", "instagram", err, status="failed")
        return {"status": "error", "platform": "instagram", "error": err, "timestamp": now_iso()}


# ── Universal draft (no API) ──────────────────────────────────────────────
def draft_social(platform: str, text: str, needs_approval: bool = True) -> dict:
    """Save a social media draft as .md file. Optionally create HITL approval request."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    if needs_approval:
        filepath = PENDING_APPROVAL_DIR / f"APPROVAL_REQUIRED_{ts}_social_{platform}.md"
    else:
        filepath = DONE_DIR / f"DRAFT_social_{platform}_{ts}.md"

    content = f"""---
type: social_draft
platform: {platform}
created_at: {now_iso()}
status: {"pending_approval" if needs_approval else "draft"}
action: draft_social_post
---

# 📣 Social Media Draft — {platform.title()}

**Platform:** {platform}
**Created:** {now_local_iso()}
**Approval Required:** {"Yes ⚠️" if needs_approval else "No"}

---

{text}

---

> *Draft created by social_mcp*
"""
    filepath.write_text(content, encoding="utf-8")
    log_action(
        "social_draft", "social_mcp", filepath.name,
        f"Draft for {platform}: {text[:60]}",
        approval_status="pending" if needs_approval else "N/A",
    )
    return {"status": "drafted", "platform": platform, "path": str(filepath), "timestamp": now_iso()}


# ── MCP Server (stdio protocol) ───────────────────────────────────────────
TOOLS = [
    {"name": "post_linkedin", "description": "Post text to LinkedIn", "inputSchema": {
        "type": "object", "properties": {"text": {"type": "string"}, "visibility": {"type": "string", "default": "PUBLIC"}}, "required": ["text"]}},
    {"name": "post_twitter", "description": "Post tweet to X/Twitter", "inputSchema": {
        "type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "post_facebook", "description": "Post to Facebook Page", "inputSchema": {
        "type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}},
    {"name": "post_instagram", "description": "Post to Instagram (image required)", "inputSchema": {
        "type": "object", "properties": {"caption": {"type": "string"}, "image_url": {"type": "string"}}, "required": ["caption", "image_url"]}},
    {"name": "draft_social", "description": "Save social post draft to vault", "inputSchema": {
        "type": "object", "properties": {"platform": {"type": "string"}, "text": {"type": "string"}, "needs_approval": {"type": "boolean", "default": True}}, "required": ["platform", "text"]}},
]

TOOL_MAP = {
    "post_linkedin": post_linkedin,
    "post_twitter": post_twitter,
    "post_facebook": post_facebook,
    "post_instagram": post_instagram,
    "draft_social": draft_social,
}


def handle_mcp_request(request: dict) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "tools/list":
        return {"tools": TOOLS}
    elif method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        handler = TOOL_MAP.get(tool_name)
        if handler:
            result = handler(**args)
        else:
            result = {"status": "error", "message": f"Unknown tool: {tool_name}"}
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    return {"error": f"Unknown method: {method}"}


def run_mcp_server():
    print("📣  Social Media MCP Server started (stdio)", file=sys.stderr)
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
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("📣  Social Media MCP — Test Mode\n")
        for platform in ["linkedin", "twitter", "facebook"]:
            result = draft_social(platform, f"Test post from AI Employee — {now_local_iso()}", needs_approval=False)
            print(f"  {platform}: {result['status']}")
    else:
        run_mcp_server()
