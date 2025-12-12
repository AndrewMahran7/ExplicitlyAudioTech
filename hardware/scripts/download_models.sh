#!/bin/bash

# Download Whisper models to Orange Pi

set -e

MODEL_DIR="/usr/share/explicitly/models"
TEMP_DIR="/tmp/whisper-models"

echo "==========================================="
echo "  Downloading Whisper Models"
echo "==========================================="
echo

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "This script requires sudo privileges"
    echo "Run with: sudo ./scripts/download_models.sh"
    exit 1
fi

# Create directories
mkdir -p "$MODEL_DIR"
mkdir -p "$TEMP_DIR"

# Model options
echo "Available models:"
echo "  1. tiny.en   (75 MB)  - Fastest, recommended for 1GB Orange Pi"
echo "  2. base.en   (142 MB) - Better accuracy"
echo "  3. small.en  (487 MB) - Best accuracy, requires 2GB RAM"
echo

read -p "Select model [1-3] (default: 1): " choice
choice=${choice:-1}

case $choice in
    1)
        MODEL="ggml-tiny.en.bin"
        SIZE="75 MB"
        ;;
    2)
        MODEL="ggml-base.en.bin"
        SIZE="142 MB"
        ;;
    3)
        MODEL="ggml-small.en.bin"
        SIZE="487 MB"
        ;;
    *)
        echo "Invalid choice, using tiny.en"
        MODEL="ggml-tiny.en.bin"
        SIZE="75 MB"
        ;;
esac

echo
echo "Downloading $MODEL ($SIZE)..."
echo "This may take a few minutes..."
echo

cd "$TEMP_DIR"

# Download with progress
wget --progress=bar:force \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL"

# Verify download
if [ ! -f "$MODEL" ]; then
    echo "ERROR: Download failed"
    exit 1
fi

# Move to final location
mv "$MODEL" "$MODEL_DIR/"
chown explicitly:audio "$MODEL_DIR/$MODEL"

echo
echo "==========================================="
echo "  Download complete!"
echo "==========================================="
echo
echo "Model saved to: $MODEL_DIR/$MODEL"
echo "Size: $(ls -lh $MODEL_DIR/$MODEL | awk '{print $5}')"
echo
echo "Update your config.yaml to use this model:"
echo "  sudo nano /etc/explicitly/config.yaml"
echo
echo "  processing:"
echo "    model_path: \"$MODEL_DIR/$MODEL\""
echo

# Cleanup
rm -rf "$TEMP_DIR"
