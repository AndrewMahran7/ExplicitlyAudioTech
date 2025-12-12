# Explicitly Hardware - Technical Architecture

## Overview

This document describes the technical architecture of the Orange Pi Zero 3 port of the Explicitly real-time profanity filter.

## Design Principles

1. **Headless Operation**: No GUI, no X11/Wayland dependencies
2. **Minimal Footprint**: Optimized for 1GB RAM constraint
3. **Real-Time Audio**: Low-latency ALSA integration
4. **Continuous Operation**: Systemd integration, auto-restart on failure
5. **Remote Control**: HTTP REST API for management
6. **ARM Optimization**: Compiled for ARM64 with NEON intrinsics

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Orange Pi Zero 3 Hardware                                     │
│  - ARM Cortex-A53 @ 1.5GHz (4 cores)                           │
│  - 1-2GB RAM                                                    │
│  - USB Audio Interface                                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Linux Kernel (Debian/Ubuntu ARM64)                            │
│  - ALSA audio subsystem                                        │
│  - Real-time scheduling (SCHED_FIFO)                            │
│  - Systemd service manager                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Explicitly Daemon Process                                     │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Main Thread                                               │ │
│  │ - HTTP API server (cpp-httplib)                           │ │
│  │ - Configuration management                                │ │
│  │ - Status monitoring                                       │ │
│  │ - Logging to journalctl                                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              ↓                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Audio Thread (Real-Time Priority)                         │ │
│  │ - ALSA PCM capture                                        │ │
│  │ - Write to delay buffer                                   │ │
│  │ - Read from delay buffer (10s behind)                     │ │
│  │ - Apply censorship                                        │ │
│  │ - ALSA PCM playback                                       │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              ↕                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Whisper Thread                                            │ │
│  │ - Accumulate 5s audio chunks                              │ │
│  │ - Resample 48kHz → 16kHz                                  │ │
│  │ - Run Whisper inference (CPU only)                        │ │
│  │ - Extract word timestamps                                 │ │
│  │ - Refine timestamps (energy analysis)                     │ │
│  │ - Detect profanity                                        │ │
│  │ - Create censor regions                                   │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Network API                                                   │
│  HTTP REST endpoints on port 8080                              │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. AlsaAudioEngine

**File**: `src/AlsaAudioEngine.cpp`

**Responsibilities**:
- Initialize ALSA PCM devices (capture + playback)
- Launch real-time audio thread
- Manage audio I/O with ALSA API
- Monitor CPU usage and memory
- Provide statistics to HTTP API

**Key Methods**:
- `initialize()` - Open ALSA devices, configure parameters
- `start()` - Launch audio thread with real-time priority
- `stop()` - Gracefully shut down audio processing
- `audioThreadFunc()` - Real-time audio callback
- `processAudio()` - Delegate to AudioProcessor

**ALSA Configuration**:
```cpp
Sample Format:  SND_PCM_FORMAT_FLOAT (32-bit float)
Access Type:    SND_PCM_ACCESS_RW_INTERLEAVED
Sample Rate:    48000 Hz
Channels:       2 (stereo)
Period Size:    512 frames (10.67ms @ 48kHz)
Buffer Size:    2048 frames (42.67ms @ 48kHz)
```

**Thread Priority**:
- Uses `SCHED_FIFO` scheduling policy
- Priority: 80 (high, but below kernel threads)
- Requires `CAP_SYS_NICE` capability or root
- Falls back gracefully if permission denied

### 2. AudioProcessor

**File**: `src/AudioProcessor.cpp`

**Responsibilities**:
- Delay buffering (10 second delay)
- Whisper processing in background thread
- Profanity detection
- Censorship application

**Key Components**:
- **Delay Buffer**: Circular buffer, 20 seconds capacity
  - Write head: Stores incoming audio
  - Read head: 10 seconds behind write head
  - Allows Whisper processing time
  
- **Accumulation Buffer**: 5 second chunks
  - Feeds Whisper every 5 seconds
  - Resampled to 16kHz for Whisper
  
- **Whisper Thread**:
  - Waits for new 5s chunk
  - Runs inference (0.3-0.5x RTF on ARM)
  - Extracts word-level timestamps
  - Sends to timestamp refiner
  
- **Censorship Regions**:
  - Stored as `[startSample, endSample, word]`
  - Protected by mutex (thread-safe)
  - Applied during playback (reverse or mute)

**Processing Pipeline**:
```
Input Audio (48kHz)
    ↓
Vocal Filter (150-5000 Hz) [optional]
    ↓
Delay Buffer Write
    ↓ (copy to accumulation)
Accumulation Buffer (5s chunks)
    ↓ (every 5s)
Resample to 16kHz
    ↓
Whisper Inference
    ↓
Word Timestamps
    ↓
Timestamp Refiner [optional]
    ↓
Profanity Detection
    ↓
Censor Regions (stored)
    ↓
Delay Buffer Read (10s behind)
    ↓
Apply Censorship (reverse/mute)
    ↓
Output Audio (48kHz)
```

### 3. HttpApiServer

**File**: `src/HttpApiServer.cpp`

**Responsibilities**:
- RESTful HTTP API
- Status reporting
- Runtime configuration
- Health checks

**Dependencies**:
- cpp-httplib (single-header HTTP server library)
- JSON serialization (manual, lightweight)

**API Endpoints**:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Current engine status |
| GET | `/api/health` | Health check (for monitoring) |
| POST | `/api/start` | Start audio processing |
| POST | `/api/stop` | Stop audio processing |
| POST | `/api/config` | Update configuration |

**Example Responses**:

```json
GET /api/status
{
  "running": true,
  "latency_ms": 10000.0,
  "buffer_fill": 0.85,
  "cpu_usage": 0.62,
  "memory_mb": 287.5,
  "profanity_count": 42,
  "uptime_seconds": 3600
}

GET /api/health
{
  "status": "ok",
  "version": "1.0.0"
}
```

### 4. Shared Components (from Desktop)

These components are reused from the desktop version with minimal changes:

#### ProfanityFilter
- Header-only lexicon-based filter
- Case-insensitive matching
- Multi-word pattern support
- **Change**: Replace `juce::File` with `std::ifstream`

#### VocalFilter
- IIR Butterworth bandpass filter
- Frequency range: 150-5000 Hz
- **Change**: Remove JUCE dependency, use plain C++ arrays

#### TimestampRefiner
- Energy-based timestamp refinement
- Zero-crossing rate analysis
- **Change**: None (already JUCE-independent)

#### LyricsAlignment
- Word segmentation structures
- Timestamp alignment helpers
- **Change**: None (data structures only)

## Memory Budget

### Static Allocations

| Component | Size | Notes |
|-----------|------|-------|
| Executable | 3-4 MB | Includes all code + Whisper statically linked |
| Whisper Model | 75 MB | ggml-tiny.en.bin loaded into RAM |
| Profanity Lexicon | <1 MB | Text file, ~400 words |
| Code/Stack | 5-10 MB | C++ runtime, libraries |

### Dynamic Allocations

| Component | Size | Notes |
|-----------|------|-------|
| Delay Buffer | 7.3 MB | 20s @ 48kHz stereo float32 |
| Accumulation Buffer | 1.8 MB | 5s @ 48kHz stereo float32 |
| Whisper KV Cache | 20 MB | Encoder/decoder caches |
| Whisper Compute | 30 MB | Temporary inference buffers |
| ALSA Buffers | 0.1 MB | Kernel-managed |

### Total Memory Usage

| Scenario | RAM Usage |
|----------|-----------|
| Idle (no processing) | ~80-100 MB |
| Active processing | ~280-330 MB |
| Peak (during inference) | ~350-380 MB |

**Conclusion**: Fits comfortably in 1GB Orange Pi with ~650MB free for OS.

## CPU Usage Profile

### Whisper Inference Burst

- **Duration**: 1.5-2.5 seconds per 5s chunk
- **CPU**: 80-100% (all cores)
- **RTF**: 0.3-0.5x (fast enough for real-time)

### Audio I/O (Continuous)

- **CPU**: 5-10%
- **Real-time thread**: Runs every 10ms
- **Processing time**: <1ms per callback

### Idle (No Audio)

- **CPU**: 2-5%
- **HTTP server**: Event-driven, no polling

### Average Sustained Load

- **CPU**: 50-70% (burst average)
- **Acceptable**: Orange Pi stays cool, no throttling

## Thread Model

### Thread 1: Main Thread (Normal Priority)

- **Role**: Event loop, HTTP server
- **Scheduling**: CFS (Completely Fair Scheduler)
- **CPU Affinity**: Any core
- **Blocks on**: HTTP requests, signal handling

### Thread 2: Audio Thread (Real-Time Priority)

- **Role**: ALSA I/O, delay buffering, censorship
- **Scheduling**: SCHED_FIFO, priority 80
- **CPU Affinity**: Pinned to Core 0 (optional optimization)
- **Blocks on**: ALSA `snd_pcm_readi()`/`writei()`
- **Latency**: <1ms processing time per callback

### Thread 3: Whisper Thread (Normal Priority)

- **Role**: Transcription, profanity detection
- **Scheduling**: CFS
- **CPU Affinity**: Cores 1-3 (optional, avoid Core 0)
- **Blocks on**: Condition variable (waiting for new audio chunk)
- **Duration**: 1.5-2.5s every 5 seconds

## Synchronization

### Lock-Free Structures

- **Atomic flags**: `running`, `shouldStop`, `hasNewBuffer`
- **Atomic counters**: `profanityCount`, `delayWritePos`, `delayReadPos`
- **Benefits**: No mutex contention in audio thread

### Mutex-Protected Structures

- **Censor regions**: Modified by Whisper thread, read by audio thread
  - Protected by `censorMutex`
  - Audio thread acquires briefly (<1ms)
  
- **Configuration**: Modified by HTTP API, read by audio/whisper threads
  - Protected by configuration mutex
  - Infrequent access

### Condition Variables

- **Whisper signaling**: `whisperCv` notifies Whisper thread of new audio
  - Wait in Whisper thread (no busy-wait)
  - Signal from audio thread (after accumulation complete)

## Failure Modes and Recovery

### Audio Device Failure

- **Detection**: `snd_pcm_readi()/writei()` returns `-EPIPE` (buffer overrun/underrun)
- **Recovery**: Call `snd_pcm_prepare()` to reset device
- **Fallback**: If persistent, log error and attempt restart

### Whisper Failure

- **Detection**: `whisper_full()` returns non-zero
- **Recovery**: Skip chunk, log error, continue with next chunk
- **Fallback**: Audio passes through uncensored

### Out of Memory

- **Prevention**: Systemd `MemoryMax=400M` limit
- **Detection**: `std::bad_alloc` exception
- **Recovery**: Systemd restarts service

### Network API Crash

- **Isolation**: HTTP server runs in separate thread
- **Recovery**: Main process continues, API becomes unavailable
- **Monitoring**: Health check endpoint for external monitoring

## Performance Optimizations

### ARM-Specific

1. **NEON Intrinsics**: Whisper.cpp uses ARM NEON for vectorization
2. **Compiler Flags**: `-march=armv8-a -mtune=cortex-a53`
3. **Cache Optimization**: Align buffers to 64-byte cache lines

### Memory

1. **Static Linking**: Whisper.cpp statically linked (no .so overhead)
2. **Buffer Reuse**: Accumulation buffer reused, no reallocation
3. **Lazy Allocation**: Delay buffer allocated only on `start()`

### CPU

1. **Thread Affinity**: Pin audio thread to Core 0 (cache locality)
2. **CPU Governor**: Set to `performance` mode for consistent latency
3. **Batch Processing**: Process 512 samples at a time (10ms)

## Configuration Tuning

### Low Latency (2GB Orange Pi)

```yaml
audio:
  buffer_size: 512   # 10ms
  periods: 4

processing:
  enable_vocal_filter: true
  enable_timestamp_refiner: true
```

### Low Memory (1GB Orange Pi)

```yaml
audio:
  buffer_size: 1024  # 20ms
  periods: 2

processing:
  enable_vocal_filter: false
  enable_timestamp_refiner: false
```

### Balanced (Recommended)

```yaml
audio:
  buffer_size: 512   # 10ms
  periods: 4

processing:
  enable_vocal_filter: true
  enable_timestamp_refiner: false  # CPU savings
```

## Comparison: Desktop vs Hardware

| Aspect | Desktop (x86-64) | Hardware (ARM64) |
|--------|------------------|------------------|
| **Framework** | JUCE (GUI + Audio) | ALSA (Direct) |
| **Platform** | Windows only | Linux only |
| **Control** | GUI buttons | HTTP API |
| **Model** | Tiny (75MB) | Tiny (75MB) |
| **RTF** | 0.15x | 0.3-0.5x |
| **CPU** | 10-15% | 50-70% |
| **Memory** | 200 MB | 280-330 MB |
| **Latency** | 10 seconds | 10-15 seconds |
| **Power** | ~50-100W | ~3-5W |
| **Size** | Desktop PC | Credit card |
| **Deployment** | Single exe | Systemd service |
| **Cost** | $500+ PC | $30 Orange Pi |

## Security Considerations

### User Isolation

- Runs as dedicated `explicitly` user (not root)
- Group: `audio` (for ALSA access)
- No shell access (`/bin/false`)

### Systemd Hardening

```ini
NoNewPrivileges=true        # Can't gain privileges
PrivateTmp=true             # Isolated /tmp
ProtectSystem=strict        # Read-only filesystem
ProtectHome=true            # No /home access
CapabilityBoundingSet=CAP_SYS_NICE  # Only real-time scheduling
```

### Network Exposure

- API binds to `0.0.0.0:8080` by default
- **Risk**: No authentication (local network only)
- **Mitigation**: Bind to `127.0.0.1` for localhost only, or add firewall rules

### Recommended Firewall

```bash
sudo ufw deny 8080/tcp  # Block external access
# Or allow specific IPs
sudo ufw allow from 192.168.1.0/24 to any port 8080
```

## Future Enhancements

### Potential Improvements

1. **JTAG Debugging**: Remote debugging over network
2. **Model Quantization**: INT8 quantization (75MB → 38MB)
3. **GPU Acceleration**: Mali GPU for Whisper (if driver support improves)
4. **Embedded Display**: Add I2C OLED for status (no X11 required)
5. **Web UI**: Serve static HTML dashboard from HTTP API
6. **Authentication**: API key or JWT tokens for HTTP API
7. **Multi-Channel**: Support 5.1/7.1 surround sound
8. **Streaming**: Output to network (Icecast/RTP)

### Not Recommended

- ❌ **Qt/GTK GUI**: Defeats purpose of headless design
- ❌ **Python Wrapper**: Adds overhead, complexity
- ❌ **Docker**: Unnecessary for embedded device
- ❌ **Database**: Overkill for statistics storage

## Testing Strategy

### Unit Tests

- AudioProcessor buffer management
- Profanity filter matching
- Timestamp refiner accuracy

### Integration Tests

- ALSA device open/close
- Whisper model loading
- HTTP API endpoints

### Performance Tests

- RTF measurement across different models
- Memory leak detection (valgrind)
- CPU profiling (perf)

### Stress Tests

- 24-hour continuous operation
- Rapid start/stop cycles
- Network congestion (API load)

## Deployment Checklist

- [ ] Flash OS to microSD
- [ ] Configure audio devices
- [ ] Build or copy binary
- [ ] Download Whisper model
- [ ] Copy profanity lexicon
- [ ] Edit config.yaml
- [ ] Install systemd service
- [ ] Test ALSA audio I/O
- [ ] Test HTTP API
- [ ] Enable real-time priority
- [ ] Monitor logs for errors
- [ ] Set up firewall rules
- [ ] Configure auto-start on boot

## Conclusion

The Orange Pi Zero 3 port successfully removes all desktop dependencies while maintaining the core profanity filtering functionality. The headless architecture is optimized for embedded deployment with minimal RAM and CPU overhead, making it suitable for continuous operation in resource-constrained environments.

Key achievements:
- ✅ 1GB RAM compatible
- ✅ Headless operation (no GUI)
- ✅ Real-time audio processing
- ✅ HTTP REST API control
- ✅ Systemd integration
- ✅ Production-ready reliability
