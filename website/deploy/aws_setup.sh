#!/bin/bash
# AWS EC2 Setup Script for Explicitly
# Run this on a fresh Ubuntu 22.04 instance with GPU support

set -e

echo "===== Explicitly AWS Setup ====="

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    ffmpeg \
    git \
    nginx \
    certbot \
    python3-certbot-nginx \
    build-essential

# Install NVIDIA drivers and CUDA (for GPU instances)
echo "Installing NVIDIA drivers..."
sudo apt-get install -y ubuntu-drivers-common
sudo ubuntu-drivers autoinstall

# Install Docker
echo "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install NVIDIA Container Toolkit
echo "Installing NVIDIA Container Toolkit..."
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Assume we're already in the explicitly directory with .env configured
echo "Configuring application..."
APP_DIR=$(pwd)

# Create virtual environment
echo "Setting up Python virtual environment..."
python3.10 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements-prod.txt

# Create data directories
echo "Creating data directories..."
mkdir -p data/{uploads,output,stems,work,logs}

# Configure Nginx
echo "Configuring Nginx..."
sudo cp nginx.conf /etc/nginx/sites-available/explicitly
sudo ln -sf /etc/nginx/sites-available/explicitly /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/explicitly.service > /dev/null <<EOF
[Unit]
Description=Explicitly Profanity Filter
After=network.target

[Service]
Type=notify
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn -c gunicorn_config.py "explicitly.web:app"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Start service
echo "Starting Explicitly service..."
sudo systemctl daemon-reload
sudo systemctl enable explicitly
sudo systemctl start explicitly

# Configure firewall
echo "Configuring firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# Display status
echo ""
echo "===== Setup Complete! ====="
echo ""
echo "Service status:"
sudo systemctl status explicitly --no-pager
echo ""
echo "Next steps:"
echo "1. Point your domain to this server's IP address"
echo "2. Run: sudo certbot --nginx -d your-domain.com"
echo "3. Test the application at http://$(curl -s ifconfig.me)"
echo ""
echo "Useful commands:"
echo "  - View logs: sudo journalctl -u explicitly -f"
echo "  - Restart service: sudo systemctl restart explicitly"
echo "  - Check GPU: nvidia-smi"
