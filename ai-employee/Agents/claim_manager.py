"""
Claim Manager — Prevent Double-Work Between Cloud + Local Agents
===================================================================
Implements claim-by-move rule:
  - Before an agent works on a task, it "claims" it by moving to
    /In_Progress/<agent_name>/
  - When done, moves to /Done or /Pending_Approval
  - If a file is already claimed, other agents skip it

This prevents Cloud and Local agents from working on the same task.

Usage:
    from claim_manager import ClaimManager
    cm = ClaimManager("cloud_agent")
    claimed = cm.claim(file_path)
    # ... work on it ...
    cm.release(claimed, destination_dir)
"""

import shutil
from pathlib import Path
from datetime import datetime, timezone

try:
    from Agents.config import IN_PROGRESS_DIR, DONE_DIR, now_iso
    from Agents.action_logger import log_action
except ImportError:
    from config import IN_PROGRESS_DIR, DONE_DIR, now_iso
    from action_logger import log_action


class ClaimManager:
    """Manages task claims to prevent double-work."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.claim_dir = IN_PROGRESS_DIR / agent_name
        self.claim_dir.mkdir(parents=True, exist_ok=True)

    def is_claimed_by_anyone(self, filename: str) -> bool:
        """Check if a file is claimed by any agent."""
        for agent_dir in IN_PROGRESS_DIR.iterdir():
            if agent_dir.is_dir() and (agent_dir / filename).exists():
                return True
        return False

    def claim(self, source_path: Path) -> Path | None:
        """
        Claim a task by moving it to /In_Progress/<agent>/.
        Returns the new path, or None if already claimed.
        """
        if not source_path.exists():
            return None

        filename = source_path.name

        # Check if already claimed by anyone
        if self.is_claimed_by_anyone(filename):
            return None

        dest = self.claim_dir / filename
        try:
            shutil.move(str(source_path), str(dest))
            log_action(
                "task_claimed", self.agent_name, filename,
                f"Claimed by {self.agent_name}"
            )
            return dest
        except (OSError, shutil.Error):
            return None

    def release(self, claimed_path: Path, destination: Path) -> Path | None:
        """
        Release a claimed task by moving to destination (Done, Pending_Approval, etc).
        """
        if not claimed_path.exists():
            return None

        destination.mkdir(parents=True, exist_ok=True)
        dest = destination / claimed_path.name
        try:
            shutil.move(str(claimed_path), str(dest))
            log_action(
                "task_released", self.agent_name, claimed_path.name,
                f"Released to {destination.name}"
            )
            return dest
        except (OSError, shutil.Error):
            return None

    def release_to_done(self, claimed_path: Path) -> Path | None:
        return self.release(claimed_path, DONE_DIR)

    def list_claimed(self) -> list[Path]:
        """List all files currently claimed by this agent."""
        if not self.claim_dir.exists():
            return []
        return [f for f in self.claim_dir.iterdir()
                if f.is_file() and not f.name.startswith(".")]

    def abandon_stale(self, source_dir: Path, max_age_hours: int = 4) -> int:
        """
        Move stale claims (older than max_age_hours) back to source_dir.
        Returns count of abandoned claims.
        """
        count = 0
        now = datetime.now().timestamp()
        for f in self.list_claimed():
            age_hours = (now - f.stat().st_mtime) / 3600
            if age_hours > max_age_hours:
                try:
                    shutil.move(str(f), str(source_dir / f.name))
                    log_action(
                        "task_abandoned", self.agent_name, f.name,
                        f"Stale claim ({age_hours:.1f}h), returned to {source_dir.name}"
                    )
                    count += 1
                except (OSError, shutil.Error):
                    pass
        return count
