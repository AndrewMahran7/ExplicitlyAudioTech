# Building Explicitly Desktop

## System Requirements

### Development Environment
- **Windows 10/11** (64-bit)
- **Visual Studio 2022** with C++ Desktop Development workload
- **CMake 3.20+**
- **JUCE Framework 7.x** 

### Runtime Requirements  
- **Vosk SDK**: Lightweight streaming ASR library
- **Vosk Model**: vosk-model-small-en-us-0.15 (~40MB)
- **CPU**: Intel i5/AMD Ryzen 5 or better (no GPU required)
- **RAM**: 4GB minimum, 8GB recommended

## Quick Start Build

### 1. Install Prerequisites

**Visual Studio 2022**
```powershell
# Download from: https://visualstudio.microsoft.com/downloads/
# Install "Desktop development with C++" workload
```

**JUCE Framework**
```powershell
# Download Projucer from: https://juce.com/get-juce/download
# Or clone from GitHub
git clone https://github.com/juce-framework/JUCE.git C:\JUCE
```

**CMake**
```powershell
# Download from: https://cmake.org/download/
# Or use winget
winget install Kitware.CMake
```

**Vosk SDK**
```powershell
# Download from: https://github.com/alphacep/vosk-api/releases
# Get: vosk-win64-x.x.x.zip
# Extract to C:\vosk-sdk

# Your directory structure should look like:
# C:\vosk-sdk\
#   include\
#     vosk_api.h
#   lib\
#     vosk.lib
#   bin\
#     libvosk.dll
```

**Vosk Model**
```powershell
# Download from: https://alphacephei.com/vosk/models
# Get: vosk-model-small-en-us-0.15.zip (~40MB)
# Extract to desktop\Models\vosk-model-small-en-us

cd C:\Users\andre\Desktop\Explicitly\desktop\Models
# Download
Invoke-WebRequest -Uri "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip" -OutFile "vosk-model.zip"
# Extract
Expand-Archive -Path "vosk-model.zip" -DestinationPath "."
# Rename
Rename-Item "vosk-model-small-en-us-0.15" "vosk-model-small-en-us"
```

### 3. Clone Project

```powershell
cd C:\Users\andre\Desktop\Explicitly
# Desktop folder already exists with source files
```

### 4. Configure Build

```powershell
cd desktop

# Create build directory
mkdir build
cd build

# Generate Visual Studio solution
cmake .. -G "Visual Studio 17 2022" -A x64 `
  -DJUCE_DIR="C:/JUCE" `
  -DONNXRUNTIME_DIR="C:/onnxruntime"
```

### 5. Build

```powershell
# Build Release configuration
cmake --build . --config Release

# Or open in Visual Studio
start ExplicitlyDesktop.sln
# Then Build > Build Solution (Ctrl+Shift+B)
```

### 6. Run

```powershell
# Run from build directory
.\Release\ExplicitlyDesktop.exe

# Or install to Program Files
cmake --install . --config Release
```

## Project Structure

```
desktop/
├── CMakeLists.txt              # Main build configuration
├── README.md                   # Architecture overview
├── BUILDING.md                 # This file
├── DRIVER_SETUP.md             # Virtual driver guide
│
├── Source/                     # C++ source files
│   ├── Main.cpp                # Entry point
│   ├── MainComponent.h/cpp     # GUI
│   ├── AudioEngine.h/cpp       # Core audio processing
│   ├── CircularBuffer.h        # Lock-free audio buffer
│   ├── LockFreeQueue.h         # Thread-safe queue
│   ├── ProfanityProcessor.h/cpp# ML processing
│   └── CensorshipEngine.h/cpp  # DSP censorship
│
├── Models/                     # ML models (ONNX format)
│   ├── demucs/                 # Vocal separation
│   ├── whisper/                # Speech recognition
│   └── lexicon.txt             # Profanity words
│
└── build/                      # Generated build files
    └── Release/
        └── ExplicitlyDesktop.exe
```

## CMake Options

```powershell
# Enable GPU acceleration (requires CUDA)
cmake .. -DUSE_CUDA=ON

# Disable ML features (pass-through only)
cmake .. -DDISABLE_ML=ON

# Custom JUCE path
cmake .. -DJUCE_DIR="D:/SDKs/JUCE"

# Custom ONNX Runtime path
cmake .. -DONNXRUNTIME_DIR="D:/SDKs/onnxruntime"

# Enable debug logging
cmake .. -DCMAKE_BUILD_TYPE=Debug -DVERBOSE_LOGGING=ON
```

## Troubleshooting

### JUCE Not Found
```powershell
# Set JUCE_DIR environment variable
setx JUCE_DIR "C:\JUCE"

# Or specify in cmake command
cmake .. -DJUCE_DIR="C:/JUCE"
```

### ONNX Runtime Not Found
```powershell
# Download from GitHub releases
# Extract to C:\onnxruntime
# Ensure directory structure:
# C:\onnxruntime\
#   ├── include\
#   │   └── onnxruntime\
#   └── lib\
#       └── onnxruntime.lib
```

### Virtual Audio Device Not Detected
```powershell
# Check device installation
# Control Panel > Sound > Playback Devices
# Should see "VB-Cable Input" or "Explicitly Filter"

# Restart audio service
net stop audiosrv
net start audiosrv
```

### Build Errors: Missing Headers
```powershell
# Ensure all JUCE modules are available
# Check JUCE/modules/ directory exists

# Re-run CMake with verbose output
cmake .. -DCMAKE_VERBOSE_MAKEFILE=ON
```

### Runtime Error: Models Not Found
```powershell
# Models must be in same directory as .exe
# Or set environment variable
setx EXPLICITLY_MODELS_DIR "C:\Users\andre\Desktop\Explicitly\desktop\Models"
```

## Performance Optimization

### GPU Acceleration
```powershell
# Install CUDA Toolkit 11.8+
# https://developer.nvidia.com/cuda-downloads

# Install cuDNN 8.9+
# https://developer.nvidia.com/cudnn

# Rebuild with CUDA support
cmake .. -DUSE_CUDA=ON
cmake --build . --config Release
```

### CPU Optimization
```powershell
# Build with AVX2 support (faster on modern CPUs)
cmake .. -DUSE_AVX2=ON

# Enable link-time optimization
cmake .. -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON
```

## Testing

### Unit Tests
```powershell
# Build tests
cmake .. -DBUILD_TESTS=ON
cmake --build . --config Release --target Tests

# Run tests
ctest -C Release --output-on-failure
```

### Integration Test
```powershell
# Run application with test audio
.\Release\ExplicitlyDesktop.exe --test-mode

# Check logs
type "%APPDATA%\Explicitly\log.txt"
```

## Packaging for Distribution

### Create Installer
```powershell
# Install NSIS
winget install NSIS.NSIS

# Generate installer
cmake --build . --config Release --target package

# Output: ExplicitlyDesktop-1.0.0-win64.exe
```

### Portable Version
```powershell
# Copy files to distribution folder
mkdir dist
copy Release\ExplicitlyDesktop.exe dist\
copy ..\Models\* dist\Models\
copy C:\onnxruntime\bin\onnxruntime.dll dist\

# Create ZIP
Compress-Archive -Path dist\* -DestinationPath ExplicitlyDesktop-Portable.zip
```

## Development Workflow

### Recommended IDE Setup
1. Open `ExplicitlyDesktop.sln` in Visual Studio 2022
2. Set `ExplicitlyDesktop` as startup project
3. Configure debugging:
   - Working Directory: `$(ProjectDir)..\`
   - Command Arguments: `--log-level=debug`

### Hot Reload (Experimental)
```powershell
# Enable Edit and Continue
# Tools > Options > Debugging > Edit and Continue
# ☑ Enable Edit and Continue
```

### Profiling
```powershell
# Use Visual Studio Performance Profiler
# Debug > Performance Profiler
# Select: CPU Usage, Memory Usage

# Or use Intel VTune
# https://www.intel.com/content/www/us/en/developer/tools/oneapi/vtune-profiler.html
```

## Support

For build issues:
- Check GitHub Issues: github.com/explicitly/desktop/issues
- Discord: discord.gg/explicitly
- Email: dev@explicitly.audio
