#!/bin/bash

# Initial Orange Pi Zero 3 Setup Script
# Prepares the system for Explicitly installation

set -e  # Exit on error

echo "==========================================="
echo "  Explicitly - Orange Pi Zero 3 Setup"
echo "==========================================="
echo

# Check if running on ARM
if [ "$(uname -m)" != "aarch64" ]; then
    echo "ERROR: This script must run on ARM64 (aarch64) system"
    exit 1
fi

echo "[1/8] Updating system packages..."
sudo apt update
sudo apt upgrade -y

echo "[2/8] Installing build dependencies..."
sudo apt install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl

echo "[3/8] Installing audio libraries..."
sudo apt install -y \
    alsa-utils \
    libasound2-dev \
    libasound2

echo "[4/8] Installing monitoring tools..."
sudo apt install -y \
    htop \
    iotop \
    iftop

echo "[5/8] Creating explicitly user..."
if ! id "explicitly" &>/dev/null; then
    sudo useradd -r -s /bin/false -G audio explicitly
    echo "  - User 'explicitly' created"
else
    echo "  - User 'explicitly' already exists"
fi

echo "[6/8] Creating directories..."
sudo mkdir -p /usr/share/explicitly/models
sudo mkdir -p /etc/explicitly
sudo mkdir -p /var/log/explicitly

sudo chown -R explicitly:audio /usr/share/explicitly
sudo chown -R explicitly:audio /etc/explicitly
sudo chown -R explicitly:audio /var/log/explicitly

echo "[7/8] Configuring real-time audio priorities..."
if ! grep -q "explicitly.*rtprio" /etc/security/limits.conf; then
    sudo tee -a /etc/security/limits.conf > /dev/null <<EOF

# Explicitly Audio - Real-time priority for audio processing
explicitly  -  rtprio     80
explicitly  -  memlock    unlimited
@audio      -  rtprio     80
@audio      -  memlock    unlimited
EOF
    echo "  - Real-time limits configured"
else
    echo "  - Real-time limits already configured"
fi

echo "[8/8] Setting CPU governor to performance..."
if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
    for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        echo performance | sudo tee $cpu > /dev/null
    done
    echo "  - CPU governor set to 'performance'"
    
    # Make permanent
    if ! grep -q "GOVERNOR=" /etc/default/cpufrequtils 2>/dev/null; then
        sudo tee /etc/default/cpufrequtils > /dev/null <<EOF
GOVERNOR="performance"
EOF
        echo "  - CPU governor configured to persist on reboot"
    fi
else
    echo "  - CPU frequency scaling not available or already configured"
fi

echo
echo "==========================================="
echo "  Setup Complete!"
echo "==========================================="
echo
echo "System is ready for Explicitly installation."
echo
echo "Next steps:"
echo "  1. Build whisper.cpp: ./scripts/build_whisper.sh"
echo "  2. Build Explicitly: ./scripts/build_explicitly.sh"
echo "  3. Install: sudo make install (from build directory)"
echo
echo "IMPORTANT: Reboot required for real-time priority changes to take effect"
echo "  sudo reboot"
echo
