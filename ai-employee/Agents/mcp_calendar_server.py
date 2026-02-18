"""
Calendar MCP Server — Task Scheduling & Event Management
==========================================================
MCP server for Google Calendar integration.
Supports creating events, listing upcoming events, and scheduling tasks.

MCP Config:
{
  "mcpServers": {
    "calendar-mcp": {
      "command": "python",
      "args": ["Agents/mcp_calendar_server.py"],
      "cwd": "<vault_root>"
    }
  }
}
"""

import sys
import json
from datetime import datetime, timedelta, timezone

try:
    from Agents.config import (
        GOOGLE_CALENDAR_ID, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET,
        GMAIL_REFRESH_TOKEN, DRY_RUN, NEEDS_ACTION_DIR,
        now_iso, now_local_iso,
    )
    from Agents.action_logger import log_action
except ImportError:
    from config import (
        GOOGLE_CALENDAR_ID, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET,
        GMAIL_REFRESH_TOKEN, DRY_RUN, NEEDS_ACTION_DIR,
        now_iso, now_local_iso,
    )
    from action_logger import log_action


def _get_calendar_service():
    """Build Google Calendar API service."""
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
        return build("calendar", "v3", credentials=creds)
    except ImportError:
        return None


def create_event(
    summary: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
) -> dict:
    """Create a Google Calendar event."""
    if DRY_RUN:
        log_action("calendar_event", "calendar_mcp", summary, f"DRY RUN: {start_time}", status="dry_run")
        return {
            "status": "dry_run",
            "summary": summary,
            "start": start_time,
            "end": end_time,
            "timestamp": now_iso(),
        }

    service = _get_calendar_service()
    if service is None:
        return {"status": "error", "message": "Google API libraries not installed", "timestamp": now_iso()}

    event = {
        "summary": summary,
        "description": description,
        "location": location,
        "start": {"dateTime": start_time, "timeZone": "UTC"},
        "end": {"dateTime": end_time, "timeZone": "UTC"},
    }

    try:
        created = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
        log_action("calendar_event", "calendar_mcp", summary, f"Created: {created.get('htmlLink')}", status="success")
        return {"status": "created", "id": created.get("id"), "link": created.get("htmlLink"), "timestamp": now_iso()}
    except Exception as e:
        log_action("calendar_event_failed", "calendar_mcp", summary, str(e), status="failed")
        return {"status": "error", "message": str(e), "timestamp": now_iso()}


def list_upcoming(max_results: int = 10) -> dict:
    """List upcoming calendar events."""
    if DRY_RUN:
        return {
            "status": "dry_run",
            "events": [
                {"summary": "Daily Standup", "start": "09:00", "end": "09:30"},
                {"summary": "CEO Briefing Review", "start": "10:00", "end": "10:30"},
            ],
            "message": "DRY RUN — showing sample events",
            "timestamp": now_iso(),
        }

    service = _get_calendar_service()
    if service is None:
        return {"status": "error", "message": "Google API libraries not installed", "timestamp": now_iso()}

    try:
        now_utc = datetime.now(timezone.utc).isoformat()
        result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=now_utc,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = [
            {
                "summary": e.get("summary", ""),
                "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
                "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
                "link": e.get("htmlLink", ""),
            }
            for e in result.get("items", [])
        ]
        return {"status": "success", "events": events, "timestamp": now_iso()}
    except Exception as e:
        return {"status": "error", "message": str(e), "timestamp": now_iso()}


def schedule_task_reminder(task: str, when: str) -> dict:
    """
    Create a calendar reminder for a vault task.
    `when` should be ISO datetime or relative like '+1h', '+1d'.
    """
    # Parse relative time
    if when.startswith("+"):
        now_dt = datetime.now(timezone.utc)
        unit = when[-1]
        amount = int(when[1:-1])
        if unit == "h":
            start = now_dt + timedelta(hours=amount)
        elif unit == "d":
            start = now_dt + timedelta(days=amount)
        elif unit == "m":
            start = now_dt + timedelta(minutes=amount)
        else:
            start = now_dt + timedelta(hours=1)
        start_str = start.isoformat()
        end_str = (start + timedelta(minutes=30)).isoformat()
    else:
        start_str = when
        end_dt = datetime.fromisoformat(when) + timedelta(minutes=30)
        end_str = end_dt.isoformat()

    return create_event(
        summary=f"🔔 Task Reminder: {task}",
        start_time=start_str,
        end_time=end_str,
        description=f"Auto-scheduled by AI Employee\nTask: {task}",
    )


# ── MCP Server ─────────────────────────────────────────────────────────────
TOOLS = [
    {"name": "create_event", "description": "Create a Google Calendar event", "inputSchema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"}, "start_time": {"type": "string"},
            "end_time": {"type": "string"}, "description": {"type": "string"},
            "location": {"type": "string"},
        },
        "required": ["summary", "start_time", "end_time"],
    }},
    {"name": "list_upcoming", "description": "List upcoming calendar events", "inputSchema": {
        "type": "object", "properties": {"max_results": {"type": "integer", "default": 10}}}},
    {"name": "schedule_task_reminder", "description": "Schedule a task reminder", "inputSchema": {
        "type": "object",
        "properties": {"task": {"type": "string"}, "when": {"type": "string"}},
        "required": ["task", "when"],
    }},
]

TOOL_MAP = {
    "create_event": create_event,
    "list_upcoming": list_upcoming,
    "schedule_task_reminder": schedule_task_reminder,
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
    print("📅  Calendar MCP Server started (stdio)", file=sys.stderr)
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
        print("📅  Calendar MCP — Test Mode\n")
        result = list_upcoming()
        print(json.dumps(result, indent=2))
    else:
        run_mcp_server()
