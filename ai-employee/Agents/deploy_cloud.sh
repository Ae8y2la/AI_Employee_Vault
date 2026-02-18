#!/bin/bash
# ===========================================================================
# Cloud VM Deployment Script — AI Employee Vault (Platinum Tier)
# ===========================================================================
# Deploys the AI Employee system on a cloud VM (Oracle Cloud Free Tier,
# AWS, etc.) with:
#   - Cloud Agent (24/7 always-on)
#   - Orchestrator in cloud mode
#   - Git-based vault sync
#   - Systemd service for auto-restart
#   - Odoo Community (optional)
#
# Usage:
#   scp deploy_cloud.sh user@cloud-vm:~/
#   ssh user@cloud-vm 'chmod +x deploy_cloud.sh && ./deploy_cloud.sh'
# ===========================================================================

set -e

VAULT_DIR="$HOME/ai-employee"
REPO_URL="${CLOUD_SYNC_REMOTE:-}"
BRANCH="${CLOUD_SYNC_BRANCH:-main}"
PYTHON="python3"

echo "================================================"
echo "  ☁️  AI Employee — Cloud Deployment"
echo "================================================"

# ── System dependencies ─────────────────────────────────────────────────
echo ""
echo "📦  Installing system dependencies..."
sudo apt update -qq
sudo apt install -y python3 python3-pip python3-venv git curl -qq

# ── Clone or update repo ────────────────────────────────────────────────
if [ -d "$VAULT_DIR/.git" ]; then
    echo "📁  Vault exists, pulling latest..."
    cd "$VAULT_DIR"
    git pull origin "$BRANCH"
else
    if [ -z "$REPO_URL" ]; then
        echo "📁  Creating fresh vault..."
        mkdir -p "$VAULT_DIR"
        cd "$VAULT_DIR"
        git init
    else
        echo "📁  Cloning vault from $REPO_URL..."
        git clone "$REPO_URL" "$VAULT_DIR"
        cd "$VAULT_DIR"
    fi
fi

# ── Python dependencies ─────────────────────────────────────────────────
echo ""
echo "🐍  Installing Python dependencies..."
$PYTHON -m pip install --user google-auth google-auth-oauthlib google-api-python-client 2>/dev/null || true

# ── Create cloud .env if missing ─────────────────────────────────────────
if [ ! -f "$VAULT_DIR/.env" ]; then
    echo ""
    echo "📝  Creating cloud .env from template..."
    if [ -f "$VAULT_DIR/.env.template" ]; then
        cp "$VAULT_DIR/.env.template" "$VAULT_DIR/.env"
    fi
    # Set cloud mode
    echo "" >> "$VAULT_DIR/.env"
    echo "# Cloud deployment settings" >> "$VAULT_DIR/.env"
    echo "AGENT_MODE=cloud" >> "$VAULT_DIR/.env"
    echo "DRY_RUN=true" >> "$VAULT_DIR/.env"
    echo ""
    echo "⚠️   Edit $VAULT_DIR/.env to add your credentials"
fi

# ── Ensure folder structure ──────────────────────────────────────────────
echo ""
echo "📁  Creating vault folders..."
$PYTHON -c "
import sys; sys.path.insert(0, '$VAULT_DIR')
from Agents.config import ensure_dirs
ensure_dirs()
print('  ✅  All directories created')
"

# ── Systemd service ──────────────────────────────────────────────────────
echo ""
echo "🔧  Creating systemd service..."

sudo tee /etc/systemd/system/ai-employee-cloud.service > /dev/null <<EOF
[Unit]
Description=AI Employee Cloud Agent
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$VAULT_DIR
ExecStart=$PYTHON $VAULT_DIR/Agents/cloud_agent.py
Restart=always
RestartSec=30
StandardOutput=append:$VAULT_DIR/Logs/cloud_agent.log
StandardError=append:$VAULT_DIR/Logs/cloud_agent_error.log
Environment="AGENT_MODE=cloud"

[Install]
WantedBy=multi-user.target
EOF

# ── Sync service ─────────────────────────────────────────────────────────
sudo tee /etc/systemd/system/ai-employee-sync.service > /dev/null <<EOF
[Unit]
Description=AI Employee Vault Sync
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$VAULT_DIR
ExecStart=$PYTHON $VAULT_DIR/Agents/sync_manager.py --auto
Restart=always
RestartSec=60
StandardOutput=append:$VAULT_DIR/Logs/sync.log
StandardError=append:$VAULT_DIR/Logs/sync_error.log

[Install]
WantedBy=multi-user.target
EOF

# ── Odoo Community (optional) ────────────────────────────────────────────
echo ""
read -p "Install Odoo Community? [y/N]: " INSTALL_ODOO
if [ "$INSTALL_ODOO" = "y" ] || [ "$INSTALL_ODOO" = "Y" ]; then
    echo "🏢  Installing Odoo Community..."
    sudo apt install -y postgresql -qq
    sudo -u postgres createuser -s $USER 2>/dev/null || true
    sudo -u postgres createdb odoo 2>/dev/null || true
    pip install --user odoo 2>/dev/null || {
        echo "  ⚠️  Odoo pip install failed — try manual install:"
        echo "  https://www.odoo.com/documentation/17.0/administration/install.html"
    }
fi

# ── Enable and start services ────────────────────────────────────────────
echo ""
echo "🚀  Enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable ai-employee-cloud.service
sudo systemctl enable ai-employee-sync.service

echo ""
read -p "Start services now? [Y/n]: " START_NOW
if [ "$START_NOW" != "n" ] && [ "$START_NOW" != "N" ]; then
    sudo systemctl start ai-employee-cloud.service
    sudo systemctl start ai-employee-sync.service
    echo "  ✅  Services started!"
fi

# ── Summary ──────────────────────────────────────────────────────────────
echo ""
echo "================================================"
echo "  ✅  Cloud Deployment Complete!"
echo "================================================"
echo ""
echo "  Vault:     $VAULT_DIR"
echo "  Mode:      cloud"
echo "  Services:"
echo "    ai-employee-cloud  — Cloud Agent (24/7)"
echo "    ai-employee-sync   — Vault Sync"
echo ""
echo "  Commands:"
echo "    sudo systemctl status ai-employee-cloud"
echo "    sudo systemctl status ai-employee-sync"
echo "    sudo journalctl -u ai-employee-cloud -f"
echo "    tail -f $VAULT_DIR/Logs/cloud_agent.log"
echo ""
echo "  Next steps:"
echo "    1. Edit $VAULT_DIR/.env with your credentials"
echo "    2. Set CLOUD_SYNC_REMOTE in .env for git sync"
echo "    3. Set DRY_RUN=false when ready"
echo "================================================"
