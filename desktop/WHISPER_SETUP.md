# Whisper.cpp Setup Instructions

## Quick Setup

### 1. Download Whisper.cpp

```powershell
# Clone the repository
cd C:\
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp

# Build with Visual Studio
cmake -B build -G "Visual Studio 17 2022" -DBUILD_SHARED_LIBS=ON
cmake --build build --config Release
```

### 2. Download Whisper Model

```powershell
# Download the tiny.en model (fastest, good accuracy)
cd C:\whisper.cpp
curl -L "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin" -o models/ggml-tiny.en.bin

# OR download base.en (better accuracy, slower)
curl -L "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin" -o models/ggml-base.en.bin
```

### 3. Verify Installation

After building, verify these files exist:

```powershell
# Check library files
Test-Path "C:\whisper.cpp\build\bin\Release\whisper.dll"      # Should be True
Test-Path "C:\whisper.cpp\build\Release\whisper.lib"          # Should be True
Test-Path "C:\whisper.cpp\whisper.h"                          # Should be True
Test-Path "C:\whisper.cpp\models\ggml-tiny.en.bin"           # Should be True
```

### 4. Copy Files to Project

```powershell
# Create whisper SDK directory
New-Item -ItemType Directory -Path "C:\whisper-sdk" -Force
New-Item -ItemType Directory -Path "C:\whisper-sdk\include" -Force
New-Item -ItemType Directory -Path "C:\whisper-sdk\lib" -Force

# Copy header
Copy-Item "C:\whisper.cpp\whisper.h" -Destination "C:\whisper-sdk\include\"

# Copy library files
Copy-Item "C:\whisper.cpp\build\Release\whisper.lib" -Destination "C:\whisper-sdk\lib\"
Copy-Item "C:\whisper.cpp\build\bin\Release\whisper.dll" -Destination "C:\whisper-sdk\lib\"

# Copy model to project
Copy-Item "C:\whisper.cpp\models\ggml-tiny.en.bin" -Destination "C:\Users\andre\Desktop\Explicitly\desktop\Models\"
```

## Model Comparison

| Model | Size | Speed | Accuracy | Latency |
|-------|------|-------|----------|---------|
| tiny.en | 75 MB | Fastest | Good | ~100ms |
| base.en | 140 MB | Fast | Better | ~150ms |
| small.en | 460 MB | Medium | Best | ~300ms |

**Recommendation**: Use `tiny.en` for <150ms latency requirement.

## Whisper.cpp vs Vosk

**Advantages:**
- More stable (no crashes)
- Better accuracy
- Actively maintained (updated weekly)
- Native C++ (no FFI issues)
- Better documentation

**Setup Time:**
- Building from source: ~5 minutes
- Model download: ~30 seconds
- Integration: Already done!

## Troubleshooting

### Build Errors

If CMake fails, ensure Visual Studio 2022 is installed with C++ tools:
```powershell
# Check VS installation
Get-Command cl.exe
```

### Model Download Issues

If curl fails, download manually:
- Tiny model: https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin
- Base model: https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin

Save to `C:\whisper.cpp\models\`

## Next Steps

After completing setup, the project will automatically:
1. Detect Whisper instead of Vosk
2. Load the tiny.en model
3. Process audio with ~100ms latency
4. Return word-level timestamps for profanity detection

Run the rebuild command from the project directory:
```powershell
cd C:\Users\andre\Desktop\Explicitly\desktop
cmake -B build -G "Visual Studio 17 2022" -DJUCE_DIR="C:/JUCE" -DWHISPER_SDK_DIR="C:/whisper-sdk"
cmake --build build --config Release
```
