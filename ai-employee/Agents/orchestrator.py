"""
Orchestrator — Process Manager (Platinum Tier)
=================================================
Manages all agent processes with support for three modes:
  - standalone (Gold Tier compat, all agents on one machine)
  - cloud      (Cloud VM agents: cloud_agent, sync_manager, watchers)
  - local      (Local machine: local_agent, WhatsApp, payments)

Usage:
    python Agents/orchestrator.py              # standalone (all agents)
    python Agents/orchestrator.py --cloud      # cloud mode
    python Agents/orchestrator.py --local      # local mode
    python Agents/orchestrator.py --minimal    # core agents only
"""

import subprocess
import sys
import time
import signal
from pathlib import Path
from datetime import datetime, timezone

try:
    from Agents.config import AGENTS_DIR, VAULT_ROOT, AGENT_MODE, now_iso, now_local_iso
    from Agents.action_logger import log_action
except ImportError:
    from config import AGENTS_DIR, VAULT_ROOT, AGENT_MODE, now_iso, now_local_iso
    from action_logger import log_action


# ── Agent definitions ──────────────────────────────────────────────────────

AGENTS_STANDALONE = [
    {"name": "inbox_watcher",      "script": "inbox_watcher.py",     "group": "watcher",    "required": True},
    {"name": "gmail_watcher",      "script": "gmail_watcher.py",     "group": "watcher",    "required": False},
    {"name": "whatsapp_watcher",   "script": "whatsapp_watcher.py",  "group": "watcher",    "required": False},
    {"name": "task_router",        "script": "task_router.py",       "group": "reasoning",  "required": True},
    {"name": "reasoning_loop",     "script": "reasoning_loop.py",    "group": "reasoning",  "required": True},
    {"name": "hitl_approval",      "script": "hitl_approval.py",     "group": "control",    "required": True},
    {"name": "audit_agent",        "script": "audit_agent.py",       "group": "reporting",  "required": False},
]

AGENTS_CLOUD = [
    {"name": "cloud_agent",        "script": "cloud_agent.py",       "group": "cloud",      "required": True},
    {"name": "sync_manager",       "script": "sync_manager.py",      "group": "sync",       "required": True,  "args": ["--auto"]},
    {"name": "inbox_watcher",      "script": "inbox_watcher.py",     "group": "watcher",    "required": True},
    {"name": "gmail_watcher",      "script": "gmail_watcher.py",     "group": "watcher",    "required": False},
    {"name": "task_router",        "script": "task_router.py",       "group": "reasoning",  "required": True},
    {"name": "reasoning_loop",     "script": "reasoning_loop.py",    "group": "reasoning",  "required": True},
    {"name": "audit_agent",        "script": "audit_agent.py",       "group": "reporting",  "required": False},
]

AGENTS_LOCAL = [
    {"name": "local_agent",        "script": "local_agent.py",       "group": "local",      "required": True},
    {"name": "sync_manager",       "script": "sync_manager.py",      "group": "sync",       "required": True,  "args": ["--auto"]},
    {"name": "whatsapp_watcher",   "script": "whatsapp_watcher.py",  "group": "watcher",    "required": False},
    {"name": "hitl_approval",      "script": "hitl_approval.py",     "group": "control",    "required": True},
    {"name": "inbox_watcher",      "script": "inbox_watcher.py",     "group": "watcher",    "required": True},
]

AGENTS_MINIMAL = [
    {"name": "inbox_watcher",      "script": "inbox_watcher.py",     "group": "watcher",    "required": True},
    {"name": "task_router",        "script": "task_router.py",       "group": "reasoning",  "required": True},
    {"name": "reasoning_loop",     "script": "reasoning_loop.py",    "group": "reasoning",  "required": True},
    {"name": "hitl_approval",      "script": "hitl_approval.py",     "group": "control",    "required": True},
]


# ── Agent Process ──────────────────────────────────────────────────────────

class AgentProcess:
    MAX_RESTARTS = 5

    def __init__(self, name: str, script: str, group: str = "",
                 required: bool = True, args: list = None):
        self.name = name
        self.script = script
        self.group = group
        self.required = required
        self.args = args or []
        self.process = None
        self.status = "idle"
        self.restarts = 0

    def start(self) -> bool:
        script_path = AGENTS_DIR / self.script
        if not script_path.exists():
            print(f"  ⚠️  {self.name}: script not found ({self.script})")
            self.status = "missing"
            return False

        try:
            cmd = [sys.executable, str(script_path)] + self.args
            self.process = subprocess.Popen(
                cmd,
                cwd=str(VAULT_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self.status = "running"
            print(f"  🟢  {self.name} started (PID {self.process.pid})")
            log_action("agent_started", "orchestrator", self.name,
                       f"Started (PID {self.process.pid})")
            return True
        except Exception as e:
            self.status = "failed"
            print(f"  ❌  {self.name}: failed to start — {e}")
            return False

    def is_alive(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def get_exit_info(self) -> str:
        if self.process and self.process.stderr:
            try:
                err = self.process.stderr.read()
                if err:
                    return err.decode("utf-8", errors="replace")[-500:]
            except Exception:
                pass
        return ""

    def stop(self) -> None:
        if self.process and self.is_alive():
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.status = "stopped"

    def restart(self) -> bool:
        if self.restarts >= self.MAX_RESTARTS:
            self.status = "abandoned"
            print(f"  💀  {self.name}: max restarts reached ({self.MAX_RESTARTS})")
            return False

        self.stop()
        self.restarts += 1
        diag = self.get_exit_info()
        if diag:
            print(f"  🔍  {self.name} crash: {diag[:200]}")
        return self.start()


# ── Orchestrator ───────────────────────────────────────────────────────────

class Orchestrator:
    HEALTH_CHECK_INTERVAL = 30

    def __init__(self, agents_config: list[dict], mode: str):
        self.mode = mode
        self.agents = [AgentProcess(**cfg) for cfg in agents_config]
        self.running = True

    def start_all(self) -> None:
        for agent in self.agents:
            agent.start()
            time.sleep(0.5)  # stagger

    def stop_all(self) -> None:
        print(f"\n⏹️  Stopping all agents...")
        for agent in self.agents:
            agent.stop()
        print("  ✅  All agents stopped")

    def health_check(self) -> None:
        for agent in self.agents:
            if agent.status in ("abandoned", "missing", "idle"):
                continue
            if not agent.is_alive() and agent.status == "running":
                agent.status = "crashed"
                print(f"  💀  {agent.name} crashed — restarting "
                      f"({agent.restarts + 1}/{agent.MAX_RESTARTS})")
                agent.restart()

    def status_line(self) -> str:
        states = []
        for a in self.agents:
            icon = {"running": "🟢", "stopped": "⏹️", "crashed": "💀",
                    "abandoned": "☠️", "missing": "❓", "failed": "❌",
                    "idle": "⚪"}.get(a.status, "❔")
            states.append(f"{icon}{a.name}")
        return " | ".join(states)

    def run(self) -> None:
        mode_icons = {"standalone": "🏗️", "cloud": "☁️", "local": "🏠", "minimal": "⚡"}
        icon = mode_icons.get(self.mode, "🚀")
        print(f"\n{icon}  Orchestrator — Starting {len(self.agents)} agents "
              f"({self.mode} mode)")
        print(f"    Time: {now_local_iso()}\n")

        self.start_all()
        log_action("orchestrator_started", "orchestrator", self.mode,
                   f"Started {len(self.agents)} agents in {self.mode} mode")

        print(f"\n  ✅  All agents active — health check every "
              f"{self.HEALTH_CHECK_INTERVAL}s")
        print(f"  {self.status_line()}\n")

        def shutdown(sig, frame):
            self.running = False
            print(f"\n⚠️  Received shutdown signal")
            self.stop_all()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown)

        while self.running:
            time.sleep(self.HEALTH_CHECK_INTERVAL)
            self.health_check()


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    if "--cloud" in sys.argv:
        mode = "cloud"
        agents = AGENTS_CLOUD
    elif "--local" in sys.argv:
        mode = "local"
        agents = AGENTS_LOCAL
    elif "--minimal" in sys.argv:
        mode = "minimal"
        agents = AGENTS_MINIMAL
    else:
        mode = AGENT_MODE if AGENT_MODE in ("cloud", "local") else "standalone"
        agents = {
            "cloud": AGENTS_CLOUD,
            "local": AGENTS_LOCAL,
            "standalone": AGENTS_STANDALONE,
        }.get(mode, AGENTS_STANDALONE)

    orch = Orchestrator(agents, mode)
    orch.run()


if __name__ == "__main__":
    main()
