#!/bin/bash
# Streamlined setup script for Explicitly
# Use this when system dependencies are already installed
# Run from inside the explicitly directory with .env configured

set -e

echo "===== Explicitly Application Setup ====="

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

# Configure firewall (if not already configured)
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
echo "Application accessible at: http://$(curl -s ifconfig.me)"
echo ""
echo "Useful commands:"
echo "  - View logs: sudo journalctl -u explicitly -f"
echo "  - Restart service: sudo systemctl restart explicitly"
echo "  - Check GPU: nvidia-smi"
echo "  - Test app: curl http://localhost"
