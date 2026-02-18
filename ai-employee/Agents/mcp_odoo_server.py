"""
Odoo Accounting MCP Server — Financial Integration
====================================================
MCP server for Odoo ERP accounting integration.
Supports reading invoices, balances, journal entries, and creating records.

MCP Config:
{
  "mcpServers": {
    "odoo-mcp": {
      "command": "python",
      "args": ["Agents/mcp_odoo_server.py"],
      "cwd": "<vault_root>"
    }
  }
}
"""

import sys
import json
import xmlrpc.client
from pathlib import Path
from datetime import datetime, timezone

try:
    from Agents.config import (
        ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD,
        ACCOUNTING_DIR, DRY_RUN, BANK_BALANCE_LAST_KNOWN,
        BANK_CURRENCY, BANK_NAME,
        now_iso, now_local_iso,
    )
    from Agents.action_logger import log_action
except ImportError:
    from config import (
        ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD,
        ACCOUNTING_DIR, DRY_RUN, BANK_BALANCE_LAST_KNOWN,
        BANK_CURRENCY, BANK_NAME,
        now_iso, now_local_iso,
    )
    from action_logger import log_action


# ── Odoo connection ───────────────────────────────────────────────────────
class OdooClient:
    """Lightweight Odoo XML-RPC client."""

    def __init__(self):
        self.url = ODOO_URL
        self.db = ODOO_DB
        self.uid = None
        self._connected = False

    def connect(self) -> bool:
        if not all([self.url, self.db, ODOO_USERNAME, ODOO_PASSWORD]):
            return False
        try:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self.uid = common.authenticate(self.db, ODOO_USERNAME, ODOO_PASSWORD, {})
            self._connected = self.uid is not None and self.uid is not False
            return self._connected
        except Exception:
            return False

    def execute(self, model: str, method: str, *args, **kwargs):
        if not self._connected:
            raise RuntimeError("Not connected to Odoo")
        models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        return models.execute_kw(self.db, self.uid, ODOO_PASSWORD, model, method, list(args), kwargs)

_odoo = OdooClient()


# ── Financial tools ────────────────────────────────────────────────────────
def get_bank_balance() -> dict:
    """Get current bank balance (from Odoo or .env fallback)."""
    if DRY_RUN or not _odoo.connect():
        return {
            "status": "dry_run" if DRY_RUN else "offline",
            "bank": BANK_NAME or "Not configured",
            "balance": BANK_BALANCE_LAST_KNOWN,
            "currency": BANK_CURRENCY,
            "source": ".env fallback",
            "timestamp": now_iso(),
        }

    try:
        journals = _odoo.execute(
            "account.journal", "search_read",
            [("type", "=", "bank")],
            fields=["name", "default_account_id"],
            limit=5,
        )
        balances = []
        for j in journals:
            balance_data = _odoo.execute(
                "account.move.line", "read_group",
                [("account_id", "=", j["default_account_id"][0])],
                fields=["balance"],
                groupby=[],
            )
            bal = balance_data[0]["balance"] if balance_data else 0
            balances.append({"journal": j["name"], "balance": f"{bal:.2f}"})

        log_action("finance_query", "odoo_mcp", "bank_balance", f"Retrieved {len(balances)} accounts", status="success")
        return {"status": "success", "accounts": balances, "currency": BANK_CURRENCY, "timestamp": now_iso()}
    except Exception as e:
        log_action("finance_query_failed", "odoo_mcp", "bank_balance", str(e), status="failed")
        return {"status": "error", "message": str(e), "timestamp": now_iso()}


def get_unpaid_invoices(invoice_type: str = "out_invoice", limit: int = 20) -> dict:
    """Get unpaid invoices from Odoo."""
    if DRY_RUN or not _odoo.connect():
        return {
            "status": "dry_run" if DRY_RUN else "offline",
            "invoices": [
                {"number": "INV-SAMPLE-001", "partner": "Sample Client", "amount": "1,500.00", "due": "2026-02-28"},
            ],
            "message": "Sample data — connect Odoo for live invoices",
            "timestamp": now_iso(),
        }

    try:
        invoices = _odoo.execute(
            "account.move", "search_read",
            [("move_type", "=", invoice_type), ("payment_state", "!=", "paid"), ("state", "=", "posted")],
            fields=["name", "partner_id", "amount_total", "invoice_date_due", "currency_id"],
            limit=limit,
        )
        result = [
            {
                "number": inv["name"],
                "partner": inv["partner_id"][1] if inv["partner_id"] else "",
                "amount": f"{inv['amount_total']:.2f}",
                "due": str(inv.get("invoice_date_due", "")),
                "currency": inv["currency_id"][1] if inv.get("currency_id") else BANK_CURRENCY,
            }
            for inv in invoices
        ]
        log_action("finance_query", "odoo_mcp", "unpaid_invoices", f"Found {len(result)} unpaid", status="success")
        return {"status": "success", "invoices": result, "timestamp": now_iso()}
    except Exception as e:
        return {"status": "error", "message": str(e), "timestamp": now_iso()}


def create_accounting_note(title: str, content: str) -> dict:
    """Save an accounting note to /Accounting as .md file."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    filepath = ACCOUNTING_DIR / f"{ts}_{title.replace(' ', '_')[:40]}.md"

    md_content = f"""---
type: accounting_note
created_at: {now_iso()}
---

# 💰 {title}

{content}

---
> *Created by odoo_mcp — {now_local_iso()}*
"""
    filepath.write_text(md_content, encoding="utf-8")
    log_action("accounting_note", "odoo_mcp", filepath.name, f"Note: {title}", status="success")
    return {"status": "created", "path": str(filepath), "timestamp": now_iso()}


def get_profit_loss_summary() -> dict:
    """Get a P&L summary from Odoo (or sample data in dry-run)."""
    if DRY_RUN or not _odoo.connect():
        return {
            "status": "dry_run" if DRY_RUN else "offline",
            "summary": {
                "revenue": "0.00",
                "expenses": "0.00",
                "net_profit": "0.00",
                "period": "current_month",
            },
            "message": "Sample data — connect Odoo for live P&L",
            "timestamp": now_iso(),
        }

    try:
        # Simplified P&L — revenue vs expense accounts
        revenue = _odoo.execute(
            "account.move.line", "read_group",
            [("account_id.account_type", "=", "income")],
            fields=["balance"], groupby=[],
        )
        expenses = _odoo.execute(
            "account.move.line", "read_group",
            [("account_id.account_type", "=", "expense")],
            fields=["balance"], groupby=[],
        )

        rev = abs(revenue[0]["balance"]) if revenue else 0
        exp = abs(expenses[0]["balance"]) if expenses else 0

        return {
            "status": "success",
            "summary": {
                "revenue": f"{rev:.2f}",
                "expenses": f"{exp:.2f}",
                "net_profit": f"{rev - exp:.2f}",
                "period": "all_time",
            },
            "timestamp": now_iso(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "timestamp": now_iso()}


# ── MCP Server ─────────────────────────────────────────────────────────────
TOOLS = [
    {"name": "get_bank_balance", "description": "Get bank account balance", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_unpaid_invoices", "description": "List unpaid invoices", "inputSchema": {
        "type": "object", "properties": {"invoice_type": {"type": "string", "default": "out_invoice"}, "limit": {"type": "integer", "default": 20}}}},
    {"name": "create_accounting_note", "description": "Save accounting note to /Accounting", "inputSchema": {
        "type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}}, "required": ["title", "content"]}},
    {"name": "get_profit_loss_summary", "description": "Get P&L summary", "inputSchema": {"type": "object", "properties": {}}},
]

TOOL_MAP = {
    "get_bank_balance": get_bank_balance,
    "get_unpaid_invoices": get_unpaid_invoices,
    "create_accounting_note": create_accounting_note,
    "get_profit_loss_summary": get_profit_loss_summary,
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
    print("💰  Odoo Accounting MCP Server started (stdio)", file=sys.stderr)
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
        print("💰  Odoo MCP — Test Mode\n")
        print("Bank Balance:")
        print(json.dumps(get_bank_balance(), indent=2))
        print("\nUnpaid Invoices:")
        print(json.dumps(get_unpaid_invoices(), indent=2))
        print("\nP&L Summary:")
        print(json.dumps(get_profit_loss_summary(), indent=2))
    else:
        run_mcp_server()
