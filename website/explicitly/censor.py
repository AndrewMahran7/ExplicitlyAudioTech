"""
Audio censoring functionality to mute or bleep profane content.

This module handles the final step of the profanity filtering pipeline:
selectively censoring identified profane words while preserving the rest
of the audio. It provides two censoring methods:

1. Muting: Replaces profane audio with silence (gradual fade for smoothness)
2. Bleeping: Replaces profane audio with a tone (classic "bleep" sound)

Key design considerations:
- Precise timing: Uses word-level timestamps from speech recognition
- Smooth transitions: Applies audio fades to avoid harsh cuts/clicks
- Margin handling: Adds small buffers before/after words for clarity
- Multi-channel support: Works with mono and stereo audio
- Detailed reporting: Generates comprehensive statistics and reports

The censoring process:
1. Load original audio file
2. For each profane word segment:
   - Calculate exact start/end times with margins
   - Apply chosen censoring method (mute/bleep)
   - Use audio fades for smooth transitions
3. Save censored audio file
4. Generate detailed report with statistics

This approach preserves audio quality while removing offensive content,
making it suitable for broadcast, streaming, or family-friendly versions.
"""

# Standard library imports
import json                           # JSON report generation
from pathlib import Path             # Modern path handling
from typing import List, Dict, Union, Optional, Any  # Type hints

# Core processing libraries
import numpy as np                   # Audio array manipulation

# Internal modules
from .transcribe_align import WordSegment    # Word timing data structure
from .utils_audio import (                   # Audio processing utilities
    load_audio, save_audio, mute_segment, 
    apply_fade, create_silence, get_audio_duration
)


class AudioCensor:
    """
    Handles precise audio censoring based on profane word timings.
    
    This class implements intelligent audio censoring that goes beyond simple
    word replacement. It handles timing precision, audio quality, and user
    preferences to create professional-quality censored audio.
    
    Features:
    - Multiple censoring methods (mute silence vs bleep tones)
    - Configurable timing margins for better speech flow
    - Smooth audio transitions with fade in/out
    - Multi-channel audio support (mono/stereo)
    - Detailed censoring statistics and reporting
    - Quality preservation (no artifacts or clicks)
    
    The censoring process considers human speech patterns:
    - Pre-margin: Brief silence before profane words (helps with fast speech)
    - Post-margin: Brief silence after profane words (ensures complete removal)
    - Audio fades: Gradual transitions prevent harsh cuts that sound unnatural
    
    This creates censored audio that sounds natural rather than obviously edited.
    """
    
    def __init__(
        self,
        fade_ms: int = 25,              # Fade duration for smooth transitions (reduced)
        pre_margin_ms: int = 0,         # Buffer time before profane words (eliminated for better timing)
        post_margin_ms: int = 25,       # Buffer time after profane words (minimal)
        censor_method: str = "mute"     # Censoring approach ("mute", "bleep", or "reverse")
    ):
        """
        Initialize the audio censor with quality and timing preferences.
        
        The timing parameters are crucial for natural-sounding results:
        - Fade duration: Too short causes clicks, too long affects adjacent words
        - Pre-margin: Ensures fast speech doesn't "leak" into profanity
        - Post-margin: Ensures word endings are completely removed
        
        Args:
            fade_ms: Audio fade duration in milliseconds (prevents clicks/pops)
                    Recommended: 25-100ms depending on content type
            pre_margin_ms: Extra silence before each profane word (milliseconds)
                         Recommended: 50-150ms for natural speech flow
            post_margin_ms: Extra silence after each profane word (milliseconds)
                          Recommended: 50-150ms to ensure complete removal
            censor_method: Censoring technique:
                         - "mute": Replace with silence (subtle, professional)
                         - "bleep": Replace with tone (obvious, classic)
                         - "reverse": Reverse audio and lower volume (creative, subtle)
        """
        self.fade_ms = fade_ms
        self.pre_margin_ms = pre_margin_ms
        self.post_margin_ms = post_margin_ms
        self.censor_method = censor_method
    
    def _generate_bleep(
        self, 
        duration_ms: float,        # How long the bleep should last
        sr: int,                   # Audio sample rate (Hz)
        frequency: float = 1000.0, # Bleep tone frequency (Hz)
        fade_ms: int = 10         # Fade duration to prevent clicks
    ) -> np.ndarray:
        """
        Generate a professional-quality bleep tone for audio censoring.
        
        Creates a sine wave tone at the specified frequency with proper
        fade in/out to prevent audio artifacts. The frequency and volume
        are chosen to be audible but not harsh or annoying.
        
        Technical details:
        - Uses sine wave generation for clean, predictable tone
        - Volume set to 30% to avoid overpowering surrounding audio
        - Applies fade to prevent clicks when inserting into audio stream
        - Generates exact sample count to match censored segment length
        
        Args:
            duration_ms: Bleep duration in milliseconds (matches profane word length)
            sr: Audio sample rate in Hz (must match source audio)
            frequency: Bleep frequency in Hz (1000Hz is standard "TV bleep")
            fade_ms: Fade duration in milliseconds (prevents audio clicks)
            
        Returns:
            numpy.ndarray: Audio samples for the bleep tone (float32 format)
        """
        samples = int(duration_ms * sr / 1000)
        t = np.linspace(0, duration_ms / 1000, samples, False)
        
        # Generate sine wave
        bleep = np.sin(2 * np.pi * frequency * t) * 0.3  # Lower volume
        
        # Apply fade to avoid clicks
        if fade_ms > 0:
            bleep = apply_fade(bleep, sr, fade_ms)
        
        return bleep.astype(np.float32)
    
    def _generate_reversed_audio(
        self,
        audio_segment: np.ndarray,     # Original audio segment to reverse
        volume_reduction: float = 0.3  # How much to reduce volume (0.3 = 30% of original)
    ) -> np.ndarray:
        """
        Generate reversed audio with reduced volume for subtle censoring.
        
        This creates a creative censoring effect by:
        1. Reversing the audio (playing it backwards)
        2. Reducing the volume to make it less prominent
        3. Preserving the timing and rhythm of speech
        
        This method is much more subtle than bleeping and maintains the
        musical flow while making the profane word unintelligible.
        
        Args:
            audio_segment: The original audio segment containing the profane word
            volume_reduction: Volume multiplier (0.1 = very quiet, 0.5 = half volume)
            
        Returns:
            numpy.ndarray: Reversed and quieted audio segment
        """
        # Reverse the audio (flip the array)
        reversed_audio = np.flip(audio_segment)
        
        # Reduce volume
        quieted_audio = reversed_audio * volume_reduction
        
        # Apply slight fade to make it even more subtle
        if len(quieted_audio) > 100:  # Only if segment is long enough
            fade_samples = min(50, len(quieted_audio) // 4)
            
            # Fade in at start
            for i in range(fade_samples):
                factor = i / fade_samples
                quieted_audio[i] *= factor
            
            # Fade out at end
            for i in range(fade_samples):
                factor = (fade_samples - i) / fade_samples
                quieted_audio[-(i+1)] *= factor
        
        return quieted_audio.astype(np.float32)
    
    def censor_audio(
        self, 
        audio_path: Union[str, Path],        # Source audio file to process
        profane_segments: List[WordSegment], # Words to censor with timing data
        output_path: Union[str, Path],       # Where to save censored result
        instrumental_path: Optional[Union[str, Path]] = None  # Optional instrumental track for volume compensation
    ) -> Dict[str, Any]:
        """
        Apply precise audio censoring to remove profane content.
        
        This is the core censoring method that processes the entire audio file,
        applying the chosen censoring technique to each identified profane word
        while preserving all clean audio content.
        
        The process:
        1. Load original audio file (supports mono/stereo)
        2. For each profane word segment:
           - Calculate precise timing with margins
           - Apply censoring method (mute silence or bleep tone)
           - Use smooth audio fades to prevent artifacts
        3. Generate detailed statistics about the censoring process
        4. Save the censored audio file
        
        Quality considerations:
        - Preserves original audio format and quality
        - Maintains proper audio levels and dynamics
        - Applies smooth transitions to avoid detection
        - Handles edge cases (overlapping words, file boundaries)
        
        Args:
            audio_path: Path to input audio file (MP3, WAV, FLAC, etc.)
            profane_segments: List of WordSegment objects with timing and text
                            Each segment contains start/end times and confidence
            output_path: Path where censored audio will be saved (typically WAV)
            
        Returns:
            Dictionary containing detailed censoring statistics:
            {
                'total_segments': int,        # Number of words censored
                'censored_duration_ms': float, # Total milliseconds censored
                'censor_method': str,          # Method used (mute/bleep)
                'segments': [...]              # Per-word censoring details
            }
            
        Raises:
            RuntimeError: If censoring fails (corrupted audio, disk space, etc.)
        """
        try:
            print(f"Censoring audio: {audio_path}")
            
            # Load the source audio file (preserving original format)
            audio, sr = load_audio(audio_path, sr=None, mono=False)
            
            # Load instrumental track if provided for volume compensation
            instrumental_audio = None
            if instrumental_path and self.censor_method == "reverse":
                try:
                    instrumental_audio, instr_sr = load_audio(instrumental_path, sr=sr, mono=False)
                    print(f"Loaded instrumental track for volume compensation: {instrumental_path}")
                    
                    # Ensure same format as main audio
                    if len(instrumental_audio.shape) == 1 and len(audio.shape) > 1:
                        instrumental_audio = instrumental_audio.reshape(1, -1)
                    elif len(instrumental_audio.shape) > 1 and len(audio.shape) == 1:
                        audio = audio.reshape(1, -1)
                except Exception as e:
                    print(f"Warning: Could not load instrumental track: {e}")
                    instrumental_audio = None
            
            # Normalize audio format for processing (ensure 2D array)
            is_mono = len(audio.shape) == 1
            if is_mono:
                # Convert mono (1D) to channel format (2D: [channels, samples])
                audio = audio.reshape(1, -1)
            
            # Create working copy for censoring (preserves original)
            censored_audio = audio.copy()
            
            # Create instrumental compensation array if available
            compensated_instrumental = None
            if instrumental_audio is not None:
                compensated_instrumental = instrumental_audio.copy()
            censor_stats = {
                "total_segments": len(profane_segments),
                "censored_duration_ms": 0,
                "censor_method": self.censor_method,
                "segments": []
            }
            
            for segment in profane_segments:
                # Apply smart timing adjustment for rap content
                original_start_ms = segment.start * 1000
                original_end_ms = segment.end * 1000
                original_duration = original_end_ms - original_start_ms
                
                # Detect and fix obviously wrong timing (common with rap alignment failures)
                if original_duration > 1500:  # Words longer than 1.5 seconds are suspect
                    print(f"    ⚠️ Suspicious long duration for '{segment.word}': {original_duration:.0f}ms")
                    # Compress unreasonably long words (likely estimation errors)
                    compressed_duration = min(800, original_duration * 0.6)  # Max 800ms, or 60% of original
                    
                    # Keep start time, adjust end time
                    start_ms = original_start_ms
                    end_ms = original_start_ms + compressed_duration
                    
                    print(f"    🔧 Adjusted to: {start_ms:.0f}ms-{end_ms:.0f}ms ({compressed_duration:.0f}ms)")
                else:
                    # Use original timing for reasonable durations
                    start_ms = original_start_ms
                    end_ms = original_end_ms
                
                duration_ms = end_ms - start_ms + self.pre_margin_ms + self.post_margin_ms
                
                # Debug timing information with sample positions
                start_sample = max(0, int((start_ms - self.pre_margin_ms) * sr / 1000))
                end_sample = min(len(censored_audio[0]), int((end_ms + self.post_margin_ms) * sr / 1000))
                
                print(f"Censoring '{segment.word}': {start_ms:.0f}ms-{end_ms:.0f}ms "
                      f"(samples {start_sample}-{end_sample}, duration: {(end_sample-start_sample)/sr:.3f}s)")
                
                # Apply censoring to each channel
                for channel in range(censored_audio.shape[0]):
                    if self.censor_method == "mute":
                        censored_audio[channel] = mute_segment(
                            censored_audio[channel],
                            sr,
                            start_ms,
                            end_ms,
                            fade_ms=self.fade_ms,
                            pre_margin_ms=self.pre_margin_ms,
                            post_margin_ms=self.post_margin_ms
                        )
                    elif self.censor_method == "bleep":
                        # Generate a bleep tone matching the word duration
                        bleep = self._generate_bleep(
                            duration_ms, sr, fade_ms=self.fade_ms
                        )
                        
                        # Convert timing to exact sample positions
                        start_sample = max(0, int((start_ms - self.pre_margin_ms) * sr / 1000))
                        end_sample = min(
                            len(censored_audio[channel]), 
                            int((end_ms + self.post_margin_ms) * sr / 1000)
                        )
                        
                        # Ensure bleep exactly matches the audio segment length
                        actual_length = end_sample - start_sample
                        if len(bleep) > actual_length:
                            # Truncate bleep if it's too long
                            bleep = bleep[:actual_length]
                        elif len(bleep) < actual_length:
                            # Pad bleep with silence if it's too short
                            padding = np.zeros(actual_length - len(bleep))
                            bleep = np.concatenate([bleep, padding])
                        
                        # Replace the profane audio segment with the bleep tone
                        censored_audio[channel, start_sample:end_sample] = bleep
                        
                    elif self.censor_method == "reverse":
                        # Extract the original audio segment
                        start_sample = max(0, int((start_ms - self.pre_margin_ms) * sr / 1000))
                        end_sample = min(
                            len(censored_audio[channel]), 
                            int((end_ms + self.post_margin_ms) * sr / 1000)
                        )
                        
                        # Get the original audio segment
                        original_segment = censored_audio[channel, start_sample:end_sample].copy()
                        
                        # Generate reversed and quieted version
                        reversed_segment = self._generate_reversed_audio(
                            original_segment, volume_reduction=0.3
                        )
                        
                        # Ensure same length
                        actual_length = end_sample - start_sample
                        if len(reversed_segment) != actual_length:
                            if len(reversed_segment) > actual_length:
                                reversed_segment = reversed_segment[:actual_length]
                            else:
                                padding = np.zeros(actual_length - len(reversed_segment))
                                reversed_segment = np.concatenate([reversed_segment, padding])
                        
                        # Replace the original segment with reversed version
                        censored_audio[channel, start_sample:end_sample] = reversed_segment
                        
                        # Boost instrumental volume during this segment to compensate
                        if compensated_instrumental is not None and channel < compensated_instrumental.shape[0]:
                            # Calculate volume boost - if vocals go to 30%, boost instrumental by ~40% 
                            instrumental_boost = 1.4  # 40% boost to compensate for 70% vocal reduction
                            
                            # Apply boost to instrumental in the same time segment
                            if end_sample <= compensated_instrumental.shape[1]:
                                original_instr = compensated_instrumental[channel, start_sample:end_sample].copy()
                                boosted_instr = original_instr * instrumental_boost
                                
                                # Apply gentle fade to the boost to avoid sudden volume changes
                                fade_samples = min(int(0.05 * sr), actual_length // 4)  # 50ms fade
                                if fade_samples > 0:
                                    # Fade in the boost
                                    for i in range(fade_samples):
                                        blend_factor = i / fade_samples
                                        boosted_instr[i] = original_instr[i] * (1 + (instrumental_boost - 1) * blend_factor)
                                    
                                    # Fade out the boost
                                    for i in range(fade_samples):
                                        blend_factor = (fade_samples - i) / fade_samples
                                        idx = -(i + 1)
                                        boosted_instr[idx] = original_instr[idx] * (1 + (instrumental_boost - 1) * blend_factor)
                                
                                compensated_instrumental[channel, start_sample:end_sample] = boosted_instr
                                print(f"  → Boosted instrumental by {instrumental_boost:.1f}x during '{segment.word}' to maintain energy")
                
                # Record segment info
                segment_info = {
                    "word": segment.word,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "duration_ms": duration_ms,
                    "confidence": segment.confidence
                }
                censor_stats["segments"].append(segment_info)
                censor_stats["censored_duration_ms"] += duration_ms
                
                print(f"Censored '{segment.word}' at {start_ms:.0f}ms - {end_ms:.0f}ms")
            
            # If we have compensated instrumental, we need to mix it back with the vocals
            if compensated_instrumental is not None and self.censor_method == "reverse":
                print("Mixing compensated instrumental with censored vocals...")
                
                # Ensure same length
                min_length = min(censored_audio.shape[1], compensated_instrumental.shape[1])
                censored_audio = censored_audio[:, :min_length]
                compensated_instrumental = compensated_instrumental[:, :min_length]
                
                # Mix the tracks (vocals + boosted instrumental)
                mixed_audio = censored_audio + compensated_instrumental
                
                # Gentle limiting to prevent clipping from the mix
                max_val = np.max(np.abs(mixed_audio))
                if max_val > 0.95:
                    mixed_audio = mixed_audio * (0.95 / max_val)
                    print(f"  → Applied gentle limiting to prevent clipping (peak: {max_val:.3f} → 0.95)")
                
                final_audio = mixed_audio
            else:
                final_audio = censored_audio
            
            # Convert back to original format
            if is_mono:
                final_audio = final_audio[0]
            else:
                final_audio = final_audio.T  # Transpose for soundfile
            
            # Save censored audio
            save_audio(final_audio, output_path, sr)
            
            print(f"Censored audio saved: {output_path}")
            return censor_stats
            
        except Exception as e:
            raise RuntimeError(f"Audio censoring failed: {str(e)}")
    
    def generate_report(
        self,
        original_audio_path: Union[str, Path],   # Original unprocessed audio
        censored_audio_path: Union[str, Path],   # Censored output audio
        profane_segments: List[WordSegment],     # All detected profane words
        censor_stats: Dict[str, Any],           # Statistics from censoring process
        output_path: Union[str, Path]           # Where to save JSON report
    ) -> None:
        """
        Generate a comprehensive censoring report for audit and analysis.
        
        Creates a detailed JSON report documenting the entire censoring process.
        This is valuable for:
        - Quality assurance and review
        - Understanding content patterns
        - Compliance and audit requirements
        - Performance optimization
        - User feedback and transparency
        
        The report includes:
        - File metadata (paths, timestamps, settings)
        - Audio analysis (durations, censorship percentage)
        - Profanity detection details (words found, confidence scores)
        - Processing statistics (timing, performance metrics)
        - Complete word-by-word breakdown
        
        This enables users to understand exactly what was censored and why,
        building trust in the automated process.
        
        Args:
            original_audio_path: Path to the original unprocessed audio file
            censored_audio_path: Path to the final censored output file
            profane_segments: All WordSegment objects for detected profane words
            censor_stats: Statistics dictionary returned by censor_audio()
            output_path: Where to save the comprehensive JSON report
            
        Raises:
            RuntimeError: If report generation fails (disk space, permissions, etc.)
        """
        try:
            from datetime import datetime
            
            # Get audio durations
            original_duration = get_audio_duration(original_audio_path)
            censored_duration = get_audio_duration(censored_audio_path)
            
            # Calculate statistics
            total_censored_ms = censor_stats["censored_duration_ms"]
            censorship_percentage = (total_censored_ms / 1000) / original_duration * 100
            
            # Create comprehensive report
            report = {
                "metadata": {
                    "original_file": str(original_audio_path),
                    "censored_file": str(censored_audio_path),
                    "processing_timestamp": datetime.now().isoformat(),
                    "censor_method": self.censor_method
                },
                "audio_info": {
                    "original_duration_seconds": original_duration,
                    "censored_duration_seconds": censored_duration,
                    "total_censored_ms": total_censored_ms,
                    "censorship_percentage": censorship_percentage
                },
                "profanity_detection": {
                    "total_profane_words": len(profane_segments),
                    "unique_words": len(set(seg.word.lower().strip() for seg in profane_segments)),
                    "segments": [seg.to_dict() for seg in profane_segments]
                },
                "censoring_settings": {
                    "fade_ms": self.fade_ms,
                    "pre_margin_ms": self.pre_margin_ms,
                    "post_margin_ms": self.post_margin_ms,
                    "censor_method": self.censor_method
                },
                "statistics": censor_stats
            }
            
            # Save report
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"Censoring report saved: {output_path}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate report: {str(e)}")


def censor_audio(
    audio_path: Union[str, Path],        # Source audio to process
    profane_segments: List[WordSegment], # Words to censor with timing
    output_path: Union[str, Path],       # Censored output path
    fade_ms: int = 50,                  # Fade duration for smoothness
    pre_margin_ms: int = 100,           # Buffer before profane words
    post_margin_ms: int = 100,          # Buffer after profane words
    censor_method: str = "mute",        # Censoring technique
    instrumental_path: Optional[Union[str, Path]] = None  # Optional instrumental for volume compensation
) -> Dict[str, Any]:
    """
    One-shot convenience function for audio censoring.
    
    This is a simple wrapper around the AudioCensor class for quick,
    one-time censoring operations. It creates an AudioCensor instance
    with the specified settings and processes the audio file.
    
    For batch processing multiple files or when you need to generate
    reports, it's more efficient to create an AudioCensor instance
    directly and reuse it.
    
    Args:
        audio_path: Path to input audio file to be censored
        profane_segments: List of WordSegment objects with profane words and timing
        output_path: Path where the censored audio will be saved
        fade_ms: Fade duration in milliseconds (25-100ms recommended)
        pre_margin_ms: Extra silence before each word (50-150ms recommended)
        post_margin_ms: Extra silence after each word (50-150ms recommended)
        censor_method: "mute" for silence, "bleep" for tone, or "reverse" for reversed audio
        
    Returns:
        Dictionary with censoring statistics and segment details
        
    Example:
        >>> from explicitly.transcribe_align import WordSegment
        >>> segments = [WordSegment("damn", 1.5, 1.8, 0.95)]
        >>> stats = censor_audio("input.mp3", segments, "clean.wav")
        >>> print(f"Censored {stats['total_segments']} words")
    """
    censor = AudioCensor(
        fade_ms=fade_ms,
        pre_margin_ms=pre_margin_ms,
        post_margin_ms=post_margin_ms,
        censor_method=censor_method
    )
    
    return censor.censor_audio(audio_path, profane_segments, output_path, instrumental_path)
