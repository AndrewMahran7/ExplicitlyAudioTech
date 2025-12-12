# Building Explicitly for Orange Pi Zero 3

## Prerequisites

### On Orange Pi Zero 3 (Native Build)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install build tools
sudo apt install -y build-essential cmake git

# Install ALSA development libraries
sudo apt install -y libasound2-dev

# Install additional dependencies
sudo apt install -y wget curl
```

### On Desktop (Cross-Compilation) - Optional

For faster builds, you can cross-compile on your x86-64 machine:

```bash
# Install ARM64 cross-compilation toolchain
sudo apt install -y gcc-aarch64-linux-gnu g++-aarch64-linux-gnu

# Set up CMake toolchain file (see below)
```

## Building Whisper.cpp for ARM64

Whisper.cpp must be built first as a dependency.

### Option 1: Native Build on Orange Pi

```bash
cd ~/
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp

# Build for ARM64 with NEON optimizations
make -j4

# This creates libwhisper.a
ls -lh libwhisper.a  # Should be ~2-3 MB
```

### Option 2: Cross-Compile on Desktop

```bash
cd ~/
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp

# Cross-compile for ARM64
make CC=aarch64-linux-gnu-gcc CXX=aarch64-linux-gnu-g++ -j$(nproc)

# Copy to Orange Pi later
```

## Building Explicitly Hardware

### Option 1: Native Build on Orange Pi (Recommended for First Time)

```bash
# Clone repository (adjust path as needed)
cd ~/
git clone https://your-repo/explicitly
cd explicitly/hardware

# Create build directory
mkdir build && cd build

# Configure CMake
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DWHISPER_DIR=~/whisper.cpp

# Build (will take 5-15 minutes on Orange Pi)
make -j4

# Check binary
ls -lh explicitly-daemon
file explicitly-daemon  # Should show: ELF 64-bit LSB executable, ARM aarch64

# Optional: Install system-wide
sudo make install
```

### Option 2: Cross-Compile on Desktop

Create a toolchain file `arm64-toolchain.cmake`:

```cmake
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(CMAKE_C_COMPILER aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)

set(CMAKE_FIND_ROOT_PATH /usr/aarch64-linux-gnu)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
```

Then build:

```bash
cd explicitly/hardware
mkdir build-arm64 && cd build-arm64

cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE=../arm64-toolchain.cmake \
    -DWHISPER_DIR=/path/to/whisper.cpp-arm64 \
    -DALSA_LIBRARY=/usr/aarch64-linux-gnu/lib/libasound.so \
    -DALSA_INCLUDE_DIR=/usr/aarch64-linux-gnu/include

make -j$(nproc)

# Copy to Orange Pi
scp explicitly-daemon orangepi@orangepi.local:~/
```

## Copying Required Source Files

The build requires some source files from the desktop version:

```bash
cd explicitly/hardware

# Create src directory structure
mkdir -p src

# Copy shared components from desktop
cp ../desktop/Source/ProfanityFilter.h src/
cp ../desktop/Source/VocalFilter.cpp src/
cp ../desktop/Source/VocalFilter.h src/
cp ../desktop/Source/TimestampRefiner.cpp src/
cp ../desktop/Source/TimestampRefiner.h src/
cp ../desktop/Source/LyricsAlignment.cpp src/
cp ../desktop/Source/LyricsAlignment.h src/
cp ../desktop/Source/Types.h src/
cp ../desktop/Source/CircularBuffer.h src/
cp ../desktop/Source/LockFreeQueue.h src/

# Note: ProfanityFilter.h is header-only, but you may need to adapt it
# to remove JUCE dependencies (replace juce::File with std::ifstream)
```

## Installing cpp-httplib

The HTTP API server uses cpp-httplib (single-header library):

```bash
cd explicitly/hardware/src

# Download latest release
wget https://raw.githubusercontent.com/yhirose/cpp-httplib/master/httplib.h

# That's it! It's a single-header library
```

## Troubleshooting Build Issues

### Missing ALSA Headers

```bash
sudo apt install -y libasound2-dev
```

### Whisper.cpp Not Found

Make sure `WHISPER_DIR` points to the correct location:

```bash
cmake .. -DWHISPER_DIR=/home/orangepi/whisper.cpp
```

### Undefined Reference Errors

If you get linker errors about Whisper functions, rebuild whisper.cpp:

```bash
cd ~/whisper.cpp
make clean
make -j4
```

### ARM Optimization Warnings

If you see warnings about unknown CPU features, that's normal. The build will still work.

## Build Output

Successful build creates:

- `explicitly-daemon` - Main executable (~2-3 MB)
- Links to:
  - `libwhisper.a` (~2-3 MB statically linked)
  - `libasound.so` (ALSA, dynamically linked)
  - `libpthread.so` (threading, dynamically linked)

Check dependencies:

```bash
ldd explicitly-daemon
```

Should show:
```
linux-vdso.so.1
libasound.so.2 => /lib/aarch64-linux-gnu/libasound.so.2
libpthread.so.0 => /lib/aarch64-linux-gnu/libpthread.so.0
libstdc++.so.6 => /lib/aarch64-linux-gnu/libstdc++.so.6
libm.so.6 => /lib/aarch64-linux-gnu/libm.so.6
libgcc_s.so.1 => /lib/aarch64-linux-gnu/libgcc_s.so.1
libc.so.6 => /lib/aarch64-linux-gnu/libc.so.6
```

## Testing the Build

```bash
# Run with default config
./explicitly-daemon --help

# Run with test config
./explicitly-daemon --config ../config.yaml.example
```

## Next Steps

See `INSTALL.md` for deployment instructions.

## Build Times

Approximate build times on different platforms:

| Platform | Whisper.cpp | Explicitly | Total |
|----------|-------------|------------|-------|
| Orange Pi Zero 3 | 30-45 min | 5-10 min | ~40-55 min |
| Desktop (x86-64) | 2-3 min | 30-60 sec | ~3-4 min |
| Cross-compile | 2-3 min | 30-60 sec | ~3-4 min |

**Recommendation**: For development, cross-compile on desktop. For production deployment, native build on Orange Pi ensures full compatibility.
