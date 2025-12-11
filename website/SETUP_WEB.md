# Quick Setup Guide for Web Interface

## Installation

1. **Install Python dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

2. **Verify installation**:
   ```powershell
   python -m explicitly version
   ```

## Running the Web Interface

### Method 1: Using the CLI (Recommended)
```powershell
python -m explicitly web
```

### Method 2: Using the run script
```powershell
python run_web.py
```

### Method 3: Custom port
```powershell
python -m explicitly web --port 8080
```

## First Time Setup

If you get an error about Flask not being installed:
```powershell
pip install flask werkzeug
```

## Accessing the Interface

Once the server starts, open your browser and go to:
```
http://localhost:5000
```

## Using the Interface

1. **Upload File**: Click to browse or drag & drop your audio file
2. **Select Model**:
   - **Speed**: Fastest (tiny.en) - Great for testing
   - **Balanced**: Medium speed (base.en) - Recommended for most files
   - **Accuracy**: Slowest (large-v2) - Best quality
3. **Choose Method**:
   - **Mute**: Silent gaps
   - **Bleep**: Beep sound
   - **Reverse**: Backward audio
4. **Select Device**:
   - **Auto**: Automatically choose GPU or CPU
   - **GPU (CUDA)**: Faster with NVIDIA GPU
   - **CPU**: Compatible with all systems
5. **Click "Start Processing"** and wait
6. **Download** your clean audio and report when complete

## GPU Acceleration (Optional)

For faster processing with NVIDIA GPU:

1. Check if you have CUDA:
   ```powershell
   nvidia-smi
   ```

2. Install CUDA-enabled PyTorch:
   ```powershell
   pip uninstall torch torchvision torchaudio
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```

## Troubleshooting

### Port already in use
```powershell
python -m explicitly web --port 8080
```

### Processing is slow
- Use GPU acceleration if available
- Select "Speed" model
- Process shorter files

### Upload fails
- Check file size (max 100MB)
- Verify file format (MP3, WAV, FLAC, OGG, M4A, AAC)

## Stopping the Server

Press `Ctrl+C` in the terminal to stop the server.
