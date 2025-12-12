# Explicitly Hardware - Orange Pi Zero 3 Port

## Overview

This is a headless, lightweight port of the Explicitly Desktop profanity filter designed to run on the **Orange Pi Zero 3** (ARM64 Linux). The desktop GUI has been removed and replaced with a daemon process that can be controlled via HTTP API or configuration files.

## Target Hardware: Orange Pi Zero 3

- **SoC**: Allwinner H618 (ARM Cortex-A53 quad-core @ 1.5GHz)
- **RAM**: 4GB (full-featured configuration)
- **Architecture**: ARM64 (aarch64)
- **OS**: Debian Bookworm or Ubuntu 22.04+ ARM64
- **Audio**: USB audio interface required (no onboard audio codec)
- **Network**: 100Mbps Ethernet
- **Storage**: microSD card (16GB+ recommended)

## Architecture Changes from Desktop

### Removed Components
- ❌ JUCE Framework (GUI, audio abstraction)
- ❌ Windows-specific code (VB-Cable, WASAPI)
- ❌ CUDA/GPU code paths
- ❌ MainComponent GUI
- ❌ Heavy dependencies

### New Components
- ✅ **ALSA** for direct audio I/O
- ✅ **cpp-httplib** for REST API control (single-header, lightweight)
- ✅ **Headless daemon** with systemd integration
- ✅ **Configuration file** support (YAML/JSON)
- ✅ **Logging** to syslog/journalctl
- ✅ **Memory-optimized** for 1GB RAM constraint

## System Requirements

### Hardware
- Orange Pi Zero 3 with 4GB RAM (tested configuration)
- USB audio interface (input + output)
- 16GB+ microSD card (Class 10 or better)
- Ethernet connection (WiFi adds latency)
- Network access for initial setup

## Memory Budget

| Component | Memory Usage |
|-----------|--------------|
| Linux OS (Debian minimal) | ~100-150 MB |
| Explicitly daemon | ~30 MB |
| Whisper tiny model | ~127 MB |
| Audio buffers (20s @ 48kHz) | ~8 MB |
| Processing overhead | ~20 MB |
| **Total** | **~280-330 MB** |
| **Free (on 4GB device)** | **~3.7-3.9 GB** |

✅ Full feature parity with desktop - no simplifications needed with 4GB RAM

## Performance Expectations

### Orange Pi Zero 3 (ARM Cortex-A53 @ 1.5GHz)
- **Whisper Tiny Model RTF**: ~0.3-0.5x (estimated)
  - Desktop (x86-64): 0.15x
  - ARM64 is ~2-3x slower than x86 for Whisper
  - Still fast enough for real-time (< 1.0x)
- **CPU Usage**: 50-80% during transcription (acceptable)
- **Latency**: 10-15 seconds (includes safety buffer)
- **Accuracy**: Same as desktop (~90-92% on clear vocals)

## Control Interfaces

### 1. HTTP REST API (Default)
```bash
# Start processing
curl -X POST http://orangepi.local:8080/api/start

# Stop processing
curl -X POST http://orangepi.local:8080/api/stop

# Get status
curl http://orangepi.local:8080/api/status

# Change censor mode
curl -X POST http://orangepi.local:8080/api/config -d '{"mode":"mute"}'
```

### 2. Configuration File
Edit `/etc/explicitly/config.yaml`:
```yaml
audio:
  input_device: "hw:1,0"
  output_device: "hw:1,0"
  sample_rate: 48000
  buffer_size: 512

processing:
  model_path: "/usr/share/explicitly/models/ggml-tiny.en.bin"
  censor_mode: "reverse"  # or "mute"
  
api:
  enabled: true
  port: 8080
  bind_address: "0.0.0.0"
```

Then restart service:
```bash
sudo systemctl restart explicitly
```

### 3. Systemd Service Commands
```bash
# Start service
sudo systemctl start explicitly

# Stop service
sudo systemctl stop explicitly

# Enable auto-start on boot
sudo systemctl enable explicitly

# Check status
sudo systemctl status explicitly

# View logs
sudo journalctl -u explicitly -f
```

## Audio Routing Options

### Option 1: USB Audio Pass-Through (Simplest)
```
Audio Source → USB Audio Input → Orange Pi → USB Audio Output → Speakers
```
- Single USB audio interface with input/output
- Direct hardware routing
- Lowest latency

### Option 2: ALSA Loopback (Advanced)
```
Audio App → ALSA Loopback → Orange Pi → ALSA Output → Speakers
```
- Requires `snd-aloop` kernel module
- Allows capturing from software sources
- Similar to VB-Cable on Windows

### Option 3: JACK Audio (Professional)
```
Audio Source → JACK Input → Orange Pi → JACK Output → Speakers
```
- Most flexible routing
- Higher CPU overhead
- Best for complex setups

**Recommended for Orange Pi Zero 3**: Option 1 (USB Audio Pass-Through)

## Directory Structure

```
hardware/
├── README.md                          # This file
├── BUILD.md                           # Build instructions
├── INSTALL.md                         # Installation guide for Orange Pi
├── ARCHITECTURE.md                    # Technical architecture doc
├── CMakeLists.txt                     # ARM64 build configuration
├── config.yaml.example                # Example configuration
├── explicitly.service                 # Systemd unit file
│
├── src/
│   ├── main.cpp                       # Headless daemon entry point
│   ├── AlsaAudioEngine.cpp/h          # ALSA audio I/O
│   ├── AudioProcessor.cpp/h           # Core processing (from desktop)
│   ├── WhisperProcessor.cpp/h         # Whisper integration
│   ├── ProfanityFilter.h              # Profanity detection (reused)
│   ├── TimestampRefiner.cpp/h         # Timestamp refinement (reused)
│   ├── VocalFilter.cpp/h              # Vocal bandpass filter (reused)
│   ├── HttpApiServer.cpp/h            # REST API server
│   ├── Config.cpp/h                   # Configuration loader
│   └── Utils.cpp/h                    # Logging, memory monitoring
│
├── scripts/
│   ├── setup_orangepi.sh              # Initial Orange Pi setup
│   ├── install_dependencies.sh        # Install ALSA, Whisper, etc.
│   └── deploy.sh                      # Deploy to Orange Pi via SSH
│
├── models/
│   └── download_model.sh              # Script to download ggml-tiny.en.bin
│
└── tests/
    ├── test_alsa.cpp                  # Test ALSA audio I/O
    └── test_whisper.cpp               # Test Whisper on ARM64
```

## Key Design Decisions

### 1. Remove JUCE Framework
**Why**: JUCE is designed for desktop GUI apps and adds 10-20MB overhead.
**Solution**: Direct ALSA API for audio I/O (more efficient).

### 2. Headless Operation
**Why**: Orange Pi has no display, X11 would waste resources.
**Solution**: Daemon process with HTTP API and systemd integration.

### 3. CPU-Only Whisper
**Why**: No GPU on Orange Pi Zero 3, no OpenCL support.
**Solution**: Optimized CPU build of whisper.cpp with ARM NEON intrinsics.

### 4. Reduced Buffer Sizes
**Why**: Limited RAM (1GB).
**Solution**: 
- Reduce delay buffer from 20s → 15s (saves ~3.5MB)
- Keep safety margin for ARM's slower RTF (0.5x vs 0.15x)

### 5. Single-Threaded API Server
**Why**: Minimize context switching overhead.
**Solution**: Lightweight HTTP server in same process (cpp-httplib).

### 6. No GUI Fallback
**Why**: Headless only - no X11/Wayland dependencies.
**Solution**: All control via HTTP API, config files, or systemd.

## Build Approaches

### Approach 1: Cross-Compile on Desktop (Faster)
Compile on your Windows/Linux x86-64 machine using ARM64 toolchain, then copy binary to Orange Pi.

**Pros**: Much faster compilation
**Cons**: Requires cross-compile toolchain setup

### Approach 2: Native Compile on Orange Pi (Simpler)
Compile directly on the Orange Pi using native GCC.

**Pros**: No cross-compile complexity
**Cons**: Very slow (1-2 hours for Whisper.cpp)

**Recommended**: Cross-compile on desktop for development, native compile for final deployment.

## Tradeoffs vs Desktop Version

| Aspect | Desktop (x86-64) | Hardware (ARM64) |
|--------|------------------|------------------|
| **GUI** | ✅ Full JUCE GUI | ❌ Headless only |
| **Control** | Mouse/keyboard | HTTP API, config files |
| **Audio I/O** | JUCE abstraction | Direct ALSA |
| **Platform** | Windows-only | Linux-only |
| **Memory** | 200 MB | 280-330 MB |
| **RTF** | 0.15x | 0.3-0.5x |
| **CPU** | 10-15% | 50-80% |
| **Setup** | Easy (exe + model) | Requires Linux knowledge |
| **Updates** | GUI settings | Edit config, restart |
| **Monitoring** | Visual indicators | HTTP status, logs |
| **Power** | Desktop PC | 5W (USB powered) |

## Next Steps

1. Read `BUILD.md` for compilation instructions
2. Read `INSTALL.md` for Orange Pi setup and deployment
3. Read `ARCHITECTURE.md` for technical details

## Quick Start (TL;DR)

```bash
# On Orange Pi Zero 3 (Debian/Ubuntu)
git clone https://github.com/your-repo/explicitly
cd explicitly/hardware

# Install dependencies
./scripts/install_dependencies.sh

# Build (native)
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j4

# Install
sudo make install

# Configure
sudo cp config.yaml.example /etc/explicitly/config.yaml
sudo nano /etc/explicitly/config.yaml

# Start service
sudo systemctl enable explicitly
sudo systemctl start explicitly

# Check status
curl http://localhost:8080/api/status
```

## Support

For issues specific to Orange Pi Zero 3 deployment, check:
- Orange Pi forums: http://www.orangepi.org/
- ALSA documentation: https://www.alsa-project.org/
- Whisper.cpp ARM builds: https://github.com/ggerganov/whisper.cpp

## License

Same as desktop version - see main repository LICENSE file.
