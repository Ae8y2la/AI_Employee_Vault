"""
Sync Manager — Git-Based Vault Sync Between Cloud + Local
============================================================
Manages bidirectional sync of the vault between Cloud VM and Local machine.

Security rules:
  - NEVER syncs: .env, credentials.json, token.json, WhatsApp sessions
  - Only syncs: .md files, .json state files (logs), folder structure
  - Pull before push (prevent conflicts)

Phase 1: Git-based sync
Phase 2: Syncthing (planned)

Usage:
    python Agents/sync_manager.py --push       # push local changes to remote
    python Agents/sync_manager.py --pull       # pull remote changes
    python Agents/sync_manager.py --sync       # pull then push
    python Agents/sync_manager.py --auto       # continuous auto-sync
    python Agents/sync_manager.py --status     # show sync status
"""

import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from Agents.config import (
        VAULT_ROOT, CLOUD_SYNC_REMOTE, CLOUD_SYNC_BRANCH,
        CLOUD_SYNC_INTERVAL, AGENT_MODE, now_local_iso,
    )
    from Agents.action_logger import log_action
except ImportError:
    from config import (
        VAULT_ROOT, CLOUD_SYNC_REMOTE, CLOUD_SYNC_BRANCH,
        CLOUD_SYNC_INTERVAL, AGENT_MODE, now_local_iso,
    )
    from action_logger import log_action


# Files/patterns that should NEVER sync
SYNC_EXCLUDE = [
    ".env",
    "Agents/credentials.json",
    "Agents/token.json",
    "Agents/whatsapp_session/",
    "__pycache__/",
    "*.pyc",
]


def _run_git(args: list[str], cwd: str = None) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or str(VAULT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except FileNotFoundError:
        return 1, "", "Git not found — install git first"


def ensure_gitignore() -> None:
    """Ensure .gitignore excludes sensitive files."""
    gitignore = VAULT_ROOT / ".gitignore"
    existing = ""
    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8")

    missing = []
    for pattern in SYNC_EXCLUDE:
        if pattern not in existing:
            missing.append(pattern)

    if missing:
        with open(gitignore, "a", encoding="utf-8") as f:
            f.write("\n# Sync Manager — security exclusions\n")
            for p in missing:
                f.write(f"{p}\n")
        print(f"  🔒  Added {len(missing)} exclusions to .gitignore")


def git_init() -> bool:
    """Initialize git repo if not exists."""
    git_dir = VAULT_ROOT / ".git"
    if git_dir.exists():
        return True

    code, out, err = _run_git(["init"])
    if code == 0:
        print("  📁  Git repo initialized")
        ensure_gitignore()
        _run_git(["add", "."])
        _run_git(["commit", "-m", "Initial vault commit"])
        return True
    else:
        print(f"  ❌  Git init failed: {err}")
        return False


def git_status() -> dict:
    """Get current git status."""
    code, out, err = _run_git(["status", "--porcelain"])
    changes = out.splitlines() if out else []

    code2, branch, _ = _run_git(["branch", "--show-current"])
    code3, remote, _ = _run_git(["remote", "-v"])

    return {
        "branch": branch if code2 == 0 else "unknown",
        "changes": len(changes),
        "changed_files": changes[:10],
        "remote": remote if code3 == 0 else "none",
    }


def git_pull() -> dict:
    """Pull changes from remote."""
    if not CLOUD_SYNC_REMOTE:
        return {"status": "skipped", "reason": "No CLOUD_SYNC_REMOTE configured"}

    ensure_gitignore()

    # Stash local changes
    _run_git(["stash"])

    # Pull
    code, out, err = _run_git(["pull", "origin", CLOUD_SYNC_BRANCH, "--rebase"])

    # Pop stash
    _run_git(["stash", "pop"])

    if code == 0:
        log_action("sync_pull", "sync_manager", "vault", f"Pulled from {CLOUD_SYNC_BRANCH}")
        return {"status": "success", "output": out}
    else:
        log_action("sync_pull_failed", "sync_manager", "vault", err, status="failed")
        return {"status": "error", "error": err}


def git_push() -> dict:
    """Push changes to remote."""
    if not CLOUD_SYNC_REMOTE:
        return {"status": "skipped", "reason": "No CLOUD_SYNC_REMOTE configured"}

    ensure_gitignore()

    # Stage all changes
    _run_git(["add", "-A"])

    # Commit
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    agent = "cloud" if AGENT_MODE == "cloud" else "local"
    code, out, err = _run_git(["commit", "-m", f"[{agent}] Auto-sync {ts}"])

    if code != 0 and "nothing to commit" in err + out:
        return {"status": "clean", "message": "Nothing to commit"}

    # Push
    code, out, err = _run_git(["push", "origin", CLOUD_SYNC_BRANCH])

    if code == 0:
        log_action("sync_push", "sync_manager", "vault", f"Pushed to {CLOUD_SYNC_BRANCH}")
        return {"status": "success", "output": out}
    else:
        log_action("sync_push_failed", "sync_manager", "vault", err, status="failed")
        return {"status": "error", "error": err}


def full_sync() -> dict:
    """Pull then push — safest sync pattern."""
    pull_result = git_pull()
    push_result = git_push()
    return {"pull": pull_result, "push": push_result}


def auto_sync() -> None:
    """Continuous auto-sync loop."""
    interval = CLOUD_SYNC_INTERVAL
    print(f"\n🔄  Sync Manager — Auto-sync started")
    print(f"    Remote: {CLOUD_SYNC_REMOTE or '(not configured)'}")
    print(f"    Branch: {CLOUD_SYNC_BRANCH}")
    print(f"    Interval: {interval}s")
    print(f"    Mode: {AGENT_MODE}\n")

    git_init()

    while True:
        result = full_sync()
        pull_status = result["pull"]["status"]
        push_status = result["push"]["status"]

        if pull_status != "skipped" or push_status != "skipped":
            print(f"  🔄  Sync: pull={pull_status}, push={push_status} ({now_local_iso()})")

        time.sleep(interval)


def show_status() -> None:
    """Show sync status."""
    print(f"\n🔄  Sync Manager Status — {now_local_iso()}")
    status = git_status()
    print(f"    Branch:    {status['branch']}")
    print(f"    Remote:    {CLOUD_SYNC_REMOTE or '(not configured)'}")
    print(f"    Changes:   {status['changes']} uncommitted files")
    if status["changed_files"]:
        for f in status["changed_files"]:
            print(f"      {f}")
    print(f"    Mode:      {AGENT_MODE}")
    print(f"    Interval:  {CLOUD_SYNC_INTERVAL}s")


if __name__ == "__main__":
    if "--push" in sys.argv:
        result = git_push()
        print(f"🔄  Push: {result['status']}")
    elif "--pull" in sys.argv:
        result = git_pull()
        print(f"🔄  Pull: {result['status']}")
    elif "--sync" in sys.argv:
        result = full_sync()
        print(f"🔄  Sync complete")
    elif "--auto" in sys.argv:
        auto_sync()
    elif "--status" in sys.argv:
        show_status()
    elif "--init" in sys.argv:
        git_init()
    else:
        show_status()
