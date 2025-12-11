# Explicitly Deployment Guide

Complete guide to deploy Explicitly to production on various platforms.

## Table of Contents
1. [Quick Deploy Options](#quick-deploy-options)
2. [AWS EC2 Deployment](#aws-ec2-deployment)
3. [Docker Deployment](#docker-deployment)
4. [Render.com Deployment](#rendercom-deployment)
5. [Post-Deployment Setup](#post-deployment-setup)
6. [Monitoring & Maintenance](#monitoring--maintenance)

---

## Quick Deploy Options

### Fastest: Render.com (15 minutes)
**Cost**: Free tier or $7/month  
**GPU**: Not available on free tier  
**Best for**: Testing, small-scale use

```bash
# 1. Push code to GitHub
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/explicitly.git
git push -u origin main

# 2. Go to https://render.com
# 3. Click "New +" → "Blueprint"
# 4. Connect your GitHub repo
# 5. Deploy automatically uses deploy/render.yaml
```

### Docker (30 minutes)
**Cost**: Your server costs  
**GPU**: Supported with nvidia-docker  
**Best for**: Any server with Docker

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

---

## AWS EC2 Deployment

### Prerequisites
- AWS account
- Domain name (optional but recommended)
- SSH client

### Step 1: Launch EC2 Instance

1. **Go to AWS Console** → EC2 → Launch Instance

2. **Select AMI**:
   - Ubuntu Server 22.04 LTS
   - 64-bit (x86)

3. **Choose Instance Type**:
   - **For GPU**: `g4dn.xlarge` ($0.526/hr, ~$380/month)
   - **For CPU only**: `t3.xlarge` ($0.1664/hr, ~$120/month)
   - **Budget option**: `t3.medium` ($0.0416/hr, ~$30/month)

4. **Configure Storage**:
   - Root: 30 GB gp3
   - Additional EBS: 50 GB for data (optional)

5. **Security Group**:
   ```
   Port 22  (SSH)     - Your IP only
   Port 80  (HTTP)    - 0.0.0.0/0
   Port 443 (HTTPS)   - 0.0.0.0/0
   ```

6. **Create/Select Key Pair**:
   - Download .pem file
   - Save as `explicitly-key.pem`

7. **Launch Instance**

### Step 2: Connect to Instance

```bash
# Windows (PowerShell)
ssh -i "explicitly-key.pem" ubuntu@<PUBLIC_IP>

# Or use PuTTY with converted .ppk key
```

### Step 3: Run Automated Setup

```bash
# On the EC2 instance
cd ~
git clone https://github.com/AndrewMahran7/explicitly.git
cd explicitly
chmod +x deploy/aws_setup.sh
./deploy/aws_setup.sh
```

The script will:
- ✅ Install Python, ffmpeg, nginx
- ✅ Install NVIDIA drivers (GPU instances)
- ✅ Install Docker + NVIDIA Container Toolkit
- ✅ Set up virtual environment
- ✅ Install dependencies
- ✅ Configure nginx
- ✅ Create systemd service
- ✅ Configure firewall

### Step 4: Configure Domain (Optional)

```bash
# Update nginx config with your domain
sudo nano /etc/nginx/sites-available/explicitly
# Change: server_name your-domain.com;

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
# Follow prompts, enter email

# Restart nginx
sudo systemctl restart nginx
```

### Step 5: Verify Deployment

```bash
# Check service status
sudo systemctl status explicitly

# View logs
sudo journalctl -u explicitly -f

# Test GPU (if applicable)
nvidia-smi

# Test application
curl http://localhost:5000
```

Access at: `http://<PUBLIC_IP>` or `https://your-domain.com`

---

## Docker Deployment

### Local Testing

```bash
# Build image
docker build -t explicitly:latest .

# Run container
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  --name explicitly \
  explicitly:latest

# With GPU support
docker run -d \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  --gpus all \
  --name explicitly \
  explicitly:latest

# View logs
docker logs -f explicitly

# Stop container
docker stop explicitly
docker rm explicitly
```

### Using Docker Compose

```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f explicitly

# Restart
docker-compose restart

# Stop
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

### Production Docker Deployment

```bash
# On production server
cd /opt
git clone https://github.com/yourusername/explicitly.git
cd explicitly

# Set environment variables
cp .env.example .env
nano .env  # Edit configuration

# Start with compose
docker-compose -f docker-compose.yml up -d

# Set up auto-restart
sudo systemctl enable docker
```

---

## Render.com Deployment

### Step 1: Prepare Repository

```bash
# Ensure render.yaml is in deploy/ directory
# Ensure requirements-prod.txt exists

# Push to GitHub
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

### Step 2: Deploy on Render

1. Go to https://render.com
2. Sign in with GitHub
3. Click **"New +"** → **"Blueprint"**
4. Select your `explicitly` repository
5. Render will detect `deploy/render.yaml`
6. Click **"Apply"**

### Step 3: Configure Environment

In Render dashboard:
1. Go to your service
2. Click **"Environment"**
3. Add:
   ```
   SECRET_KEY: [generate random]
   FLASK_ENV: production
   ```

### Step 4: Monitor Deployment

- View logs in real-time
- First deploy takes ~10 minutes (downloading models)
- Service will be available at: `https://explicitly.onrender.com`

### Limitations on Free Tier
- ❌ No GPU support
- ❌ Service sleeps after 15 min inactivity
- ❌ 512MB RAM (may cause OOM)
- ✅ Good for testing/demo

**Upgrade to paid plan** ($7-25/month) for:
- Always-on service
- More RAM/CPU
- Custom domain

---

## Post-Deployment Setup

### 1. Test All Features

```bash
# Test upload endpoint
curl -X POST -F "file=@test.mp3" \
  http://your-server:5000/upload

# Test GPU (if available)
curl http://your-server:5000/status
```

### 2. Configure Monitoring

```bash
# Install monitoring (AWS)
sudo apt-get install -y prometheus-node-exporter

# View system metrics
htop
nvidia-smi -l 1  # GPU monitoring
```

### 3. Set Up Backups

```bash
# Backup data directory daily
sudo crontab -e

# Add line:
0 2 * * * tar -czf /backups/explicitly-$(date +\%Y\%m\%d).tar.gz /home/ubuntu/explicitly/data
```

### 4. Configure Log Rotation

```bash
sudo tee /etc/logrotate.d/explicitly > /dev/null <<EOF
/home/ubuntu/explicitly/data/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 ubuntu ubuntu
}
EOF
```

---

## Monitoring & Maintenance

### View Logs

```bash
# Application logs
sudo journalctl -u explicitly -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Gunicorn logs
tail -f data/logs/gunicorn_error.log
```

### Check Resource Usage

```bash
# CPU/Memory
htop

# GPU
nvidia-smi

# Disk space
df -h

# Active connections
netstat -ant | grep :5000
```

### Restart Service

```bash
# Systemd service
sudo systemctl restart explicitly

# Docker
docker-compose restart

# Nginx
sudo systemctl restart nginx
```

### Update Application

```bash
# Pull latest code
cd /home/ubuntu/explicitly
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements-prod.txt

# Restart service
sudo systemctl restart explicitly
```

### Scale Up

**Add more workers:**
```bash
# Edit gunicorn_config.py
nano gunicorn_config.py
# Change: workers = 8

sudo systemctl restart explicitly
```

**Use multiple instances with load balancer:**
1. Launch 2-3 EC2 instances
2. Create Application Load Balancer
3. Add instances to target group
4. Point domain to ALB

---

## Cost Breakdown

### AWS EC2 (Monthly)

| Configuration | Instance | Cost/month | Use Case |
|--------------|----------|------------|----------|
| **Budget CPU** | t3.medium | $30 | Testing only |
| **Production CPU** | t3.xlarge | $120 | 10-50 jobs/day |
| **GPU Basic** | g4dn.xlarge | $380 | Fast processing |
| **GPU Production** | g4dn.2xlarge | $750 | High volume |

**Additional costs:**
- Storage: $5-10/month (50-100GB)
- Data transfer: $9/month per 100GB
- Load balancer: $16/month (if used)

### Render.com

| Tier | Cost | RAM | Use Case |
|------|------|-----|----------|
| **Free** | $0 | 512MB | Demo only |
| **Starter** | $7 | 512MB | Light use |
| **Standard** | $25 | 2GB | Production |
| **Pro** | $85 | 8GB | Heavy use |

---

## Troubleshooting

### Service won't start
```bash
# Check logs
sudo journalctl -u explicitly -xe

# Common issues:
# 1. Port 5000 already in use
sudo lsof -i :5000
sudo kill -9 <PID>

# 2. Python dependencies missing
source venv/bin/activate
pip install -r requirements-prod.txt

# 3. Permission issues
sudo chown -R ubuntu:ubuntu /home/ubuntu/explicitly
```

### Out of memory
```bash
# Check memory usage
free -h

# Reduce workers in gunicorn_config.py
nano gunicorn_config.py
# Change: workers = 2

# Add swap space
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### GPU not detected
```bash
# Verify driver
nvidia-smi

# Reinstall if needed
sudo ubuntu-drivers autoinstall
sudo reboot

# Test in Python
python -c "import torch; print(torch.cuda.is_available())"
```

### Slow processing
```bash
# Check if using GPU
nvidia-smi

# Monitor CPU usage
htop

# Check if model is downloaded
ls -lh ~/.cache/whisper/

# Reduce model size
# Edit web.py: change 'large-v2' to 'small'
```

---

## Security Checklist

- ✅ Change default SECRET_KEY
- ✅ Enable firewall (UFW)
- ✅ Use HTTPS with SSL certificate
- ✅ Restrict SSH to your IP
- ✅ Regular security updates: `sudo apt-get update && sudo apt-get upgrade`
- ✅ Use environment variables for secrets
- ✅ Enable fail2ban: `sudo apt-get install fail2ban`
- ✅ Regular backups
- ✅ Monitor logs for suspicious activity

---

## Support

- **Issues**: GitHub Issues
- **Email**: your-email@domain.com
- **Documentation**: https://github.com/yourusername/explicitly

---

## Next Steps

1. ✅ Deploy to chosen platform
2. ✅ Configure domain and SSL
3. ✅ Test with sample files
4. ✅ Set up monitoring
5. ✅ Configure backups
6. ✅ Share with users!
