# Installing Explicitly on Orange Pi Zero 3

## System Requirements

- Orange Pi Zero 3 with 1GB+ RAM
- Debian Bookworm or Ubuntu 22.04+ ARM64
- USB audio interface (input + output)
- 8GB+ microSD card (16GB recommended)
- Network access (Ethernet recommended)

## Step 1: Prepare Orange Pi

### Flash OS

1. Download Debian/Ubuntu image for Orange Pi Zero 3:
   - Official: http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/service-and-support/Orange-Pi-Zero-3.html
   - Or use Armbian: https://www.armbian.com/orange-pi-zero-3/

2. Flash to microSD card using balenaEtcher or Rufus

3. Boot Orange Pi and complete initial setup

### Initial Configuration

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Set hostname
sudo hostnamectl set-hostname explicitly

# Enable real-time scheduling for audio
sudo nano /etc/security/limits.conf
```

Add these lines:
```
explicitly  -  rtprio     80
explicitly  -  memlock    unlimited
@audio      -  rtprio     80
@audio      -  memlock    unlimited
```

### Create Service User

```bash
# Create dedicated user for running the service
sudo useradd -r -s /bin/false -G audio explicitly

# Create directories
sudo mkdir -p /usr/share/explicitly/models
sudo mkdir -p /etc/explicitly
sudo mkdir -p /var/log/explicitly

# Set permissions
sudo chown -R explicitly:audio /usr/share/explicitly
sudo chown -R explicitly:audio /etc/explicitly
sudo chown -R explicitly:audio /var/log/explicitly
```

## Step 2: Install Dependencies

```bash
# Audio libraries
sudo apt install -y alsa-utils libasound2

# Required for running the daemon
sudo apt install -y libstdc++6 libc6

# Optional: for monitoring
sudo apt install -y htop

# Test ALSA
aplay -l  # List playback devices
arecord -l  # List capture devices
```

## Step 3: Setup USB Audio

### Connect USB Audio Interface

1. Plug in USB audio interface
2. Check if detected:

```bash
lsusb  # Should show your USB audio device
aplay -l  # Should list the device
```

### Configure ALSA

Create/edit `/etc/asound.conf`:

```bash
sudo nano /etc/asound.conf
```

Add (adjust card numbers as needed):

```
defaults.pcm.card 1
defaults.ctl.card 1

pcm.!default {
    type hw
    card 1
    device 0
}

ctl.!default {
    type hw
    card 1
}
```

### Test Audio

```bash
# Record 5 seconds of audio
arecord -D hw:1,0 -f S16_LE -r 48000 -c 2 -d 5 test.wav

# Play it back
aplay -D hw:1,0 test.wav

# Check latency
aplay -D hw:1,0 -r 48000 -f S16_LE -c 2 --period-size=512 test.wav
```

## Step 4: Download Whisper Model

```bash
cd /usr/share/explicitly/models

# Download tiny model (75 MB - recommended for 1GB Orange Pi)
sudo wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin

# Verify download
ls -lh ggml-tiny.en.bin  # Should be ~75 MB

# Set permissions
sudo chown explicitly:audio ggml-tiny.en.bin
```

**Alternative models** (if you have 2GB+ RAM):

```bash
# Base model (142 MB - better accuracy)
sudo wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin

# Small model (487 MB - best accuracy, requires 2GB RAM)
sudo wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin
```

## Step 5: Copy Profanity Lexicon

```bash
# Copy from your repository
sudo cp /path/to/explicitly/desktop/Models/profanity_en.txt /usr/share/explicitly/

# Set permissions
sudo chown explicitly:audio /usr/share/explicitly/profanity_en.txt
```

## Step 6: Install Explicitly Daemon

### Option A: From Pre-Built Binary

```bash
# Copy binary to Orange Pi (from your build machine)
scp explicitly-daemon orangepi@explicitly.local:~/

# Install
sudo cp explicitly-daemon /usr/local/bin/
sudo chmod +x /usr/local/bin/explicitly-daemon
sudo chown explicitly:audio /usr/local/bin/explicitly-daemon
```

### Option B: Build from Source

See `BUILD.md` for full build instructions.

## Step 7: Configure Explicitly

```bash
# Copy example config
sudo cp config.yaml.example /etc/explicitly/config.yaml

# Edit configuration
sudo nano /etc/explicitly/config.yaml
```

**Important settings to check**:

```yaml
audio:
  input_device: "hw:1,0"   # Update based on aplay -l
  output_device: "hw:1,0"  # Update based on aplay -l
  sample_rate: 48000
  buffer_size: 512

processing:
  model_path: "/usr/share/explicitly/models/ggml-tiny.en.bin"
  profanity_lexicon: "/usr/share/explicitly/profanity_en.txt"
  censor_mode: "reverse"

api:
  port: 8080
  bind_address: "0.0.0.0"
```

## Step 8: Install Systemd Service

```bash
# Copy service file
sudo cp explicitly.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable explicitly

# Start service
sudo systemctl start explicitly

# Check status
sudo systemctl status explicitly
```

Expected output:
```
● explicitly.service - Explicitly Audio Profanity Filter
     Loaded: loaded (/etc/systemd/system/explicitly.service; enabled)
     Active: active (running) since ...
```

## Step 9: Test and Verify

### Check API

```bash
# Get status
curl http://localhost:8080/api/status

# Start processing
curl -X POST http://localhost:8080/api/start

# Stop processing
curl -X POST http://localhost:8080/api/stop
```

### Monitor Logs

```bash
# Follow logs in real-time
sudo journalctl -u explicitly -f

# View recent logs
sudo journalctl -u explicitly -n 100
```

### Check Resource Usage

```bash
# Monitor CPU and memory
htop

# Check specifically for explicitly-daemon
ps aux | grep explicitly
```

Expected resource usage:
- **Idle**: ~30 MB RAM, 2-5% CPU
- **Processing**: ~200-300 MB RAM, 50-80% CPU (during transcription bursts)

## Step 10: Network Access (Optional)

If you want to access the API from other devices:

```bash
# Find Orange Pi IP address
hostname -I

# Test from another computer
curl http://<orange-pi-ip>:8080/api/status
```

### Firewall Configuration

If using firewall:

```bash
sudo apt install -y ufw
sudo ufw allow 8080/tcp
sudo ufw enable
```

## Troubleshooting

### Service Won't Start

```bash
# Check detailed error
sudo journalctl -u explicitly -n 50 --no-pager

# Common issues:
# 1. Model file not found - check path in config.yaml
# 2. ALSA device not available - check with aplay -l
# 3. Permission denied - check user "explicitly" has audio group
```

### Audio Device Not Found

```bash
# List all ALSA devices
aplay -L
arecord -L

# Update config.yaml with correct device name
sudo nano /etc/explicitly/config.yaml
sudo systemctl restart explicitly
```

### High CPU Usage

```bash
# Check buffer size in config - increase if CPU is maxed out
sudo nano /etc/explicitly/config.yaml

# Change buffer_size from 512 to 1024 or 2048
audio:
  buffer_size: 1024

sudo systemctl restart explicitly
```

### Out of Memory

```bash
# Check memory usage
free -h

# If using tiny model and still OOM, disable features:
sudo nano /etc/explicitly/config.yaml

processing:
  enable_vocal_filter: false
  enable_timestamp_refiner: false

sudo systemctl restart explicitly
```

## Uninstallation

```bash
# Stop and disable service
sudo systemctl stop explicitly
sudo systemctl disable explicitly

# Remove files
sudo rm /usr/local/bin/explicitly-daemon
sudo rm /etc/systemd/system/explicitly.service
sudo rm -rf /etc/explicitly
sudo rm -rf /usr/share/explicitly
sudo rm -rf /var/log/explicitly

# Remove user
sudo userdel explicitly

# Reload systemd
sudo systemctl daemon-reload
```

## Performance Tuning

### For 1GB RAM Orange Pi

```yaml
audio:
  buffer_size: 1024  # Larger buffer = less CPU
  periods: 2         # Fewer periods = less memory

processing:
  enable_vocal_filter: true     # Keep for accuracy
  enable_timestamp_refiner: false  # Disable to save CPU
```

### For 1.5GB+ RAM Orange Pi

```yaml
audio:
  buffer_size: 512   # Lower latency
  periods: 4

processing:
  enable_vocal_filter: true
  enable_timestamp_refiner: true  # Better censorship boundaries
```

## Next Steps

- Set up automatic model updates
- Configure network audio streaming (if needed)
- Add monitoring/alerts for service health
- Create backup scripts for configuration

## Support

For issues:
1. Check logs: `sudo journalctl -u explicitly -f`
2. Verify ALSA: `aplay -l` and `arecord -l`
3. Test API: `curl http://localhost:8080/api/health`
4. Monitor resources: `htop`
