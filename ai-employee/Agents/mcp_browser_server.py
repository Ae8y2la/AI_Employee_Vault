"""
Browser MCP Server — Web Automation via Playwright
=====================================================
MCP server for browser-based actions: navigating, scraping, form filling.
Uses Playwright for headless browser control.

MCP Config:
{
  "mcpServers": {
    "browser-mcp": {
      "command": "python",
      "args": ["Agents/mcp_browser_server.py"],
      "cwd": "<vault_root>"
    }
  }
}
"""

import sys
import json
from datetime import datetime, timezone

try:
    from Agents.config import DRY_RUN, DONE_DIR, now_iso, now_local_iso
    from Agents.action_logger import log_action
except ImportError:
    from config import DRY_RUN, DONE_DIR, now_iso, now_local_iso
    from action_logger import log_action


# ── Playwright helper ──────────────────────────────────────────────────────
def _check_playwright() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def navigate_and_extract(url: str, selector: str = "body", wait_ms: int = 3000) -> dict:
    """Navigate to URL and extract text content from a CSS selector."""
    if DRY_RUN:
        log_action("browser_navigate", "browser_mcp", url, f"DRY RUN: {selector}", status="dry_run")
        return {
            "status": "dry_run",
            "url": url,
            "selector": selector,
            "content": f"[DRY RUN] Would extract '{selector}' from {url}",
            "timestamp": now_iso(),
        }

    if not _check_playwright():
        return {"status": "error", "message": "Playwright not installed", "timestamp": now_iso()}

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_timeout(wait_ms)

            element = page.query_selector(selector)
            content = element.inner_text() if element else page.content()[:2000]

            browser.close()

        log_action("browser_navigate", "browser_mcp", url, f"Extracted from {selector}", status="success")
        return {"status": "success", "url": url, "content": content[:3000], "timestamp": now_iso()}
    except Exception as e:
        log_action("browser_navigate_failed", "browser_mcp", url, str(e), status="failed")
        return {"status": "error", "url": url, "message": str(e), "timestamp": now_iso()}


def take_screenshot(url: str, output_name: str = "screenshot") -> dict:
    """Take a screenshot of a webpage."""
    if DRY_RUN:
        return {"status": "dry_run", "url": url, "message": "Would take screenshot", "timestamp": now_iso()}

    if not _check_playwright():
        return {"status": "error", "message": "Playwright not installed", "timestamp": now_iso()}

    try:
        from playwright.sync_api import sync_playwright
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        screenshot_path = DONE_DIR / f"screenshot_{output_name}_{ts}.png"

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_timeout(2000)
            page.screenshot(path=str(screenshot_path))
            browser.close()

        log_action("browser_screenshot", "browser_mcp", url, f"Saved: {screenshot_path.name}", status="success")
        return {"status": "success", "path": str(screenshot_path), "timestamp": now_iso()}
    except Exception as e:
        return {"status": "error", "message": str(e), "timestamp": now_iso()}


def fill_form(url: str, fields: dict, submit_selector: str = "") -> dict:
    """Navigate to URL and fill form fields. Fields = {selector: value}."""
    if DRY_RUN:
        log_action("browser_form", "browser_mcp", url, f"DRY RUN: {len(fields)} fields", status="dry_run")
        return {
            "status": "dry_run",
            "url": url,
            "fields_count": len(fields),
            "message": "Would fill form (DRY_RUN)",
            "timestamp": now_iso(),
        }

    if not _check_playwright():
        return {"status": "error", "message": "Playwright not installed", "timestamp": now_iso()}

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            page.wait_for_timeout(2000)

            for selector, value in fields.items():
                page.fill(selector, value)

            if submit_selector:
                page.click(submit_selector)
                page.wait_for_timeout(3000)

            browser.close()

        log_action("browser_form", "browser_mcp", url, f"Filled {len(fields)} fields", status="success")
        return {"status": "success", "url": url, "fields_filled": len(fields), "timestamp": now_iso()}
    except Exception as e:
        log_action("browser_form_failed", "browser_mcp", url, str(e), status="failed")
        return {"status": "error", "message": str(e), "timestamp": now_iso()}


# ── MCP Server ─────────────────────────────────────────────────────────────
TOOLS = [
    {"name": "navigate_and_extract", "description": "Navigate to URL and extract text from selector", "inputSchema": {
        "type": "object",
        "properties": {"url": {"type": "string"}, "selector": {"type": "string", "default": "body"}, "wait_ms": {"type": "integer", "default": 3000}},
        "required": ["url"],
    }},
    {"name": "take_screenshot", "description": "Take screenshot of a webpage", "inputSchema": {
        "type": "object",
        "properties": {"url": {"type": "string"}, "output_name": {"type": "string", "default": "screenshot"}},
        "required": ["url"],
    }},
    {"name": "fill_form", "description": "Fill and optionally submit a web form", "inputSchema": {
        "type": "object",
        "properties": {"url": {"type": "string"}, "fields": {"type": "object"}, "submit_selector": {"type": "string"}},
        "required": ["url", "fields"],
    }},
]

TOOL_MAP = {
    "navigate_and_extract": navigate_and_extract,
    "take_screenshot": take_screenshot,
    "fill_form": fill_form,
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
    print("🌐  Browser MCP Server started (stdio)", file=sys.stderr)
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
        print("🌐  Browser MCP — Test Mode\n")
        result = navigate_and_extract("https://example.com", "h1")
        print(json.dumps(result, indent=2))
    else:
        run_mcp_server()
