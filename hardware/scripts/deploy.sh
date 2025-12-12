#!/bin/bash

# Deploy Explicitly to Orange Pi Zero 3 via SSH
# Run this from your development machine

set -e

# Configuration
ORANGE_PI_USER="orangepi"
ORANGE_PI_HOST=""
BUILD_DIR="build"

echo "==========================================="
echo "  Deploy Explicitly to Orange Pi Zero 3"
echo "==========================================="
echo

# Get Orange Pi hostname/IP
if [ -z "$ORANGE_PI_HOST" ]; then
    read -p "Enter Orange Pi hostname or IP (e.g., orangepi.local): " ORANGE_PI_HOST
fi

SSH_TARGET="$ORANGE_PI_USER@$ORANGE_PI_HOST"

# Check if binary exists
if [ ! -f "$BUILD_DIR/explicitly-daemon" ]; then
    echo "ERROR: explicitly-daemon not found in $BUILD_DIR"
    echo "Build first with: ./scripts/build_explicitly.sh"
    exit 1
fi

echo "[1/5] Testing SSH connection..."
if ! ssh "$SSH_TARGET" "echo 'SSH connection successful'"; then
    echo "ERROR: Cannot connect to $SSH_TARGET"
    echo "Check hostname/IP and SSH access"
    exit 1
fi

echo "[2/5] Creating directories on Orange Pi..."
ssh "$SSH_TARGET" "sudo mkdir -p /usr/local/bin /etc/explicitly /usr/share/explicitly"

echo "[3/5] Copying binary..."
scp "$BUILD_DIR/explicitly-daemon" "$SSH_TARGET:~/"
ssh "$SSH_TARGET" "sudo mv ~/explicitly-daemon /usr/local/bin/ && sudo chmod +x /usr/local/bin/explicitly-daemon"

echo "[4/5] Copying configuration..."
scp "config.yaml.example" "$SSH_TARGET:~/"
ssh "$SSH_TARGET" "sudo mv ~/config.yaml.example /etc/explicitly/config.yaml"

echo "[5/5] Copying systemd service..."
scp "explicitly.service" "$SSH_TARGET:~/"
ssh "$SSH_TARGET" "sudo mv ~/explicitly.service /etc/systemd/system/ && sudo systemctl daemon-reload"

echo
echo "==========================================="
echo "  Deployment complete!"
echo "==========================================="
echo
echo "Next steps on Orange Pi:"
echo "  1. Download model: sudo ./scripts/download_models.sh"
echo "  2. Copy profanity lexicon:"
echo "     scp ../desktop/Models/profanity_en.txt $SSH_TARGET:~/"
echo "     ssh $SSH_TARGET 'sudo mv ~/profanity_en.txt /usr/share/explicitly/'"
echo "  3. Edit config: ssh $SSH_TARGET 'sudo nano /etc/explicitly/config.yaml'"
echo "  4. Start service: ssh $SSH_TARGET 'sudo systemctl start explicitly'"
echo "  5. Check status: ssh $SSH_TARGET 'sudo systemctl status explicitly'"
echo
