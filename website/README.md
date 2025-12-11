# Explicitly

A Python-based profanity filtering tool for audio files using AI-powered speech recognition and stem separation.

## 🌐 New! Web Interface

**Easy-to-use web interface now available!** Upload files, select models, and download clean audio through your browser.

```bash
python -m explicitly web
# Then open http://localhost:5000
```

See [WEB_README.md](WEB_README.md) for details or [SETUP_WEB.md](SETUP_WEB.md) for quick setup.

## Overview

Explicitly automatically detects and censors profane language in audio files by:

1. **Stem Separation**: Uses Demucs to separate vocals from instrumentals
2. **Speech Recognition**: Transcribes vocals using Whisper with word-level timestamps
3. **Profanity Detection**: Matches transcribed words against configurable lexicons
4. **Audio Censoring**: Mutes or bleeps profane segments with smooth fading
5. **Remixing**: Recombines cleaned vocals with instrumentals
6. **Reporting**: Generates detailed JSON reports of all detected profanity

## Requirements

### System Dependencies

- **Python 3.10+**
- **FFmpeg**: Required for high-quality audio processing and format conversion
- **CUDA** (optional): For GPU acceleration of AI models

### Python Dependencies

All Python dependencies are listed in `requirements.txt` and will be installed automatically:

- **PyTorch ecosystem**: `torch`, `torchvision`, `torchaudio`
- **AI Models**: `demucs` (stem separation), `faster-whisper` + `whisperx` (speech recognition)
- **Audio Processing**: `librosa`, `soundfile`, `pydub`, `scipy`, `numpy`
- **CLI & Utilities**: `typer`, `PyYAML`, `regex`, `unidecode`, `wordfreq`

## Installation

### 1. Create Python Environment

```bash
# Using conda (recommended)
conda create -n explicitly python=3.10
conda activate explicitly

# Or using venv
python -m venv explicitly
# Windows:
explicitly\Scripts\activate
# Linux/Mac:
source explicitly/bin/activate
```

### 2. Install FFmpeg

**Windows (conda):**
```bash
conda install -c conda-forge ffmpeg
```

**Windows (manual):**
1. Download FFmpeg from https://ffmpeg.org/download.html
2. Extract and add to PATH

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Note for CUDA users:** Install PyTorch with CUDA support first:
```bash
# For CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Then install remaining dependencies
pip install -r requirements.txt
```

### 4. Verify Installation

```bash
python -m explicitly.cli version
ffmpeg -version
```

## Usage

### Basic Usage

```bash
# Clean a single audio file
python -m explicitly.cli clean song.mp3

# Specify output directory
python -m explicitly.cli clean song.mp3 --output /path/to/output

# Use GPU acceleration
python -m explicitly.cli clean song.mp3 --device cuda

# Use bleep censoring instead of muting
python -m explicitly.cli clean song.mp3 --method bleep
```

### Advanced Usage

```bash
# Analyze without creating output (dry run)
python -m explicitly.cli analyze song.mp3

# Keep intermediate files for debugging
python -m explicitly.cli clean song.mp3 --keep-stems

# Use custom configuration
python -m explicitly.cli clean song.mp3 --config my_config.yaml

# Use custom profanity lexicon
python -m explicitly.cli clean song.mp3 --lexicon my_words.txt
```

### Expected Input/Output

**Input:**
- Audio files in common formats: MP3, WAV, FLAC, M4A, etc.
- Place input files in `data/input/` directory

**Output:**
- `song.clean.mp3`: Censored audio file
- `song.report.json`: Detailed processing report
- Files saved to `data/output/` by default

## Configuration

### Settings File: `config/settings.yaml`

```yaml
# Audio processing settings
fade_ms: 50                    # Fade duration for smooth transitions
pre_margin_ms: 100             # Extra silence before profane words
post_margin_ms: 100            # Extra silence after profane words

# AI model settings
demucs_model: "htdemucs"       # Stem separation model
whisper_model: "base.en"       # Speech recognition model
whisper_device: "auto"         # Device for processing

# Profanity detection
profanity_threshold: 0.8       # Confidence threshold
normalize_text: true           # Handle variations (sh*t → shit)
case_sensitive: false          # Case sensitivity

# Output settings
output_format: "mp3"           # Output format
output_bitrate: "320k"         # MP3 bitrate
```

### Profanity Lexicon: `lexicons/profanity_en.txt`

Simple text file with one word per line:
```
shit
fuck
damn
...
```

Supports:
- Comments (lines starting with `#`)
- Custom word lists for different use cases
- Automatic normalization of variations (sh*t, f**k, etc.)

## Project Structure

```
explicitly/
├── data/
│   ├── input/              # Input MP3/audio files
│   ├── stems/              # Separated vocal/instrumental stems
│   ├── work/               # Intermediate processing files
│   └── output/             # Final clean audio + JSON reports
├── config/
│   └── settings.yaml       # Configuration settings
├── lexicons/
│   └── profanity_en.txt    # Profanity word list (English)
├── explicitly/             # Source code package
│   ├── __init__.py
│   ├── separate.py         # Demucs stem separation
│   ├── transcribe_align.py # Whisper speech recognition
│   ├── detect.py           # Profanity detection logic
│   ├── censor.py           # Audio censoring (mute/bleep)
│   ├── remix.py            # Audio remixing
│   ├── utils_audio.py      # Audio processing utilities
│   └── cli.py              # Command-line interface
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## API Reference

### Core Modules

#### `explicitly.separate`
```python
from explicitly.separate import separate_audio

# Separate vocals and instrumentals
stems = separate_audio(
    input_path="song.mp3",
    output_dir="stems/",
    model_name="htdemucs",
    device="cuda"
)
# Returns: {"vocals": "path/to/vocals.wav", "instrumental": "path/to/other.wav"}
```

#### `explicitly.transcribe_align`
```python
from explicitly.transcribe_align import transcribe_audio

# Get word-level transcription with timestamps
words = transcribe_audio(
    audio_path="vocals.wav",
    model="base.en",
    device="cuda"
)
# Returns: [WordSegment(start=1.2, end=1.8, word="hello", confidence=0.95), ...]
```

#### `explicitly.detect`
```python
from explicitly.detect import detect_profanity

# Detect profane words
profane_words = detect_profanity(
    word_segments=words,
    lexicon_path="lexicons/profanity_en.txt"
)
# Returns: [WordSegment(...), ...] # Filtered to profane words only
```

#### `explicitly.censor`
```python
from explicitly.censor import censor_audio

# Censor profanity in audio
stats = censor_audio(
    audio_path="vocals.wav",
    profane_segments=profane_words,
    output_path="vocals_clean.wav",
    censor_method="mute"  # or "bleep"
)
# Returns: {"total_segments": 3, "censored_duration_ms": 1500, ...}
```

#### `explicitly.remix`
```python
from explicitly.remix import remix_audio

# Recombine clean vocals with instrumentals
stats = remix_audio(
    vocals_path="vocals_clean.wav",
    instrumental_path="instrumental.wav",
    output_path="song_clean.mp3"
)
```

## Report Format

The JSON report contains comprehensive information:

```json
{
  "metadata": {
    "original_file": "song.mp3",
    "censored_file": "song.clean.mp3",
    "processing_timestamp": "2025-10-01T10:30:00",
    "censor_method": "mute"
  },
  "audio_info": {
    "original_duration_seconds": 240.5,
    "total_censored_ms": 3200,
    "censorship_percentage": 1.33
  },
  "profanity_detection": {
    "total_profane_words": 5,
    "unique_words": 3,
    "segments": [
      {
        "word": "damn",
        "start": 45.2,
        "end": 45.8,
        "confidence": 0.94
      }
    ]
  }
}
```

## Limitations & Notes

- **English Only**: Currently supports English language detection
- **Offline Processing**: All processing is done locally (no cloud APIs)
- **Not Real-time**: Designed for batch processing, not live audio
- **Accuracy Dependent**: Quality depends on audio clarity and AI model performance
- **Resource Intensive**: Requires significant CPU/GPU for large files

## Performance Tips

1. **Use GPU**: Add `--device cuda` for 3-5x speedup on compatible hardware
2. **Model Selection**: Use smaller Whisper models (`tiny`, `base`) for faster processing
3. **Batch Processing**: Process multiple files sequentially rather than parallel
4. **Audio Quality**: Higher quality input audio improves transcription accuracy

## Troubleshooting

### Common Issues

**FFmpeg not found:**
```bash
# Verify FFmpeg installation
ffmpeg -version

# If missing, install via conda:
conda install -c conda-forge ffmpeg
```

**CUDA out of memory:**
```bash
# Use smaller models or CPU processing
python -m explicitly.cli clean song.mp3 --device cpu
```

**Import errors:**
```bash
# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

**Low transcription accuracy:**
- Try larger Whisper model (`small.en`, `medium.en`)
- Ensure clean audio input (minimal background noise)
- Check audio format compatibility

### Getting Help

1. Check this README for common solutions
2. Verify all dependencies are installed correctly
3. Test with a simple, short audio file first
4. Check the generated JSON reports for debugging information

## License

This project is intended for educational and research purposes. Please ensure compliance with local laws and regulations when processing audio content.

## Contributing

This is an MVP implementation. Areas for improvement:

- Multi-language support
- Real-time processing capabilities
- Advanced censoring methods (voice synthesis replacement)
- Web interface
- Batch processing optimization
- Additional audio format support
