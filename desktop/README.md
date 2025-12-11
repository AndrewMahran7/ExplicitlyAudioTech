# Explicitly Desktop - Ultra-Low Latency Real-Time Profanity Filter

## Architecture Overview

This application performs **real-time streaming profanity filtering** with under 200ms total latency using lightweight streaming ASR (no vocal separation, no heavy ML models).

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│  Audio Input (Microphone or Line-In)                           │
│  ↓ Real-time PCM audio stream                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Explicitly Real-Time Processing (JUCE Application)            │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ Audio Thread (Real-Time Critical)                      │   │
│  │ - Captures audio: 10-20ms chunks (512-1024 samples)   │   │
│  │ - Stores in 150-300ms circular buffer                 │   │
│  │ - Sends audio to ASR thread via lock-free queue       │   │
│  │ - Applies censorship in-place (reverse/mute)          │   │
│  │ - Outputs filtered audio with <150ms latency          │   │
│  └────────────────────────────────────────────────────────┘   │
│                          ↕ (Lock-Free Queue)                   │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ ASR Thread (Streaming Recognition)                     │   │
│  │ - Receives 20-50ms audio chunks                        │   │
│  │ - Runs Vosk streaming ASR (20-80ms latency)           │   │
│  │ - Gets partial transcripts with timestamps             │   │
│  │ - Detects profanity from tokens (<1ms)                │   │
│  │ - Sends timestamps back to audio thread                │   │
│  └────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Audio Output (Speakers/Headphones)                            │
│  - User hears filtered audio with <150ms delay                │
└─────────────────────────────────────────────────────────────────┘
```

### Latency Budget (Target: <150ms)

```
Audio Capture:        10ms   (512 samples @ 48kHz)
   ↓
Lock-Free Queue:      <1ms   (zero-copy hand-off)
   ↓
Vosk ASR Inference:   50ms   (streaming partial results)
   ↓
Profanity Detection:  <1ms   (string matching)
   ↓
Lock-Free Queue:      <1ms   (timestamp result)
   ↓
Censorship DSP:       <1ms   (reverse/mute samples)
   ↓
Audio Output:         10ms   (512 samples @ 48kHz)
─────────────────────────────
TOTAL:               ~72ms   ✅ Well under 150ms target
```

### Key Design Decisions

1. **Streaming ASR (No Vocal Separation)**
   - Vosk or Picovoice Cheetah for <80ms inference latency
   - NO Demucs (eliminates 6-8 second overhead)
   - Trade music background noise for real-time performance

2. **Minimal Buffer (150-300ms)**
   - Just enough for streaming ASR processing
   - Reduces perceived latency vs 10-second buffer
   - 7,200-14,400 samples @ 48kHz (manageable for embedded)

3. **Lock-Free Threading**
   - Audio thread: real-time critical, never blocks
   - ASR thread: streaming processing, partial results
   - Atomic lock-free queue for timestamp handoff

4. **Lexicon-Based Detection**
   - Simple string matching (<1ms overhead)
   - No ML model inference for profanity (just transcription)
   - Multi-token profanity support

5. **Purpose: Latency Testing**
   - Desktop app is test harness for embedded feasibility
   - Goal: prove <200ms real-time filtering is achievable
   - Future target: ARM embedded hardware port

6. **Graceful Degradation**
   - If ML can't keep up, audio passes through uncensored
   - No dropouts or glitches under any condition
   - Visual indicators show processing status

## Technology Stack

### Audio Framework
- **JUCE 7.x**: Cross-platform C++ audio framework
- **Windows Audio**: WASAPI for low-latency I/O
- **Sample Rate**: 48 kHz (standard for real-time audio)
- **Buffer Size**: 512-1024 samples (10-20ms chunks)

### ASR Engine (Choose One)

**Option A: Vosk (Recommended - Offline, Free)**
- Lightweight streaming ASR (~100MB models)
- C++ API with streaming interface
- 20-80ms inference latency
- Offline processing (no cloud dependency)
- Free and open-source
- Good accuracy for profanity detection use case

**Option B: Picovoice Cheetah (Ultra-Low Latency)**
- Commercial license required
- <50ms inference latency
- Streaming partial results
- Embedded-optimized models
- Higher accuracy than Vosk
- Easiest path to sub-150ms total latency

### Profanity Detection
- Simple lexicon-based string matching
- No ML model (just list of banned words/phrases)
- Multi-token support (e.g., "what the hell")
- <1ms processing time

### Virtual Audio Device
- **VB-Cable** (development/testing)
- Optional custom driver for production branding

## Project Structure

```
desktop/
├── README.md                       # This file
├── BUILDING.md                     # Build instructions
├── CMakeLists.txt                  # CMake build configuration
├── ExplicitlyDesktop.jucer         # JUCE project file
│
├── Source/                         # C++ source code
│   ├── Main.cpp                    # Application entry point
│   ├── MainComponent.h/cpp         # GUI controls and status
│   ├── AudioEngine.h/cpp           # Lock-free audio processing
│   ├── CircularBuffer.h            # 150-300ms ring buffer
│   ├── ASRThread.h/cpp             # Streaming ASR processing (Vosk)
│   ├── LockFreeQueue.h             # Thread-safe timestamp queue
│   ├── ProfanityFilter.h/cpp       # Lexicon-based detection
│   ├── CensorshipEngine.h/cpp      # Reverse/mute DSP
│   └── Utils.h/cpp                 # Logging and utilities
│
├── Models/                         # ASR model files
│   ├── vosk-model-small-en-us/    # Vosk English model (~40MB)
│   └── profanity_lexicon.txt      # List of profanity words/phrases
│
└── Libs/                           # Third-party libraries
    └── vosk/                       # Vosk SDK (headers + libs)
```

## Quick Start (Development)

### Prerequisites
1. **Visual Studio 2022** with C++ Desktop Development
2. **JUCE 7.x** framework (download from juce.com)
3. **Vosk SDK** (download from alphacephei.com/vosk)
4. **Vosk Model**: vosk-model-small-en-us-0.15 (~40MB)

### Build Steps
```powershell
# Navigate to project
cd C:\Users\andre\Desktop\Explicitly\desktop

# Generate Visual Studio project
cmake -B build -G "Visual Studio 17 2022"

# Build
cmake --build build --config Release

# Run
.\build\Release\ExplicitlyDesktop.exe
```

### Usage
1. Launch Explicitly Desktop application
2. Select input device (microphone or line-in)
3. Select output device (speakers/headphones)
4. Choose censorship mode (reverse or mute)
5. Click "Start Processing"
6. Speak or play audio - profanity censored with <150ms latency
7. Monitor real-time latency indicator in GUI

## Performance Requirements

### Latency Budget (<150ms Target)
```
Audio Capture:       10ms   (512 samples @ 48kHz)
Lock-Free Queue:     <1ms   
Vosk ASR:            50ms   (streaming inference)
Profanity Check:     <1ms   (lexicon matching)
Lock-Free Queue:     <1ms   
Censorship DSP:      <1ms   (reverse/mute + fade)
Audio Output:        10ms   (512 samples @ 48kHz)
────────────────────────────
TOTAL:              ~72ms   ✅ Under 150ms target
```

### Hardware Requirements
- **Minimum**: Intel i5/Ryzen 5, 4GB RAM, 100MB disk
- **Recommended**: Intel i7/Ryzen 7, 8GB RAM
- **OS**: Windows 10/11 (64-bit)
- **No GPU Required**: CPU-only streaming ASR

## Architecture Details

### Thread Model

**Audio Thread (Real-Time Critical)**
```cpp
Priority: THREAD_PRIORITY_TIME_CRITICAL
Affinity: Pinned to dedicated core (optional)
Allocations: None (pre-allocated buffers)
Locks: None (lock-free atomics only)
Buffer Size: 512 samples (10.67ms @ 48kHz)
```

Responsibilities:
1. Capture audio from input device
2. Write to 150-300ms circular buffer
3. Push audio chunks to ASR thread via lock-free queue
4. Apply censorship based on ASR results
5. Output filtered audio to speakers

**ASR Thread (Background Processing)**
```cpp
Priority: THREAD_PRIORITY_ABOVE_NORMAL
Allocations: Allowed (Vosk internal)
Streaming: Continuous partial results
```

Responsibilities:
1. Receive 20-50ms audio chunks from lock-free queue
2. Feed to Vosk streaming recognizer
3. Get partial transcripts with timestamps
4. Detect profanity from word tokens
5. Send censorship timestamps back to audio thread

### Buffer Management

**Circular Audio Buffer (150-300ms)**
```
Size: 0.3 seconds × 48000 Hz × 2 channels × 4 bytes = 115,200 bytes
Samples: 14,400 samples @ 48kHz stereo (300ms)
```

**Lock-Free Queues**
```cpp
// Audio → ASR (audio chunks)
struct AudioChunk {
    float samples[2048];  // 42.67ms @ 48kHz stereo
    int64_t buffer_position;
    int num_samples;
};
LockFreeQueue<AudioChunk, 32> audio_queue;

// ASR → Audio (censorship timestamps)
struct CensorEvent {
    int64_t start_sample;   // Absolute sample position
    int64_t end_sample;
    CensorMode mode;        // Reverse or mute
};
LockFreeQueue<CensorEvent, 256> censor_queue;
```

### ASR Processing Pipeline (Streaming)

```cpp
// ASR Thread main loop
while (running) {
    // 1. Get audio chunk from queue (non-blocking)
    AudioChunk chunk;
    if (audio_queue.try_pop(chunk)) {
        
        // 2. Feed to Vosk recognizer (streaming API)
        bool is_partial = vosk_recognizer_accept_waveform(
            recognizer, chunk.samples, chunk.num_samples
        );
        
        // 3. Get partial or final result
        const char* result_json = is_partial
            ? vosk_recognizer_partial_result(recognizer)
            : vosk_recognizer_result(recognizer);
        
        // 4. Parse JSON for word tokens with timestamps
        auto words = parse_vosk_result(result_json);
        
        // 5. Check each word against profanity lexicon
        for (auto& word : words) {
            if (profanity_lexicon.contains(word.text)) {
                
                // 6. Convert relative time to absolute sample position
                int64_t start = chunk.buffer_position + 
                                (word.start_time * sample_rate);
                int64_t end = chunk.buffer_position + 
                              (word.end_time * sample_rate);
                
                // 7. Send censorship event to audio thread
                censor_queue.push({start, end, current_mode});
            }
        }
    }
    
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
}
```

### Censorship DSP (Audio Thread)

**Reverse Mode**
```cpp
void reverse_samples(float* buffer, int64_t start, int64_t end) {
    int64_t length = end - start;
    
    // Reverse audio samples
    for (int64_t i = 0; i < length / 2; ++i) {
        std::swap(buffer[start + i], buffer[end - 1 - i]);
    }
    
    // Apply 3-5ms fade in/out for click-free transition
    apply_fade(buffer, start, 240);      // 5ms @ 48kHz
    apply_fade(buffer, end - 240, 240);
}
```

**Mute Mode**
```cpp
void mute_samples(float* buffer, int64_t start, int64_t end) {
    // Apply fade out
    apply_fade(buffer, start, 240);
    
    // Zero samples
    for (int64_t i = start + 240; i < end - 240; ++i) {
        buffer[i] = 0.0f;
    }
    
    // Apply fade in
    apply_fade(buffer, end - 240, 240);
}

void apply_fade(float* buffer, int64_t start, int fade_samples) {
    for (int i = 0; i < fade_samples; ++i) {
        float gain = float(i) / fade_samples;  // Linear ramp
        buffer[start + i] *= gain;
    }
}
```

## Implementation Checklist

### Phase 1: Core Audio (✅ Partially Complete)
- [x] Main.cpp - JUCE application entry
- [ ] MainComponent.h/cpp - GUI with start/stop, latency indicator
- [ ] AudioEngine.h/cpp - Real-time audio processing
- [x] CircularBuffer.h - Lock-free ring buffer (NEEDS RESIZE: 10s → 150-300ms)
- [ ] LockFreeQueue.h - Atomic queue for thread communication

### Phase 2: ASR Integration (⏳ Pending)
- [ ] ASRThread.h/cpp - Vosk streaming recognizer
- [ ] ProfanityFilter.h/cpp - Lexicon-based detection
- [ ] Download Vosk model (vosk-model-small-en-us-0.15)
- [ ] Integrate Vosk SDK (headers + libs)
- [ ] Test streaming ASR with real audio

### Phase 3: Censorship (⏳ Pending)
- [ ] CensorshipEngine.h/cpp - Reverse/mute DSP
- [ ] Implement fade in/out (3-5ms)
- [ ] Test censorship with profanity samples
- [ ] Verify no clicks or pops

### Phase 4: Testing & Optimization (⏳ Pending)
- [ ] Measure end-to-end latency (<150ms target)
- [ ] Test with continuous speech
- [ ] Test with music + vocals
- [ ] Stress test (prolonged operation)
- [ ] Profile CPU usage
- [ ] Optimize hot paths if needed

### Phase 5: Embedded Preparation (⏳ Future)
- [ ] Port to ARM architecture
- [ ] Optimize for embedded hardware
- [ ] Test on target device (Raspberry Pi 4, etc.)
- [ ] Benchmark power consumption

## Future Enhancements

- [ ] Picovoice Cheetah integration (sub-50ms ASR latency)
- [ ] Multi-language support (Spanish, French, etc.)
- [ ] Adjustable latency/quality tradeoff
- [ ] Real-time waveform visualization with censorship indicators
- [ ] Custom profanity lexicon editor
- [ ] Multiple censor modes (bleep sound, scramble, pitch shift)
- [ ] Statistics dashboard (latency graph, words censored count)
- [ ] Hardware acceleration (SIMD for DSP, GPU for Whisper if needed)

## License

Proprietary - Explicitly Audio Systems

## Support

For questions: support@explicitly.audio

---

**Important Note**: This desktop application is a **latency testing harness** to validate real-time profanity filtering feasibility (<200ms total latency) before porting to embedded ARM hardware. The design intentionally omits vocal separation (Demucs) to eliminate 6-8 second processing overhead, trading music background noise for real-time performance.
