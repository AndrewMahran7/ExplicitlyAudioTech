# Explicitly Desktop - Implementation Status & Integration Guide

## What's Been Completed

### ✅ Architecture & Documentation
- [x] Complete system architecture designed for 10-second buffer
- [x] Virtual audio device routing (VB-Cable integration)
- [x] Build system (CMake configuration)
- [x] Installation and setup guides
- [x] Performance requirements documented

### ✅ Core C++ Components Created

#### 1. Application Framework
- **Main.cpp**: JUCE application entry point with lifecycle management
- **MainComponent.h/cpp**: GUI framework (needs implementation)
- Logging infrastructure
- Exception handling

#### 2. Real-Time Audio Buffer
- **CircularBuffer.h**: Lock-free circular buffer implementation
  - 10+ second capacity
  - Thread-safe read/write operations
  - Zero-copy access patterns
  - Wraparound index handling
  - Real-time safe (no allocations)

#### 3. Thread Architecture (Designed)
- Audio callback thread (real-time critical)
- ML processing thread (background)
- Lock-free communication via atomic queue

## What Needs Implementation

### 🔨 Components Requiring Your Python ML Code

#### 1. ProfanityProcessor.cpp
This is where your Python ML pipeline gets ported to C++:

```cpp
// Your Python pipeline:
// 1. separate.py -> Demucs vocal extraction
// 2. transcribe_align.py -> Whisper transcription  
// 3. detect.py -> Profanity detection
// 4. Generate timestamps

// Needs C++ implementation:
class ProfanityProcessor
{
public:
    // Main processing function called by ML thread
    std::vector<ProfaneWord> processAudioChunk(
        const AudioBuffer& chunk,  // 10 seconds of audio
        double sample_rate
    ) {
        // Step 1: Vocal separation (port from separate.py)
        AudioBuffer vocals = extractVocals(chunk);
        
        // Step 2: Transcription (port from transcribe_align.py)
        std::vector<Word> words = transcribe(vocals);
        
        // Step 3: Profanity detection (port from detect.py)
        std::vector<ProfaneWord> profane = detectProfanity(words);
        
        return profane;
    }
    
private:
    // These functions need your Python logic ported:
    AudioBuffer extractVocals(const AudioBuffer& audio);
    std::vector<Word> transcribe(const AudioBuffer& vocals);
    std::vector<ProfaneWord> detectProfanity(const std::vector<Word>& words);
};
```

**What I need from you:**
- Paste your `separate.py` Demucs code
- Paste your `transcribe_align.py` Whisper code
- Paste your `detect.py` profanity detection code
- Paste `lexicons/profanity_en.txt`

**What I'll do:**
- Port Demucs to ONNX Runtime C++ API
- Port Whisper to ONNX Runtime C++ API
- Port profanity lexicon matching to C++
- Optimize for real-time performance

#### 2. AudioEngine.cpp
Main audio processing engine:

```cpp
class AudioEngine : public juce::AudioIODeviceCallback
{
public:
    // JUCE audio callback - called every ~20ms with 512-2048 samples
    void audioDeviceIOCallback(
        const float** inputChannelData,
        int numInputChannels,
        float** outputChannelData,
        int numOutputChannels,
        int numSamples) override
    {
        // 1. Write incoming audio to circular buffer
        circularBuffer.writeSamples(inputChannelData, numSamples);
        
        // 2. Check for new profanity timestamps from ML thread
        while (resultsQueue.pop(result)) {
            pendingCensorships.push_back(result);
        }
        
        // 3. Read audio from 10 seconds ago in buffer
        // 4. Apply any censorship that falls in this time range
        // 5. Output filtered audio
        
        readFromBuffer(outputChannelData, numSamples);
        applyCensorships(outputChannelData, numSamples);
    }
    
private:
    CircularAudioBuffer circularBuffer;  // ✅ Already implemented
    LockFreeQueue<CensorResult> resultsQueue;  // Needs creation
    std::thread mlThread;  // Needs implementation
};
```

**Status:**
- Structure designed ✅
- Circular buffer implemented ✅
- Audio callback skeleton needs completion 🔨
- ML thread integration needs implementation 🔨

#### 3. CensorshipEngine.cpp
DSP for mute/reverse operations:

```cpp
class CensorshipEngine
{
public:
    // Apply reverse effect (your Python uses this)
    void reverseSamples(float* buffer, int64_t start, int64_t end)
    {
        // Port from your censor.py reverse logic
        int64_t length = end - start;
        for (int64_t i = 0; i < length / 2; ++i) {
            std::swap(buffer[start + i], buffer[end - 1 - i]);
        }
        applyFade(buffer, start, 5ms);  // Smooth edges
        applyFade(buffer, end, 5ms);
    }
    
    // Apply mute effect
    void muteSamples(float* buffer, int64_t start, int64_t end)
    {
        // Port from your censor.py mute logic
        std::memset(buffer + start, 0, (end - start) * sizeof(float));
        applyFade(buffer, start, 5ms);
        applyFade(buffer, end, 5ms);
    }
};
```

**What I need:**
- Your `censor.py` fade implementation details
- Margin settings (pre_margin_ms, post_margin_ms)

### 🔨 Additional Components Needed

#### 4. LockFreeQueue.h
Thread-safe queue for ML→Audio communication:

```cpp
template<typename T, size_t Capacity>
class LockFreeQueue
{
public:
    bool push(const T& item);  // ML thread writes results
    bool pop(T& item);         // Audio thread reads results
    
private:
    std::array<T, Capacity> data;
    std::atomic<size_t> writePos;
    std::atomic<size_t> readPos;
};
```

**Status:** Design ready, needs implementation 🔨

#### 5. MainComponent.cpp
GUI with controls:

```cpp
class MainComponent : public juce::Component
{
public:
    // UI Elements needed:
    - TextButton startStopButton;
    - Label latencyLabel;  // Shows "Latency: 10.2 seconds"
    - Label statusLabel;   // Shows "Processing..." / "Ready"
    - ComboBox censorModeBox;  // "Reverse" / "Mute" / "Pass-through"
    - ComboBox inputDeviceBox;  // Virtual device selection
    - ComboBox outputDeviceBox; // Hardware device selection
    
    void startButtonClicked()
    {
        audioEngine.start();  // Begin processing
    }
    
    void stopButtonClicked()
    {
        audioEngine.stop();  // Stop processing
    }
};
```

**Status:** Framework exists ✅, controls need implementation 🔨

## ML Model Integration Strategy

### Option A: ONNX Runtime (Recommended)

**Convert Python models to ONNX:**

```python
# Convert Demucs to ONNX
import torch
import onnx

demucs_model = load_demucs_model()
dummy_input = torch.randn(1, 2, 480000)  # 10 seconds stereo

torch.onnx.export(
    demucs_model,
    dummy_input,
    "desktop/Models/demucs.onnx",
    input_names=['audio_input'],
    output_names=['vocals', 'drums', 'bass', 'other'],
    dynamic_axes={'audio_input': {2: 'length'}}
)

# Convert Whisper to ONNX
whisper_model = load_whisper_model()
# ... similar export process
```

**Load in C++:**

```cpp
#include <onnxruntime/core/session/onnxruntime_cxx_api.h>

class DemucsONNX
{
public:
    DemucsONNX(const char* model_path)
    {
        Ort::SessionOptions options;
        options.SetIntraOpNumThreads(4);
        options.SetGraphOptimizationLevel(ORT_ENABLE_ALL);
        
        session = Ort::Session(env, model_path, options);
    }
    
    AudioBuffer extractVocals(const AudioBuffer& mixed)
    {
        // Run ONNX inference
        // Returns isolated vocals
    }
    
private:
    Ort::Env env;
    Ort::Session session;
};
```

### Option B: Direct PyTorch Integration

```cpp
// Embed Python interpreter in C++
#include <Python.h>
#include <torch/script.h>

class PythonMLProcessor
{
public:
    PythonMLProcessor()
    {
        // Initialize Python
        Py_Initialize();
        
        // Load your Python modules
        PyRun_SimpleString("import sys");
        PyRun_SimpleString("sys.path.append('../website/explicitly')");
        
        separate_module = PyImport_ImportModule("separate");
        detect_module = PyImport_ImportModule("detect");
    }
    
    // Call Python functions from C++
};
```

**Pros:** No model conversion needed
**Cons:** Slower, more complex deployment

## Next Steps - What I Need From You

### 1. Paste Your Python ML Code

Please provide:
- `website/explicitly/separate.py` (Demucs vocal extraction)
- `website/explicitly/transcribe_align.py` (Whisper transcription)
- `website/explicitly/stable_transcribe.py` (If you use this instead)
- `website/explicitly/detect.py` (Profanity detection)
- `website/explicitly/censor.py` (Reverse/mute logic)
- `lexicons/profanity_en.txt` (Word list)

### 2. Answer Architecture Questions

**Q1: Which approach do you prefer?**
- [ ] Option A: Convert models to ONNX (faster, cleaner)
- [ ] Option B: Embed Python (easier, slower)

**Q2: GPU requirements?**
- [ ] Must support CPU-only mode
- [ ] GPU required (CUDA)
- [ ] Both with fallback

**Q3: Censorship modes?**
- [ ] Reverse only
- [ ] Mute only
- [ ] Both + pass-through

### 3. Test Your Python Pipeline

Run this test to get timing baseline:

```python
# Test script to measure your ML pipeline timing
import time
from pathlib import Path

from explicitly.separate import StemSeparator
from explicitly.transcribe_align import transcribe_audio
from explicitly.detect import detect_profanity

# Load 10 seconds of test audio
audio_path = "test_audio_10sec.mp3"

# Time each step
t0 = time.time()

# Demucs
separator = StemSeparator(model_name="htdemucs", device="cuda")
stems = separator.separate_vocals_instrumental(audio_path, "test_stems")
t1 = time.time()

# Whisper
words = transcribe_audio(stems['vocals'])
t2 = time.time()

# Detection
profane = detect_profanity(words, "lexicons/profanity_en.txt")
t3 = time.time()

print(f"Demucs: {t1-t0:.2f}s")
print(f"Whisper: {t2-t1:.2f}s")
print(f"Detection: {t3-t2:.2f}s")
print(f"Total: {t3-t0:.2f}s")
```

Send me the timing results.

## Implementation Timeline

Once I have your Python code:

**Phase 1: Core ML Integration (2-3 days)**
- Port Demucs to C++ (ONNX or PyTorch)
- Port Whisper to C++ 
- Port profanity lexicon matching
- Unit tests for each component

**Phase 2: Audio Engine (1-2 days)**
- Complete AudioEngine.cpp
- ML thread implementation
- Lock-free queue
- Timestamp mapping logic

**Phase 3: GUI & Polish (1 day)**
- MainComponent UI controls
- Status indicators
- Device selection
- Settings panel

**Phase 4: Testing & Optimization (2 days)**
- End-to-end testing
- Performance profiling
- Memory optimization
- Edge case handling

**Total: ~1 week** after receiving your Python code

## Current File Status

```
✅ = Complete
🔨 = Needs implementation
📋 = Waiting for your Python code

desktop/
├── README.md                    ✅ Complete architecture docs
├── BUILDING.md                  ✅ Complete build guide  
├── DRIVER_SETUP.md             ✅ Complete driver guide
├── INTEGRATION_STATUS.md       ✅ This file
│
├── Source/
│   ├── Main.cpp                ✅ Application entry point
│   ├── CircularBuffer.h        ✅ Lock-free audio buffer
│   ├── MainComponent.h         🔨 Needs GUI implementation
│   ├── MainComponent.cpp       🔨 Needs GUI implementation
│   ├── AudioEngine.h           🔨 Needs completion
│   ├── AudioEngine.cpp         🔨 Needs completion
│   ├── ProfanityProcessor.h    📋 Awaiting Python code
│   ├── ProfanityProcessor.cpp  📋 Awaiting Python code
│   ├── CensorshipEngine.h      📋 Awaiting censor.py
│   ├── CensorshipEngine.cpp    📋 Awaiting censor.py
│   ├── LockFreeQueue.h         🔨 Needs implementation
│   └── Utils.h/cpp             🔨 Needs implementation
│
└── Models/
    ├── README.txt              ✅ Model placement instructions
    └── lexicon.txt             📋 Awaiting from you
```

## Ready to Continue?

**I'm ready to complete the implementation once you provide:**

1. ✅ Your Python ML code (separate, transcribe, detect, censor)
2. ✅ Profanity lexicon file
3. ✅ Timing test results (how long each step takes)
4. ✅ Architecture preferences (ONNX vs embedded Python)

**Reply with:**
```
"Ready to integrate ML - using [ONNX/Python] approach"
[Paste your Python code here]
```

And I'll complete the full C++ implementation with your ML pipeline integrated!
