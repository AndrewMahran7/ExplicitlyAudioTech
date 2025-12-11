# Complete Build Instructions - Explicitly Desktop

## Prerequisites Installation

### 1. Install Visual Studio 2022

```powershell
# Download from: https://visualstudio.microsoft.com/downloads/
# During installation, select "Desktop development with C++"
```

### 2. Install CMake

```powershell
# Option A: Download installer from https://cmake.org/download/

# Option B: Use winget
winget install Kitware.CMake

# Verify installation
cmake --version  # Should show 3.20 or higher
```

### 3. Install JUCE Framework

```powershell
# Clone JUCE to C:\JUCE
git clone https://github.com/juce-framework/JUCE.git C:\JUCE

# Verify
Test-Path C:\JUCE\modules  # Should return True
```

### 4. Download Vosk SDK

```powershell
# Download from: https://github.com/alphacep/vosk-api/releases
# For Windows, download: vosk-win64-0.3.45.zip (or latest version)

# Extract the ZIP file to C:\vosk-sdk\vosk-win64-0.3.45
# Then organize the files:

# Create directory structure
New-Item -ItemType Directory -Path "C:\vosk-sdk\include" -Force
New-Item -ItemType Directory -Path "C:\vosk-sdk\lib" -Force

# Copy files from extracted folder
Copy-Item "C:\vosk-sdk\vosk-win64-0.3.45\vosk_api.h" -Destination "C:\vosk-sdk\include\"
Copy-Item "C:\vosk-sdk\vosk-win64-0.3.45\libvosk.dll" -Destination "C:\vosk-sdk\lib\"
Copy-Item "C:\vosk-sdk\vosk-win64-0.3.45\libvosk.lib" -Destination "C:\vosk-sdk\lib\"

# IMPORTANT: Copy MinGW runtime DLLs (required for Vosk to work)
Copy-Item "C:\vosk-sdk\vosk-win64-0.3.45\libgcc_s_seh-1.dll" -Destination "C:\vosk-sdk\"
Copy-Item "C:\vosk-sdk\vosk-win64-0.3.45\libstdc++-6.dll" -Destination "C:\vosk-sdk\"
Copy-Item "C:\vosk-sdk\vosk-win64-0.3.45\libwinpthread-1.dll" -Destination "C:\vosk-sdk\"

# CRITICAL: Rename libvosk.lib to vosk.lib (CMake expects this name)
Rename-Item "C:\vosk-sdk\lib\libvosk.lib" -NewName "vosk.lib"

# Verify
Test-Path C:\vosk-sdk\include\vosk_api.h  # Should return True
Test-Path C:\vosk-sdk\lib\vosk.lib        # Should return True
Test-Path C:\vosk-sdk\lib\libvosk.dll     # Should return True
Test-Path C:\vosk-sdk\libgcc_s_seh-1.dll  # Should return True
```

### 5. Download Vosk Language Model

```powershell
# Download English model: vosk-model-small-en-us-0.15
# From: https://alphacephei.com/vosk/models

# Example download URL:
# https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip

# Extract to desktop\Models\vosk-model-small-en-us
# Final path should be:
# C:\Users\andre\Desktop\Explicitly\desktop\Models\vosk-model-small-en-us\

# Verify
Test-Path C:\Users\andre\Desktop\Explicitly\desktop\Models\vosk-model-small-en-us\am  # Should return True
```

## Build Steps

### 1. Navigate to Project

```powershell
cd C:\Users\andre\Desktop\Explicitly\desktop
```

### 2. Generate Visual Studio Project

```powershell
# Create build directory
New-Item -ItemType Directory -Path build -Force

# Generate project files
cmake -B build -G "Visual Studio 17 2022" `
    -DJUCE_DIR="C:/JUCE" `
    -DVOSK_SDK_DIR="C:/vosk-sdk"
```

If cmake succeeds, you should see:
```
===========================================
Explicitly Desktop Configuration
===========================================
JUCE Directory: C:/JUCE
Vosk SDK Directory: C:/vosk-sdk
Build Type: Debug
C++ Standard: 17
===========================================
-- Configuring done
-- Generating done
-- Build files have been written to: C:/Users/andre/Desktop/Explicitly/desktop/build
```

### 3. Build Project

```powershell
# Build Debug configuration
cmake --build build --config Debug

# Or build Release configuration
cmake --build build --config Release
```

### 4. Run Application

```powershell
# Debug build
.\build\bin\Debug\ExplicitlyDesktop.exe

# Release build
.\build\bin\Release\ExplicitlyDesktop.exe
```

## Troubleshooting

### Error: "JUCE not found"

```powershell
# Check if JUCE exists
Test-Path C:\JUCE\modules

# If not, clone JUCE
git clone https://github.com/juce-framework/JUCE.git C:\JUCE
```

### Error: "Vosk SDK not found"

```powershell
# Check if Vosk SDK exists
Test-Path C:\vosk-sdk\include\vosk_api.h

# If not, re-extract vosk-win64-*.zip to C:\vosk-sdk
```

### Error: "Vosk model not found"

The application looks for the model at:
```
C:\Users\andre\Desktop\Explicitly\desktop\Models\vosk-model-small-en-us\
```

Verify the model files exist:
```powershell
Get-ChildItem C:\Users\andre\Desktop\Explicitly\desktop\Models\vosk-model-small-en-us\
```

You should see:
- `am/` folder
- `conf/` folder
- `graph/` folder
- `ivector/` folder
- `README` file

### Error: "libvosk.dll not found"

The DLL should be automatically copied to the build output directory. If not:

```powershell
# Manually copy DLL
Copy-Item C:\vosk-sdk\bin\libvosk.dll -Destination .\build\bin\Debug\libvosk.dll
Copy-Item C:\vosk-sdk\bin\libvosk.dll -Destination .\build\bin\Release\libvosk.dll
```

### Compilation Errors

If you see C++ compilation errors:

1. Make sure Visual Studio 2022 is up to date
2. Clean and rebuild:
```powershell
Remove-Item -Recurse -Force build
cmake -B build -G "Visual Studio 17 2022" -DJUCE_DIR="C:/JUCE" -DVOSK_SDK_DIR="C:/vosk-sdk"
cmake --build build --config Release
```

## Opening in Visual Studio

You can also open the project directly in Visual Studio:

```powershell
# After running cmake -B build, open the solution
.\build\ExplicitlyDesktop.sln
```

Then build using Visual Studio's GUI (F7 or Build → Build Solution).

## Verifying Installation

After successful build, test the application:

1. Launch `ExplicitlyDesktop.exe`
2. You should see the main window with device selectors
3. Select an input device (microphone)
4. Select an output device (speakers)
5. Choose "Reverse" censor mode
6. Click "Start Processing"
7. Speak a profanity word
8. You should hear it reversed in real-time
9. Check the latency indicator (<150ms = green)

## File Locations Summary

```
C:\JUCE\                                           # JUCE Framework
C:\vosk-sdk\                                       # Vosk SDK
C:\Users\andre\Desktop\Explicitly\desktop\
    ├── build\                                     # CMake build output
    │   ├── bin\
    │   │   ├── Debug\ExplicitlyDesktop.exe        # Debug executable
    │   │   ├── Release\ExplicitlyDesktop.exe      # Release executable
    │   │   └── Release\Models\                    # Copied models
    │   └── ExplicitlyDesktop.sln                  # Visual Studio solution
    ├── Models\
    │   ├── vosk-model-small-en-us\                # Vosk language model
    │   └── profanity_en.txt                       # Profanity lexicon
    └── Source\
        ├── Main.cpp                               # Application entry
        ├── MainComponent.h/cpp                    # GUI
        ├── AudioEngine.h/cpp                      # Audio processing
        ├── ASRThread.h/cpp                        # Vosk integration
        ├── CircularBuffer.h                       # Ring buffer
        ├── LockFreeQueue.h                        # Thread communication
        ├── ProfanityFilter.h                      # Lexicon matching
        ├── CensorshipEngine.h                     # Reverse/mute DSP
        └── Types.h                                # Shared data structures
```

## Next Steps

Once the application builds and runs successfully:

1. **Latency Testing**: Measure end-to-end latency with test audio
2. **Accuracy Testing**: Verify profanity detection works correctly
3. **Stress Testing**: Run for 30+ minutes to check stability
4. **Optimization**: If latency >150ms, consider Picovoice Cheetah
5. **Embedded Port**: Prepare for Raspberry Pi 4/5 deployment

## Support

If you encounter issues not covered here, check:
- JUCE Forum: https://forum.juce.com/
- Vosk Documentation: https://alphacephei.com/vosk/
- Project README: `desktop/README.md`
