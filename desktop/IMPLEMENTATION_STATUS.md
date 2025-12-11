# Explicitly Desktop - Implementation Status

**Architecture**: Ultra-low latency streaming ASR (<200ms)  
**Last Updated**: December 9, 2024

## Overview

This desktop application is a **latency testing harness** to validate real-time profanity filtering feasibility before porting to embedded ARM hardware.

**Key Design Constraints**:
- Target latency: <150ms, max 300ms acceptable
- NO Demucs, NO Whisper, NO vocal separation
- Streaming ASR only (Vosk or Picovoice Cheetah)
- 150-300ms circular buffer
- Simple lexicon-based profanity detection
- Reverse/mute DSP with fade

---

## Phase 1: Core Audio Infrastructure

### ✅ Completed Components

#### `Main.cpp` (170 lines)
- JUCE application entry point
- Application lifecycle management
- MainWindow class stub
- Logging infrastructure
- **Status**: Basic structure valid, needs update for streaming ASR

#### `CircularBuffer.h` (264 lines)
- Lock-free circular buffer implementation
- Thread-safe read/write with atomic positions
- Wraparound handling
- **Status**: Needs capacity reduction from 10 seconds to 150-300ms

#### `LockFreeQueue.h` (NEW - 163 lines)
- Single-producer single-consumer queue
- Lock-free atomic operations
- Audio → ASR and ASR → Audio communication
- **Status**: ✅ Complete

#### `ProfanityFilter.h` (NEW - 198 lines)
- Lexicon-based profanity detection
- Multi-token phrase support (e.g., "what the hell")
- <1ms string matching
- Loads from profanity_lexicon.txt
- **Status**: ✅ Complete

#### `CensorshipEngine.h` (NEW - 233 lines)
- Reverse/mute DSP
- 3-5ms fade in/out for click-free transitions
- Real-time safe (no allocations)
- **Status**: ✅ Complete

### ⏳ Pending Components

#### `MainComponent.h/cpp`
- GUI with controls
- Start/Stop button
- Real-time latency indicator
- Input/output device selection
- Censor mode selector (reverse/mute)
- **Estimate**: 250 lines

#### `AudioEngine.h/cpp`
- Lock-free audio callback
- Captures audio from input device
- Writes to circular buffer
- Applies censorship based on ASR results
- Outputs to speakers
- **Estimate**: 350 lines

#### `ASRThread.h/cpp`
- Vosk streaming recognizer integration
- Receives audio chunks from queue
- Produces partial transcripts with timestamps
- Detects profanity via ProfanityFilter
- Sends censorship events to audio thread
- **Estimate**: 400 lines

---

## Phase 2: ASR Integration

### Vosk SDK Setup

**What's Needed**:
1. Download Vosk SDK for Windows (C++)
2. Extract to `C:\vosk-sdk\`
3. Download `vosk-model-small-en-us-0.15` (~40MB)
4. Extract to `desktop\Models\vosk-model-small-en-us\`

**CMakeLists.txt Changes**:
```cmake
# Add Vosk include path
include_directories(C:/vosk-sdk/include)

# Link Vosk library
target_link_libraries(ExplicitlyDesktop
    PRIVATE
        C:/vosk-sdk/lib/vosk.lib
)

# Copy DLL to output directory
add_custom_command(TARGET ExplicitlyDesktop POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        C:/vosk-sdk/bin/libvosk.dll
        $<TARGET_FILE_DIR:ExplicitlyDesktop>
)
```

### ASRThread Implementation Plan

**Core Responsibilities**:
1. Initialize Vosk model and recognizer
2. Poll lock-free queue for audio chunks
3. Feed audio to Vosk streaming API
4. Parse JSON results for word tokens + timestamps
5. Check tokens against ProfanityFilter
6. Send censorship events to audio thread

**Vosk API Usage**:
```cpp
// Initialize (once at startup)
VoskModel* model = vosk_model_new("Models/vosk-model-small-en-us");
VoskRecognizer* recognizer = vosk_recognizer_new(model, 48000.0);

// Processing loop
while (running) {
    // Get audio chunk from queue
    AudioChunk chunk;
    if (audio_queue.pop(chunk)) {
        // Feed to recognizer
        int result = vosk_recognizer_accept_waveform(
            recognizer, 
            (const char*)chunk.samples, 
            chunk.num_samples * sizeof(float)
        );
        
        // Get result (partial or final)
        const char* json = result 
            ? vosk_recognizer_result(recognizer)
            : vosk_recognizer_partial_result(recognizer);
        
        // Parse JSON and detect profanity
        parseAndDetect(json, chunk.buffer_position);
    }
    
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
}
```

---

## Phase 3: GUI Implementation

### MainComponent Requirements

**Controls**:
- Start/Stop processing button
- Input device dropdown (microphone, line-in)
- Output device dropdown (speakers, headphones)
- Censor mode selector (Reverse, Mute)
- Real-time latency indicator (milliseconds)
- Status text (processing, idle, error)

**Layout**:
```
┌────────────────────────────────────────┐
│  Explicitly Desktop - Real-Time Filter │
├────────────────────────────────────────┤
│  Input Device:  [Microphone      ▼]   │
│  Output Device: [Speakers        ▼]   │
│  Censor Mode:   [Reverse         ▼]   │
│                                        │
│  [Start Processing]                   │
│                                        │
│  Status: Processing                   │
│  Latency: 72ms                        │
└────────────────────────────────────────┘
```

---

## Phase 4: Testing & Validation

### Latency Measurement

**How to Measure**:
1. Generate test audio with known profanity at known timestamps
2. Record output audio
3. Compare input vs output timestamps
4. Calculate delta = output_time - input_time

**Target Metrics**:
- Average latency: <150ms
- 95th percentile: <200ms
- 99th percentile: <300ms

### Test Cases

1. **Single Word Profanity**
   - Input: "This is damn good"
   - Expected: "damn" reversed/muted

2. **Multi-Token Profanity**
   - Input: "What the hell is this"
   - Expected: "what the hell" reversed/muted

3. **Rapid Fire**
   - Input: "Damn damn damn"
   - Expected: All three instances censored

4. **Music + Vocals**
   - Input: Song with profanity
   - Expected: Censorship despite background music

5. **Stress Test**
   - 30+ minutes continuous operation
   - No memory leaks
   - No audio dropouts

---

## Phase 5: Optimization (If Needed)

### If Latency >150ms

**Potential Optimizations**:
1. Switch to Picovoice Cheetah (<50ms ASR)
2. Reduce buffer size to 150ms (from 300ms)
3. Use smaller Vosk model (trade accuracy for speed)
4. SIMD optimization for censorship DSP
5. Thread affinity tuning (pin audio thread to core)

### If CPU Usage Too High

**Potential Optimizations**:
1. Reduce ASR polling frequency
2. Optimize profanity lexicon (trie data structure)
3. Batch audio chunk processing
4. Profile with perf tools (VTune, Very Sleepy)

---

## Build Status Summary

| Component | Status | Lines | Notes |
|-----------|--------|-------|-------|
| Main.cpp | ✅ | 170 | Needs minor updates |
| CircularBuffer.h | ⚠️ | 264 | Resize 10s → 300ms |
| LockFreeQueue.h | ✅ | 163 | Complete |
| ProfanityFilter.h | ✅ | 198 | Complete |
| CensorshipEngine.h | ✅ | 233 | Complete |
| MainComponent.h/cpp | ❌ | 0 | Not started |
| AudioEngine.h/cpp | ❌ | 0 | Not started |
| ASRThread.h/cpp | ❌ | 0 | Not started |
| CMakeLists.txt | ⚠️ | 0 | Needs Vosk integration |
| README.md | ✅ | 411 | Complete (streaming ASR) |
| BUILDING.md | ✅ | 309 | Updated for Vosk |

**Estimated Remaining Work**: 1000-1200 lines of C++ code

---

## Next Steps

1. **Resize CircularBuffer**: Change capacity from 10 seconds to 300ms
2. **Create MainComponent**: GUI with controls and status display
3. **Create AudioEngine**: Lock-free audio processing with censorship
4. **Create ASRThread**: Vosk streaming integration
5. **Update CMakeLists.txt**: Add Vosk SDK linking
6. **Build & Test**: Measure latency, validate censorship accuracy
7. **Optimize**: If needed, switch to Cheetah or tune parameters

---

## Questions for User

1. Do you have the Vosk SDK downloaded already? Or should I provide download links?
2. Do you want to test with Vosk first (free, offline) or go straight to Picovoice Cheetah (commercial, faster)?
3. What's your target embedded hardware? (Raspberry Pi 4, NVIDIA Jetson, custom ARM board?)
4. Do you need profanity lexicon from the website project, or create a new one?

---

**Ready to continue implementation once you confirm the approach.**
