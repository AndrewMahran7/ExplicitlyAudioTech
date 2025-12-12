#!/bin/bash

# Build whisper.cpp for ARM64
# Optimized for Orange Pi Zero 3 (Cortex-A53)

set -e

echo "==========================================="
echo "  Building whisper.cpp for ARM64"
echo "==========================================="
echo

# Check if already cloned
if [ ! -d "whisper.cpp" ]; then
    echo "[1/3] Cloning whisper.cpp repository..."
    git clone https://github.com/ggerganov/whisper.cpp
    cd whisper.cpp
else
    echo "[1/3] whisper.cpp already cloned, updating..."
    cd whisper.cpp
    git pull
fi

echo "[2/3] Building with ARM optimizations..."
make clean
make -j4 \
    CFLAGS="-march=armv8-a -mtune=cortex-a53 -O3 -DNDEBUG" \
    CXXFLAGS="-march=armv8-a -mtune=cortex-a53 -O3 -DNDEBUG"

echo "[3/3] Verifying build..."
if [ -f "libwhisper.a" ]; then
    echo "  ✓ libwhisper.a created successfully"
    ls -lh libwhisper.a
else
    echo "  ✗ Build failed: libwhisper.a not found"
    exit 1
fi

echo
echo "==========================================="
echo "  whisper.cpp build complete!"
echo "==========================================="
echo
echo "Static library: $(pwd)/libwhisper.a"
echo
echo "Next: Build Explicitly with ./scripts/build_explicitly.sh"
echo
