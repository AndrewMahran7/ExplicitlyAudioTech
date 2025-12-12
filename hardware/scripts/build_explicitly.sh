#!/bin/bash

# Build Explicitly for Orange Pi Zero 3

set -e

echo "==========================================="
echo "  Building Explicitly Hardware Edition"
echo "==========================================="
echo

# Check if whisper.cpp is built
WHISPER_DIR="../whisper.cpp"
if [ ! -f "$WHISPER_DIR/libwhisper.a" ]; then
    echo "ERROR: whisper.cpp not built yet"
    echo "Run ./scripts/build_whisper.sh first"
    exit 1
fi

echo "[1/5] Copying shared source files from desktop..."
mkdir -p src

# Copy only the files we need (header-only or minimal dependencies)
FILES_TO_COPY=(
    "VocalFilter.cpp"
    "VocalFilter.h"
    "TimestampRefiner.cpp"
    "TimestampRefiner.h"
    "LyricsAlignment.cpp"
    "LyricsAlignment.h"
    "Types.h"
    "CircularBuffer.h"
    "LockFreeQueue.h"
)

for file in "${FILES_TO_COPY[@]}"; do
    if [ -f "../desktop/Source/$file" ]; then
        cp "../desktop/Source/$file" src/
        echo "  ✓ Copied $file"
    else
        echo "  ⚠ Warning: $file not found in desktop/Source/"
    fi
done

echo "[2/5] Creating ProfanityFilter.h (adapted for std::)..."
# Create a modified version without JUCE dependencies
cat > src/ProfanityFilter.h <<'EOF'
#pragma once
#include <string>
#include <vector>
#include <algorithm>
#include <fstream>
#include <sstream>

class ProfanityFilter {
public:
    bool loadLexicon(const std::string& filePath) {
        std::ifstream file(filePath);
        if (!file.is_open()) return false;
        
        std::string line;
        while (std::getline(file, line)) {
            // Trim whitespace
            line.erase(0, line.find_first_not_of(" \t\n\r"));
            line.erase(line.find_last_not_of(" \t\n\r") + 1);
            
            // Skip empty lines and comments
            if (line.empty() || line[0] == '#') continue;
            
            // Convert to lowercase
            std::transform(line.begin(), line.end(), line.begin(), ::tolower);
            
            lexicon.push_back(line);
        }
        return !lexicon.empty();
    }
    
    bool containsProfanity(const std::string& text) const {
        std::string lowerText = text;
        std::transform(lowerText.begin(), lowerText.end(), lowerText.begin(), ::tolower);
        
        for (const auto& word : lexicon) {
            if (lowerText.find(word) != std::string::npos) {
                return true;
            }
        }
        return false;
    }
    
private:
    std::vector<std::string> lexicon;
};
EOF

echo "[3/5] Downloading cpp-httplib..."
if [ ! -f "src/httplib.h" ]; then
    wget -O src/httplib.h https://raw.githubusercontent.com/yhirose/cpp-httplib/master/httplib.h
    echo "  ✓ Downloaded httplib.h"
else
    echo "  ✓ httplib.h already exists"
fi

echo "[4/5] Configuring CMake..."
mkdir -p build
cd build

cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DWHISPER_DIR="$(realpath ../../whisper.cpp)"

echo "[5/5] Building..."
make -j4

echo
if [ -f "explicitly-daemon" ]; then
    echo "==========================================="
    echo "  Build successful!"
    echo "==========================================="
    echo
    echo "Binary: $(pwd)/explicitly-daemon"
    echo "Size: $(ls -lh explicitly-daemon | awk '{print $5}')"
    echo
    echo "Test with: ./explicitly-daemon --help"
    echo "Install with: sudo make install"
    echo
else
    echo "ERROR: Build failed - explicitly-daemon not created"
    exit 1
fi
