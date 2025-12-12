# Desktop vs Hardware - Quick Reference

## Side-by-Side Comparison

| Aspect | Desktop (Windows) | Hardware (Orange Pi) |
|--------|-------------------|----------------------|
| **Platform** | Windows x64 | Linux ARM64 |
| **CPU** | Intel/AMD x86-64 | ARM Cortex-A53 |
| **RAM** | 8GB+ | 1-2GB |
| **Audio Framework** | JUCE (WASAPI) | ALSA (direct) |
| **Audio Routing** | VB-Cable (virtual) | USB Audio |
| **Control Interface** | GUI (JUCE) | HTTP REST API |
| **Configuration** | GUI settings | YAML file |
| **Deployment** | .exe + DLLs | Systemd service |
| **Display** | Required | Headless |
| **Power** | 50-100W | 3-5W |
| **Cost** | $500+ PC | $30 device |
| **Size** | Desktop tower | Credit card |

## Architecture Mapping

### Desktop → Hardware

| Desktop Component | Hardware Equivalent |
|-------------------|---------------------|
| `Main.cpp` (JUCE app) | `main.cpp` (daemon) |
| `MainComponent` (GUI) | `HttpApiServer` (API) |
| `AudioEngine` | `AlsaAudioEngine` + `AudioProcessor` |
| JUCE `AudioIODeviceCallback` | ALSA `snd_pcm_readi()/writei()` |
| JUCE `AudioDeviceManager` | Direct ALSA device management |
| JUCE `Thread` | `std::thread` |
| JUCE `AudioBuffer` | `std::vector<float>` |
| JUCE `File` | `std::ifstream/ofstream` |
| JUCE `String` | `std::string` |
| Device selection ComboBox | config.yaml `audio: input_device` |
| Start/Stop button | `POST /api/start`, `POST /api/stop` |
| Status labels | `GET /api/status` JSON response |
| Debug log TextEditor | journalctl logs |

## Code Changes Summary

### Completely New Files

```
hardware/src/AlsaAudioEngine.h      - ALSA audio I/O (replaces JUCE)
hardware/src/AlsaAudioEngine.cpp
hardware/src/HttpApiServer.h        - REST API (replaces GUI)
hardware/src/main.cpp               - Daemon entry (replaces JUCE app)
hardware/CMakeLists.txt             - ARM64 build (replaces Windows)
hardware/explicitly.service         - Systemd (replaces manual launch)
hardware/config.yaml.example        - Config file (replaces GUI)
```

### Adapted Files (Need JUCE Removal)

```
desktop/Source/AudioEngine.cpp      → hardware/src/AudioProcessor.cpp
  - Remove JUCE AudioBuffer → use std::vector<float>
  - Remove JUCE Thread → use std::thread
  - Remove JUCE String → use std::string
  - Remove JUCE File → use std::ifstream

desktop/Source/ProfanityFilter.h    → hardware/src/ProfanityFilter.h
  - Remove juce::File → use std::ifstream
  - Already mostly header-only
```

### Reused As-Is

```
desktop/Source/VocalFilter.cpp      → hardware/src/VocalFilter.cpp
desktop/Source/TimestampRefiner.cpp → hardware/src/TimestampRefiner.cpp
desktop/Source/LyricsAlignment.cpp  → hardware/src/LyricsAlignment.cpp
desktop/Source/Types.h              → hardware/src/Types.h
desktop/Models/profanity_en.txt     → /usr/share/explicitly/profanity_en.txt
```

## API Mapping

### Desktop GUI → Hardware API

| Desktop Action | Hardware Equivalent |
|----------------|---------------------|
| Click "Start Processing" | `curl -X POST http://orangepi:8080/api/start` |
| Click "Stop Processing" | `curl -X POST http://orangepi:8080/api/stop` |
| Select input device | Edit config.yaml: `audio: input_device: "hw:1,0"` |
| Select output device | Edit config.yaml: `audio: output_device: "hw:1,0"` |
| Change censor mode | `curl -X POST http://orangepi:8080/api/config -d '{"mode":"mute"}'` |
| View status | `curl http://orangepi:8080/api/status` |
| Check latency | Status JSON: `"latency_ms": 10000.0` |
| View debug log | `sudo journalctl -u explicitly -f` |
| Export log | `sudo journalctl -u explicitly > log.txt` |

## Configuration Mapping

### Desktop (GUI) → Hardware (config.yaml)

```yaml
# Desktop: Input Device ComboBox
audio:
  input_device: "hw:1,0"

# Desktop: Output Device ComboBox
audio:
  output_device: "hw:1,0"

# Desktop: Censor Mode ComboBox
processing:
  censor_mode: "reverse"  # or "mute"

# Desktop: Model path (hardcoded)
processing:
  model_path: "/usr/share/explicitly/models/ggml-tiny.en.bin"

# Desktop: Lexicon path (hardcoded)
processing:
  profanity_lexicon: "/usr/share/explicitly/profanity_en.txt"

# Desktop: Sample rate (auto-detected)
audio:
  sample_rate: 48000

# Desktop: Buffer size (auto)
audio:
  buffer_size: 512
```

## Build Process Mapping

### Desktop (Windows)

```powershell
# Desktop build
cd desktop/build
cmake --build . --config Release

# Output: ExplicitlyDesktop.exe + DLLs
# Size: ~50 MB total
# Run: double-click ExplicitlyDesktop.exe
```

### Hardware (Linux)

```bash
# Hardware build
cd hardware
./scripts/build_whisper.sh    # 30-45 min on Orange Pi
./scripts/build_explicitly.sh  # 5-10 min

# Output: explicitly-daemon (single binary)
# Size: ~3-4 MB (+ 75 MB model separate)
# Run: sudo systemctl start explicitly
```

## Dependency Mapping

### Desktop Dependencies

```
✓ JUCE 7.x              (~20 MB)
✓ whisper.dll           (~15 MB)
✓ ggml*.dll             (~20 MB)
✓ Windows SDK           (build-time)
✓ MSVC 2022             (build-time)
```

### Hardware Dependencies

```
✓ libasound2            (ALSA, ~1 MB)
✓ libpthread            (standard)
✓ libstdc++             (standard)
✓ whisper.cpp           (statically linked, ~2 MB)
✓ cpp-httplib           (header-only, no runtime dep)
```

## Runtime Monitoring

### Desktop

- **Visual**: GUI shows status, latency, profanity count
- **Debug**: TextEditor shows transcript and events
- **Export**: Button to save debug log
- **Performance**: Visual indicators for buffer fill

### Hardware

- **HTTP API**: `curl http://orangepi:8080/api/status`
- **Logs**: `sudo journalctl -u explicitly -f`
- **Status**: `sudo systemctl status explicitly`
- **Performance**: Parse JSON response
  ```json
  {
    "running": true,
    "latency_ms": 10000.0,
    "cpu_usage": 0.65,
    "memory_mb": 287.5,
    "profanity_count": 42
  }
  ```

## Error Handling

### Desktop

- **Error**: Dialog box shown to user
- **Crash**: Windows error reporting
- **Recovery**: User must restart application

### Hardware

- **Error**: Logged to journalctl
- **Crash**: Systemd auto-restarts service
- **Recovery**: Automatic (RestartSec=10)
- **Monitoring**: `systemctl status` shows exit code

## Use Case Comparison

### Desktop - Best For

✅ Development and testing
✅ Interactive use with immediate feedback
✅ Experimenting with settings
✅ Viewing real-time transcripts
✅ Debugging profanity detection
✅ Single-user, single-machine

### Hardware - Best For

✅ Production deployment
✅ Embedded applications
✅ 24/7 operation
✅ Low power consumption
✅ Headless environments
✅ Remote management
✅ Appliance integration
✅ Cost-sensitive projects

## Migration Path

### Desktop User → Hardware Deployment

1. **Develop on Desktop**
   - Use GUI for rapid iteration
   - Test profanity detection with visual feedback
   - Tune settings interactively

2. **Document Settings**
   - Note input/output device names
   - Record censor mode preference
   - Save any custom profanity words

3. **Prepare Hardware**
   - Flash Orange Pi with Debian/Ubuntu
   - Run setup scripts
   - Build or deploy binary

4. **Migrate Configuration**
   - Convert GUI settings to config.yaml
   - Transfer profanity lexicon
   - Download appropriate Whisper model

5. **Deploy and Monitor**
   - Start systemd service
   - Verify with HTTP API
   - Monitor logs for issues

6. **Maintain**
   - Update config.yaml for changes
   - Restart service: `systemctl restart explicitly`
   - Check logs periodically

## Performance Trade-offs

### Desktop Advantages

- ✅ Faster RTF: 0.15x vs 0.3-0.5x
- ✅ Lower CPU %: 10-15% vs 50-70%
- ✅ Instant feedback via GUI
- ✅ Easier debugging with visual tools

### Hardware Advantages

- ✅ Much lower power: 5W vs 100W
- ✅ Much smaller: credit card vs tower
- ✅ Much cheaper: $30 vs $500+
- ✅ Silent operation (no fans)
- ✅ Suitable for always-on use
- ✅ Can be battery powered

## When to Use Which

### Use Desktop If

- You need interactive development
- You want visual feedback
- You have power available
- You have space for a PC
- You need fastest performance
- You're testing/prototyping

### Use Hardware If

- You need 24/7 operation
- Power efficiency matters
- Space is limited
- Cost is a concern
- You need embedded deployment
- Remote management is acceptable
- You can accept slightly slower RTF

## Summary

Both versions use the **same core algorithm** (Whisper + profanity detection + censorship). The key difference is:

- **Desktop**: Interactive GUI for development/testing
- **Hardware**: Headless daemon for production deployment

Choose based on your use case: development vs deployment.
