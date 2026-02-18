"""
Central Configuration — AI Employee System (Platinum Tier)
=============================================================
Loads settings from environment variables / .env file.
Supports CLOUD / LOCAL agent modes for split architecture.
"""

import os
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Vault paths
# ---------------------------------------------------------------------------
VAULT_ROOT = Path(__file__).resolve().parent.parent  # ai-employee/
INBOX_DIR = VAULT_ROOT / "Inbox"
NEEDS_ACTION_DIR = VAULT_ROOT / "Needs_Action"
DONE_DIR = VAULT_ROOT / "Done"
AGENTS_DIR = VAULT_ROOT / "Agents"
PENDING_APPROVAL_DIR = VAULT_ROOT / "Pending_Approval"
APPROVED_DIR = VAULT_ROOT / "Approved"
ACCOUNTING_DIR = VAULT_ROOT / "Accounting"
LOGS_DIR = VAULT_ROOT / "Logs"
PROJECTS_DIR = VAULT_ROOT / "Projects"

# Platinum Tier — split architecture folders
PLANS_DIR = VAULT_ROOT / "Plans"
IN_PROGRESS_DIR = VAULT_ROOT / "In_Progress"
UPDATES_DIR = VAULT_ROOT / "Updates"
SIGNALS_DIR = VAULT_ROOT / "Signals"

# Domain subfolders
DOMAINS = ["email", "social", "accounting", "calendar", "general"]

ALL_DIRS = [
    INBOX_DIR, NEEDS_ACTION_DIR, DONE_DIR, AGENTS_DIR,
    PENDING_APPROVAL_DIR, APPROVED_DIR, ACCOUNTING_DIR,
    LOGS_DIR, PROJECTS_DIR, PLANS_DIR, IN_PROGRESS_DIR,
    UPDATES_DIR, SIGNALS_DIR,
]

# Add domain subdirectories
for _d in DOMAINS:
    ALL_DIRS.extend([
        NEEDS_ACTION_DIR / _d,
        PLANS_DIR / _d,
        PENDING_APPROVAL_DIR / _d,
    ])
ALL_DIRS.extend([
    IN_PROGRESS_DIR / "cloud_agent",
    IN_PROGRESS_DIR / "local_agent",
])

# ---------------------------------------------------------------------------
# .env loader (stdlib only)
# ---------------------------------------------------------------------------
def _load_dotenv() -> None:
    env_file = VAULT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value

_load_dotenv()

# ---------------------------------------------------------------------------
# Agent mode: "cloud", "local", or "standalone" (Gold-tier compat)
# ---------------------------------------------------------------------------
AGENT_MODE: str = os.getenv("AGENT_MODE", "standalone").lower()

# ---------------------------------------------------------------------------
# Operational settings
# ---------------------------------------------------------------------------
DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")
RATE_LIMIT_ACTIONS_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_ACTIONS_PER_MINUTE", "5"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ---------------------------------------------------------------------------
# Gmail settings
# ---------------------------------------------------------------------------
GMAIL_CLIENT_ID: str = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET: str = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REFRESH_TOKEN: str = os.getenv("GMAIL_REFRESH_TOKEN", "")
GMAIL_USER_EMAIL: str = os.getenv("GMAIL_USER_EMAIL", "")

# ---------------------------------------------------------------------------
# SMTP / Email MCP settings
# ---------------------------------------------------------------------------
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_ADDRESS: str = os.getenv("SMTP_FROM_ADDRESS", "")

# ---------------------------------------------------------------------------
# Social Media settings
# ---------------------------------------------------------------------------
LINKEDIN_ACCESS_TOKEN: str = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN: str = os.getenv("LINKEDIN_PERSON_URN", "")
TWITTER_API_KEY: str = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET: str = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN: str = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET: str = os.getenv("TWITTER_ACCESS_SECRET", "")
FACEBOOK_PAGE_TOKEN: str = os.getenv("FACEBOOK_PAGE_TOKEN", "")
FACEBOOK_PAGE_ID: str = os.getenv("FACEBOOK_PAGE_ID", "")
INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID: str = os.getenv("INSTAGRAM_ACCOUNT_ID", "")

# ---------------------------------------------------------------------------
# Odoo / Accounting settings
# ---------------------------------------------------------------------------
ODOO_URL: str = os.getenv("ODOO_URL", "")
ODOO_DB: str = os.getenv("ODOO_DB", "")
ODOO_USERNAME: str = os.getenv("ODOO_USERNAME", "")
ODOO_PASSWORD: str = os.getenv("ODOO_PASSWORD", "")

# ---------------------------------------------------------------------------
# Calendar settings
# ---------------------------------------------------------------------------
GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")

# ---------------------------------------------------------------------------
# Bank / Finance settings
# ---------------------------------------------------------------------------
BANK_NAME: str = os.getenv("BANK_NAME", "")
BANK_BALANCE_LAST_KNOWN: str = os.getenv("BANK_BALANCE_LAST_KNOWN", "0.00")
BANK_CURRENCY: str = os.getenv("BANK_CURRENCY", "USD")

# ---------------------------------------------------------------------------
# Cloud deployment settings
# ---------------------------------------------------------------------------
CLOUD_VM_HOST: str = os.getenv("CLOUD_VM_HOST", "")
CLOUD_VM_USER: str = os.getenv("CLOUD_VM_USER", "")
CLOUD_SYNC_REMOTE: str = os.getenv("CLOUD_SYNC_REMOTE", "")  # git remote URL
CLOUD_SYNC_BRANCH: str = os.getenv("CLOUD_SYNC_BRANCH", "main")
CLOUD_SYNC_INTERVAL: int = int(os.getenv("CLOUD_SYNC_INTERVAL", "60"))

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def now_local_iso() -> str:
    return datetime.now().astimezone().isoformat()

def ensure_dirs() -> None:
    for d in ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)

def is_cloud() -> bool:
    return AGENT_MODE == "cloud"

def is_local() -> bool:
    return AGENT_MODE == "local"

def is_standalone() -> bool:
    return AGENT_MODE == "standalone"
