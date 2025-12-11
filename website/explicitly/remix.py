"""
Audio remixing functionality to recombine processed vocals with instrumentals.

This module handles the final stage of the Explicitly pipeline: combining the
censored vocals with the original instrumental tracks to create the final
clean audio output. This is essential because:

1. Stem separation isolated vocals for profanity detection and censoring
2. We now need to remix the censored vocals with untouched instrumentals
3. This preserves the musical backing while removing offensive speech
4. The result sounds like the original song but with profanity removed

Key challenges in audio remixing:
- Sample rate matching: Vocals and instrumentals must have same sample rate
- Length alignment: Audio files must be exactly the same duration
- Channel matching: Mono/stereo format consistency across tracks
- Gain balancing: Relative volume levels between vocals and instruments
- Quality preservation: Maintaining audio fidelity throughout the process
- Format flexibility: Supporting multiple output formats (MP3, WAV, FLAC)

Remixing approaches:
1. FFmpeg: Professional-grade audio processing (preferred when available)
2. NumPy: Python-based mixing (fallback when FFmpeg unavailable)

The remixing process:
1. Load censored vocals and original instrumentals
2. Align sample rates, channels, and durations
3. Apply gain adjustments for proper balance
4. Mix the audio streams together
5. Normalize to prevent clipping
6. Output in desired format (MP3, WAV, FLAC)

This creates professional-quality results that maintain the original's
musical integrity while ensuring clean content.
"""

# Standard library imports
import os                            # File operations and cleanup
import subprocess                    # FFmpeg process execution
from pathlib import Path            # Modern path handling
from typing import Union, Optional, Dict, Any  # Type hints

# Core processing libraries
import numpy as np                  # Audio array manipulation and mixing

# Internal audio utilities
from .utils_audio import load_audio, save_audio, convert_wav_to_mp3


class AudioRemixer:
    """
    Handles recombining separated audio stems into final output.
    """
    
    def __init__(self, output_format: str = "mp3", output_bitrate: str = "320k"):
        """
        Initialize the audio remixer.
        
        Args:
            output_format: Output format (mp3, wav, flac)
            output_bitrate: Bitrate for compressed formats
        """
        self.output_format = output_format.lower()
        self.output_bitrate = output_bitrate
    
    def _check_ffmpeg(self) -> bool:
        """
        Check if FFmpeg is available.
        
        Returns:
            True if FFmpeg is available
        """
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
    
    def remix_audio(
        self,
        vocals_path: Union[str, Path],
        instrumental_path: Union[str, Path],
        output_path: Union[str, Path],
        vocals_gain: float = 1.0,
        instrumental_gain: float = 1.0,
        use_ffmpeg: bool = True
    ) -> Dict[str, Any]:
        """
        Remix vocals and instrumental tracks into final output.
        
        Args:
            vocals_path: Path to processed vocals
            instrumental_path: Path to instrumental track
            output_path: Path to save final output
            vocals_gain: Gain adjustment for vocals (1.0 = no change)
            instrumental_gain: Gain adjustment for instrumental
            use_ffmpeg: Use FFmpeg for high-quality output
            
        Returns:
            Dictionary with remix statistics
        """
        try:
            print(f"Remixing audio: vocals={vocals_path}, instrumental={instrumental_path}")
            
            if use_ffmpeg and self._check_ffmpeg():
                return self._remix_with_ffmpeg(
                    vocals_path, instrumental_path, output_path,
                    vocals_gain, instrumental_gain
                )
            else:
                return self._remix_with_numpy(
                    vocals_path, instrumental_path, output_path,
                    vocals_gain, instrumental_gain
                )
                
        except Exception as e:
            raise RuntimeError(f"Audio remixing failed: {str(e)}")
    
    def _remix_with_ffmpeg(
        self,
        vocals_path: Union[str, Path],
        instrumental_path: Union[str, Path],
        output_path: Union[str, Path],
        vocals_gain: float,
        instrumental_gain: float
    ) -> Dict[str, Any]:
        """
        Remix using FFmpeg for high-quality output.
        
        Args:
            vocals_path: Path to vocals
            instrumental_path: Path to instrumental
            output_path: Output path
            vocals_gain: Vocals gain
            instrumental_gain: Instrumental gain
            
        Returns:
            Remix statistics
        """
        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", str(vocals_path),
            "-i", str(instrumental_path),
            "-filter_complex",
            f"[0:a]volume={vocals_gain}[vocals];[1:a]volume={instrumental_gain}[instr];[vocals][instr]amix=inputs=2[out]",
            "-map", "[out]"
        ]
        
        # Add format-specific options with quality optimization
        if self.output_format == "mp3":
            cmd.extend([
                "-c:a", "libmp3lame", 
                "-b:a", self.output_bitrate,
                "-q:a", "0",  # Highest quality VBR
                "-joint_stereo", "0"  # Preserve stereo imaging
            ])
        elif self.output_format == "wav":
            # Use 32-bit float for maximum quality (let FFmpeg auto-detect sample rate)
            cmd.extend(["-c:a", "pcm_f32le"])
        elif self.output_format == "flac":
            cmd.extend([
                "-c:a", "flac",
                "-compression_level", "8",  # Maximum compression efficiency
                "-exact_rice_parameters", "1"  # Better quality
            ])
        
        cmd.append(str(output_path))
        
        try:
            print(f"Running FFmpeg: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                # Check if it's an encoder issue and fall back to NumPy
                if "Unknown encoder" in result.stderr or "Encoder not found" in result.stderr:
                    print(f"FFmpeg encoder not available, falling back to NumPy mixing...")
                    return self._remix_with_numpy(
                        vocals_path, instrumental_path, output_path,
                        vocals_gain, instrumental_gain
                    )
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")
            
            print(f"Remixed audio saved: {output_path}")
            
            return {
                "method": "ffmpeg",
                "vocals_gain": vocals_gain,
                "instrumental_gain": instrumental_gain,
                "output_format": self.output_format,
                "output_bitrate": self.output_bitrate if self.output_format == "mp3" else None
            }
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("FFmpeg process timed out")
        except Exception as e:
            raise RuntimeError(f"FFmpeg remixing failed: {str(e)}")
    
    def _remix_with_numpy(
        self,
        vocals_path: Union[str, Path],
        instrumental_path: Union[str, Path],
        output_path: Union[str, Path],
        vocals_gain: float,
        instrumental_gain: float
    ) -> Dict[str, Any]:
        """
        Remix using NumPy/SciPy (fallback method).
        
        Args:
            vocals_path: Path to vocals
            instrumental_path: Path to instrumental
            output_path: Output path
            vocals_gain: Vocals gain
            instrumental_gain: Instrumental gain
            
        Returns:
            Remix statistics
        """
        # Load both audio files
        vocals, vocals_sr = load_audio(vocals_path, sr=None, mono=False)
        instrumental, instr_sr = load_audio(instrumental_path, sr=None, mono=False)
        
        # Ensure same sample rate
        if vocals_sr != instr_sr:
            from .utils_audio import resample_audio
            target_sr = max(vocals_sr, instr_sr)
            
            if vocals_sr != target_sr:
                if len(vocals.shape) == 2:
                    vocals = np.array([
                        resample_audio(vocals[i], vocals_sr, target_sr)
                        for i in range(vocals.shape[0])
                    ])
                else:
                    vocals = resample_audio(vocals, vocals_sr, target_sr)
                vocals_sr = target_sr
            
            if instr_sr != target_sr:
                if len(instrumental.shape) == 2:
                    instrumental = np.array([
                        resample_audio(instrumental[i], instr_sr, target_sr)
                        for i in range(instrumental.shape[0])
                    ])
                else:
                    instrumental = resample_audio(instrumental, instr_sr, target_sr)
                instr_sr = target_sr
        
        # Ensure same shape
        vocals_mono = len(vocals.shape) == 1
        instr_mono = len(instrumental.shape) == 1
        
        if vocals_mono and not instr_mono:
            # Convert mono vocals to stereo
            vocals = np.array([vocals, vocals])
        elif not vocals_mono and instr_mono:
            # Convert mono instrumental to stereo
            instrumental = np.array([instrumental, instrumental])
        elif vocals_mono and instr_mono:
            # Both mono - keep as mono
            pass
        
        # Ensure same length
        if vocals_mono and instr_mono:
            min_len = min(len(vocals), len(instrumental))
            vocals = vocals[:min_len]
            instrumental = instrumental[:min_len]
        else:
            min_len = min(vocals.shape[1], instrumental.shape[1])
            vocals = vocals[:, :min_len]
            instrumental = instrumental[:, :min_len]
        
        # Preserve original dynamic range before mixing
        vocals_rms = np.sqrt(np.mean(vocals**2)) if not vocals_mono else np.sqrt(np.mean(vocals**2))
        instr_rms = np.sqrt(np.mean(instrumental**2)) if not instr_mono else np.sqrt(np.mean(instrumental**2))
        
        # Apply gains and mix with better balance
        mixed = (vocals * vocals_gain) + (instrumental * instrumental_gain)
        
        # Smart normalization - preserve dynamics while preventing clipping
        max_val = np.max(np.abs(mixed))
        if max_val > 0.95:  # Only normalize if approaching clipping
            # Use gentle limiting instead of hard normalization
            target_peak = 0.95
            mixed = mixed * (target_peak / max_val)
            print(f"Audio gently limited to prevent clipping (peak: {max_val:.3f} → {target_peak:.3f})")
        
        # Preserve relative levels between vocals and instrumentals
        mixed_rms = np.sqrt(np.mean(mixed**2))
        if mixed_rms > 0 and vocals_rms > 0 and instr_rms > 0:
            # Maintain original energy balance
            original_energy = vocals_rms + instr_rms
            if mixed_rms != original_energy and abs(mixed_rms - original_energy) / original_energy > 0.1:
                energy_ratio = original_energy / mixed_rms
                mixed = mixed * min(energy_ratio, 1.2)  # Cap energy boost to prevent distortion
        
        # Save based on output format with highest quality settings
        if self.output_format == "wav":
            if not vocals_mono and not instr_mono:
                mixed = mixed.T  # Transpose for soundfile
            # Save as high-quality 32-bit float WAV for maximum dynamic range
            import soundfile as sf
            try:
                sf.write(str(output_path), mixed, vocals_sr, subtype='FLOAT')
                print(f"Saved high-quality 32-bit float WAV: {output_path}")
            except:
                # Fallback to standard save method
                save_audio(mixed, output_path, vocals_sr)
        else:
            # For MP3/other formats, save as WAV first then convert
            temp_wav = str(output_path).replace(f".{self.output_format}", "_temp.wav")
            
            if not vocals_mono and not instr_mono:
                mixed = mixed.T  # Transpose for soundfile
            save_audio(mixed, temp_wav, vocals_sr)
            
            if self.output_format == "mp3":
                convert_wav_to_mp3(temp_wav, output_path, self.output_bitrate)
                os.unlink(temp_wav)  # Clean up temp file
        
        print(f"Remixed audio saved: {output_path}")
        
        return {
            "method": "numpy",
            "vocals_gain": vocals_gain,
            "instrumental_gain": instrumental_gain,
            "output_format": self.output_format,
            "sample_rate": vocals_sr,
            "normalized": max_val > 1.0
        }


def remix_audio(
    vocals_path: Union[str, Path],
    instrumental_path: Union[str, Path],
    output_path: Union[str, Path],
    output_format: str = "wav",  # Default to WAV for best quality
    output_bitrate: str = "320k",
    vocals_gain: float = 1.0,
    instrumental_gain: float = 1.0
) -> Dict[str, Any]:
    """
    Convenience function to remix audio tracks with quality optimization.
    
    Args:
        vocals_path: Path to vocals track
        instrumental_path: Path to instrumental track
        output_path: Path to save remixed audio
        output_format: Output format ("wav" for best quality, "mp3" for smaller files)
        output_bitrate: Output bitrate for compressed formats
        vocals_gain: Vocals gain adjustment (1.0 = original level)
        instrumental_gain: Instrumental gain adjustment (1.0 = original level)
        
    Returns:
        Remix statistics including quality metrics
    """
    remixer = AudioRemixer(output_format, output_bitrate)
    return remixer.remix_audio(
        vocals_path, instrumental_path, output_path,
        vocals_gain, instrumental_gain
    )


def remix_high_quality(
    vocals_path: Union[str, Path],
    instrumental_path: Union[str, Path], 
    output_path: Union[str, Path],
    vocals_gain: float = 1.0,
    instrumental_gain: float = 1.0
) -> Dict[str, Any]:
    """
    High-quality remix optimized for audiophile results.
    
    Uses the best available settings for maximum quality:
    - 32-bit float WAV output
    - Preserved dynamic range
    - Minimal normalization
    - Professional audio processing
    
    Args:
        vocals_path: Path to processed vocals
        instrumental_path: Path to original instrumentals
        output_path: Path for high-quality output (will be .wav)
        vocals_gain: Vocal level adjustment
        instrumental_gain: Instrumental level adjustment
        
    Returns:
        Remix statistics with quality metrics
    """
    # Ensure WAV output for maximum quality
    if not str(output_path).endswith('.wav'):
        output_path = Path(str(output_path).rsplit('.', 1)[0] + '.wav')
    
    remixer = AudioRemixer("wav", "320k")
    return remixer.remix_audio(
        vocals_path, instrumental_path, output_path,
        vocals_gain, instrumental_gain, use_ffmpeg=True
    )
