"""
Audio utility functions for processing, resampling, and format conversion.

This module provides a comprehensive set of audio processing utilities that
support the Explicitly profanity filtering pipeline. It handles all the
low-level audio operations needed across different stages:

Core functionality areas:
1. File I/O: Loading and saving various audio formats (WAV, MP3, FLAC)
2. Format conversion: Converting between different audio formats and sample rates
3. Audio processing: Applying fades, creating silence, muting segments
4. Quality operations: Resampling, normalization, and quality preservation

Key design principles:
- Robust error handling with informative error messages
- Format flexibility supporting common audio types
- Quality preservation throughout processing pipeline
- Performance optimization for large audio files
- Cross-platform compatibility

The utilities abstract away the complexity of different audio libraries
(librosa, soundfile, pydub) and provide a consistent interface for
audio operations throughout the Explicitly codebase.

Technical considerations:
- All audio is processed as float32 arrays for quality and compatibility
- Sample rates are handled consistently across different operations
- Memory-efficient processing for large audio files
- Graceful handling of edge cases (short files, format issues)
"""

# Standard library imports
import os                           # File system operations
import tempfile                     # Temporary file handling
from pathlib import Path           # Modern path operations
from typing import Tuple, Optional, Union, Dict, Any  # Type hints for clarity

# Audio processing libraries
import librosa                     # Advanced audio analysis and processing
import numpy as np                 # Numerical array operations
import soundfile as sf            # High-quality audio file I/O
from pydub import AudioSegment    # Format conversion and basic operations
from scipy import signal         # Signal processing utilities


def load_audio(
    filepath: Union[str, Path],     # Audio file to load
    sr: Optional[int] = None,       # Target sample rate (None = preserve original)
    mono: bool = True               # Convert to mono (True) or preserve channels
) -> Tuple[np.ndarray, int]:
    """
    Load audio file with robust error handling and format support.
    
    This is the primary audio loading function used throughout Explicitly.
    It provides a consistent interface for loading various audio formats
    while handling common issues and edge cases gracefully.
    
    Supported formats: WAV, MP3, FLAC, M4A, OGG, and more (via librosa)
    
    Key features:
    - Automatic format detection and loading
    - Optional sample rate conversion during load (efficient)
    - Mono/stereo handling based on processing needs
    - Consistent float32 output format for quality
    - Comprehensive error handling with helpful messages
    
    Audio is returned as float32 arrays with values in [-1.0, 1.0] range,
    which is the standard for digital audio processing.
    
    Args:
        filepath: Path to the audio file to load (supports Path objects and strings)
        sr: Target sample rate in Hz (e.g., 22050, 44100, 48000)
               - None: Keep original sample rate
               - int: Resample to this rate during loading (more efficient than post-load)
        mono: Channel handling preference:
             - True: Convert to mono (mix all channels to single channel)
             - False: Preserve original channel configuration (mono/stereo)
        
    Returns:
        Tuple containing:
        - audio_data (np.ndarray): Audio samples as float32 array
          Shape: (samples,) for mono or (channels, samples) for multi-channel
        - sample_rate (int): Final sample rate in Hz
        
    Raises:
        RuntimeError: If file loading fails (file not found, corrupted, unsupported format)
        
    Example:
        >>> audio, sr = load_audio("song.mp3", sr=22050, mono=True)
        >>> print(f"Loaded {len(audio)} samples at {sr}Hz")
    """
    try:
        audio, sample_rate = librosa.load(
            str(filepath), sr=sr, mono=mono, dtype=np.float32
        )
        return audio, sample_rate
    except Exception as e:
        raise RuntimeError(f"Failed to load audio file {filepath}: {str(e)}")


def save_audio(
    audio: np.ndarray, 
    filepath: Union[str, Path], 
    sr: int, 
    format: str = "wav"
) -> None:
    """
    Save audio data to file.
    
    Args:
        audio: Audio data array
        filepath: Output file path
        sr: Sample rate
        format: Audio format (wav, flac, etc.)
    """
    try:
        sf.write(str(filepath), audio, sr, format=format.upper())
    except Exception as e:
        raise RuntimeError(f"Failed to save audio to {filepath}: {str(e)}")


def resample_audio(
    audio: np.ndarray, 
    orig_sr: int, 
    target_sr: int
) -> np.ndarray:
    """
    Resample audio to target sample rate.
    
    Args:
        audio: Input audio array
        orig_sr: Original sample rate
        target_sr: Target sample rate
        
    Returns:
        Resampled audio array
    """
    if orig_sr == target_sr:
        return audio
        
    return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)


def apply_fade(
    audio: np.ndarray, 
    sr: int, 
    fade_ms: int = 50, 
    fade_type: str = "linear"
) -> np.ndarray:
    """
    Apply fade in/out to audio segment.
    
    Args:
        audio: Audio array
        sr: Sample rate
        fade_ms: Fade duration in milliseconds
        fade_type: Type of fade (linear, exponential)
        
    Returns:
        Audio with fade applied
    """
    fade_samples = int(fade_ms * sr / 1000)
    fade_samples = min(fade_samples, len(audio) // 2)
    
    if fade_samples <= 0:
        return audio
        
    result = audio.copy()
    
    # Fade in
    if fade_type == "linear":
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
    else:  # exponential
        fade_in = np.power(np.linspace(0, 1, fade_samples), 2)
        fade_out = np.power(np.linspace(1, 0, fade_samples), 2)
    
    result[:fade_samples] *= fade_in
    result[-fade_samples:] *= fade_out
    
    return result


def create_silence(duration_ms: int, sr: int) -> np.ndarray:
    """
    Create silence of specified duration.
    
    Args:
        duration_ms: Duration in milliseconds
        sr: Sample rate
        
    Returns:
        Silence audio array
    """
    samples = int(duration_ms * sr / 1000)
    return np.zeros(samples, dtype=np.float32)


def mute_segment(
    audio: np.ndarray,              # Source audio to modify
    sr: int,                        # Sample rate for timing calculations
    start_ms: float,                # Start of segment to mute (milliseconds)
    end_ms: float,                  # End of segment to mute (milliseconds) 
    fade_ms: int = 50,              # Fade duration for smooth transitions
    pre_margin_ms: int = 0,         # Extra silence before the segment
    post_margin_ms: int = 0         # Extra silence after the segment
) -> np.ndarray:
    """
    Intelligently mute an audio segment with professional-quality transitions.
    
    This function is crucial for the censoring module - it removes profane
    audio content while maintaining natural-sounding results. The key is
    using smooth fades rather than harsh cuts to avoid audio artifacts.
    
    The muting process:
    1. Calculate exact sample positions from timing
    2. Add optional margins for complete word removal
    3. Apply fade out before the muted section
    4. Replace target audio with silence
    5. Apply fade in after the muted section
    
    This creates seamless transitions that sound natural rather than
    obviously edited, which is essential for professional results.
    
    Technical considerations:
    - Prevents clicks and pops through gradual fades
    - Handles boundary cases (start/end of file)
    - Preserves audio before and after the target segment
    - Uses precise sample-level timing for accuracy
    
    Args:
        audio: Input audio array to be modified (float32 format)
        sr: Sample rate in Hz (needed for millisecond to sample conversion)
        start_ms: Start time of segment to mute in milliseconds
        end_ms: End time of segment to mute in milliseconds
        fade_ms: Duration of fade transitions in milliseconds (prevents clicks)
        pre_margin_ms: Extra time to mute before start_ms (ensures complete removal)
        post_margin_ms: Extra time to mute after end_ms (ensures complete removal)
        
    Returns:
        Modified audio array with the specified segment muted and smooth transitions
        
    Note:
        The original audio array is not modified - a copy is returned.
        Margins are useful for fast speech where word boundaries might be imprecise.
    """
    # Convert to samples
    start_sample = max(0, int((start_ms - pre_margin_ms) * sr / 1000))
    end_sample = min(len(audio), int((end_ms + post_margin_ms) * sr / 1000))
    
    if start_sample >= end_sample:
        return audio
        
    result = audio.copy()
    
    # Create muted segment with fades
    segment_length = end_sample - start_sample
    muted_segment = create_silence(segment_length * 1000 / sr, sr)
    
    # Apply fade to boundaries if there's enough space
    fade_samples = min(int(fade_ms * sr / 1000), segment_length // 4)
    
    if fade_samples > 0:
        # Fade out before mute
        if start_sample - fade_samples >= 0:
            fade_out = apply_fade(
                result[start_sample - fade_samples:start_sample], 
                sr, fade_ms
            )
            result[start_sample - fade_samples:start_sample] = fade_out
            
        # Fade in after mute
        if end_sample + fade_samples <= len(audio):
            fade_in = apply_fade(
                result[end_sample:end_sample + fade_samples], 
                sr, fade_ms
            )
            result[end_sample:end_sample + fade_samples] = fade_in
    
    # Apply the mute
    result[start_sample:end_sample] = 0
    
    return result


def convert_mp3_to_wav(mp3_path: Union[str, Path]) -> str:
    """
    Convert MP3 file to WAV format for processing.
    
    Args:
        mp3_path: Path to MP3 file
        
    Returns:
        Path to converted WAV file
    """
    try:
        audio = AudioSegment.from_mp3(str(mp3_path))
        wav_path = str(mp3_path).replace('.mp3', '_temp.wav')
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception as e:
        raise RuntimeError(f"Failed to convert MP3 to WAV: {str(e)}")


def convert_wav_to_mp3(
    wav_path: Union[str, Path], 
    mp3_path: Union[str, Path], 
    bitrate: str = "320k"
) -> None:
    """
    Convert WAV file to MP3 format.
    
    Args:
        wav_path: Path to input WAV file
        mp3_path: Path to output MP3 file
        bitrate: MP3 bitrate (e.g., "320k")
    """
    try:
        audio = AudioSegment.from_wav(str(wav_path))
        audio.export(str(mp3_path), format="mp3", bitrate=bitrate)
    except Exception as e:
        raise RuntimeError(f"Failed to convert WAV to MP3: {str(e)}")


def get_audio_duration(filepath: Union[str, Path]) -> float:
    """
    Get duration of audio file in seconds.
    
    Args:
        filepath: Path to audio file
        
    Returns:
        Duration in seconds
    """
    try:
        duration = librosa.get_duration(path=str(filepath))
        return duration
    except Exception as e:
        raise RuntimeError(f"Failed to get audio duration: {str(e)}")


def analyze_quality_difference(original_path: Union[str, Path], processed_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Analyze quality differences between original and processed audio.
    
    Provides detailed metrics to help understand quality changes through
    the processing pipeline. Useful for optimization and quality assurance.
    
    Args:
        original_path: Path to original audio file
        processed_path: Path to processed audio file
        
    Returns:
        Dictionary with quality analysis metrics
    """
    try:
        # Load both files at original sample rates
        orig, orig_sr = load_audio(original_path, sr=None, mono=False)
        proc, proc_sr = load_audio(processed_path, sr=None, mono=False)
        
        # Ensure mono for analysis
        if len(orig.shape) > 1:
            orig = np.mean(orig, axis=0)
        if len(proc.shape) > 1:
            proc = np.mean(proc, axis=0)
            
        # Align lengths for comparison
        min_len = min(len(orig), len(proc))
        orig = orig[:min_len]
        proc = proc[:min_len]
        
        # Resample processed to match original if needed
        if orig_sr != proc_sr:
            proc = resample_audio(proc, proc_sr, orig_sr)
            
        # Calculate quality metrics
        mse = np.mean((orig - proc) ** 2)
        
        if mse > 0:
            snr = 10 * np.log10(np.mean(orig ** 2) / mse)
        else:
            snr = float('inf')
            
        # Dynamic range analysis
        orig_range = np.max(orig) - np.min(orig)
        proc_range = np.max(proc) - np.min(proc)
        range_preservation = (proc_range / orig_range) * 100 if orig_range > 0 else 100
        
        # Frequency content comparison
        orig_fft = np.abs(np.fft.rfft(orig))
        proc_fft = np.abs(np.fft.rfft(proc))
        freq_correlation = np.corrcoef(orig_fft, proc_fft)[0, 1]
        
        # Quality assessment
        if snr > 25:
            quality_rating = "Excellent"
        elif snr > 15:
            quality_rating = "Good"
        elif snr > 10:
            quality_rating = "Fair"
        else:
            quality_rating = "Poor"
            
        return {
            "snr_db": float(snr),
            "quality_rating": quality_rating,
            "dynamic_range_preservation_percent": float(range_preservation),
            "frequency_correlation": float(freq_correlation),
            "original_duration_s": len(orig) / orig_sr,
            "processed_duration_s": len(proc) / proc_sr,
            "sample_rate_match": orig_sr == proc_sr
        }
        
    except Exception as e:
        raise RuntimeError(f"Quality analysis failed: {str(e)}")
