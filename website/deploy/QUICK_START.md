# Quick Start Deployment

Choose your deployment method:

## 1. Render.com (Easiest - 15 minutes)

```bash
# 1. Push to GitHub
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/explicitly.git
git push -u origin main

# 2. Go to https://render.com and sign in
# 3. Click "New +" → "Blueprint"
# 4. Connect your repo
# 5. Done! URL: https://explicitly.onrender.com
```

**Cost**: Free (with limitations) or $7/month

---

## 2. AWS EC2 (Most Powerful - 1 hour)

```bash
# 1. Launch Ubuntu 22.04 EC2 instance
#    - Instance type: g4dn.xlarge (GPU) or t3.xlarge (CPU)
#    - Security groups: Allow ports 22, 80, 443

# 2. SSH into instance
ssh -i your-key.pem ubuntu@<EC2_IP>

# 3. Run automated setup
git clone https://github.com/YOUR_USERNAME/explicitly.git
cd explicitly
chmod +x deploy/aws_setup.sh
./deploy/aws_setup.sh

# 4. Access at http://<EC2_IP>
```

**Cost**: $30-$380/month depending on instance type

---

## 3. Docker (Any Server - 30 minutes)

```bash
# 1. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 2. Clone and run
git clone https://github.com/YOUR_USERNAME/explicitly.git
cd explicitly
docker-compose up -d

# 3. Access at http://localhost:5000
```

**Cost**: Your server costs

---

## 4. Local Windows (Development)

```powershell
# Already running!
python start_web.py

# Access at http://localhost:5000
```

---

## Need Help?

See full guide: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
