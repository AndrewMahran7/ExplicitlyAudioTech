"""
Speech transcription and word-level alignment using Whisper and WhisperX.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

import torch
import numpy as np
from faster_whisper import WhisperModel

try:
    import whisperx
except ImportError:
    whisperx = None

try:
    import librosa
    import scipy.signal
    from scipy import ndimage
except ImportError:
    librosa = None
    scipy = None

from .utils_audio import load_audio, resample_audio, save_audio


class TranscriptionSegment:
    """
    Represents a transcribed segment with timing information.
    
    A transcription segment is a chunk of text that was transcribed as a unit
    by Whisper. Typically these are phrases or sentences, lasting several seconds
    and containing multiple words. This is the initial output from Faster-Whisper
    before word-level alignment.
    
    Segments are later broken down into individual words with precise timing
    for accurate profanity detection and censoring.
    
    Attributes:
        start: Start time of the segment in seconds
        end: End time of the segment in seconds  
        text: The transcribed text for this time period
        confidence: Whisper's confidence score (0.0-1.0, can be negative)
    """
    
    def __init__(
        self, 
        start: float,           # Segment start time in seconds from audio beginning
        end: float,             # Segment end time in seconds from audio beginning
        text: str,              # Transcribed text for this segment
        confidence: float = 1.0  # Whisper confidence score (1.0 = perfect)
    ):
        self.start = start      # Store start time (seconds)
        self.end = end          # Store end time (seconds)
        self.text = text        # Store transcribed text
        self.confidence = confidence  # Store confidence score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "confidence": self.confidence
        }


class WordSegment:
    """
    Represents a single word with precise timing information.
    
    This is the core data structure used throughout the Explicitly pipeline.
    Each WordSegment represents one word from the transcription with exact
    timing boundaries. This precision is essential for:
    
    - Accurate profanity detection (knowing exactly which word is profane)
    - Precise censoring (muting only the profane word, not surrounding speech)
    - Quality audio output (avoiding cuts in the middle of clean words)
    - Detailed logging (tracking exactly when each word occurs)
    
    The timing information comes from either:
    1. WhisperX word-level alignment (most accurate)
    2. Estimated timing based on segment duration (fallback)
    
    Attributes:
        start: Word start time in seconds from audio beginning
        end: Word end time in seconds from audio beginning
        word: The transcribed word text (cleaned of extra whitespace)
        confidence: Whisper confidence score for this word
    """
    
    def __init__(
        self, 
        start: float,           # Word start time in seconds
        end: float,             # Word end time in seconds
        word: str,              # The transcribed word
        confidence: float = 1.0  # Confidence score from Whisper
    ):
        self.start = start                # Store start time
        self.end = end                    # Store end time
        self.word = word.strip()          # Store word (remove extra whitespace)
        self.confidence = confidence      # Store confidence score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "word": self.word,
            "confidence": self.confidence
        }


class AudioTranscriber:
    """
    Handles audio transcription and word-level alignment.
    
    This class orchestrates the complete speech-to-text pipeline, from loading
    AI models to producing precisely timed word segments. It manages both
    Faster-Whisper (for transcription) and WhisperX (for alignment) models.
    
    The class handles:
    - Model loading and initialization on correct device (CPU/GPU)
    - Audio preprocessing (format conversion, resampling)
    - Two-stage processing: transcription then alignment
    - Graceful fallback when advanced features aren't available
    - Device compatibility checking and error handling
    
    Processing pipeline:
    1. Load Faster-Whisper model for transcription
    2. Load WhisperX model for word alignment (if available)
    3. Transcribe audio into segments with approximate timing
    4. Align segments to get precise word-level timing
    5. Return WordSegment objects for downstream processing
    """
    
    def __init__(
        self,
        whisper_model: str = "large",    # Whisper model size/variant
        device: Optional[str] = None,      # Processing device preference
        batch_size: int = 16               # Batch size for efficient processing
    ):
        """
        Initialize the audio transcriber with model configuration.
        
        Sets up the transcription pipeline with specified models and device
        preferences. Models are loaded immediately to catch any issues early.
        
        Args:
            whisper_model: Whisper model variant to use. Options:
                          - "tiny.en": Fastest, lowest accuracy (~39 MB)
                          - "base.en": Good balance (~74 MB) [DEFAULT]
                          - "small.en": Better accuracy (~244 MB)
                          - "medium.en": High accuracy (~769 MB)
                          - "large": Best accuracy, multilingual (~1550 MB)
            device: Processing device preference:
                   - None: Auto-detect best available device
                   - "cpu": Force CPU processing (slower but compatible)
                   - "cuda": Force GPU processing (faster but needs CUDA)
                   - "auto": Automatically choose best available
            batch_size: Number of audio chunks to process simultaneously.
                       Higher values use more memory but may be faster.
        """
        # Store configuration parameters
        self.model_name = whisper_model        # Which Whisper model to use
        self.device = self._get_device(device) # Resolved device (cpu/cuda)
        self.batch_size = batch_size           # Processing batch size
        
        # Model instances (loaded in _load_models)
        self.whisper_model = None      # Faster-Whisper instance
        self.alignment_model = None    # WhisperX alignment model
        
        # Load models immediately to catch configuration issues
        self._load_models()
    
    def _get_device(self, device: Optional[str]) -> str:
        """
        Determine the best device to use.
        """
        if device is None or device == "auto":
            if torch.cuda.is_available():
                print("GPU (CUDA) detected and available for transcription")
                return "cuda"
            else:
                print("Using CPU for transcription (CUDA not available)")
                return "cpu"
        elif device == "cuda":
            if not torch.cuda.is_available():
                print("⚠️  Warning: CUDA requested but not available for transcription.")
                print("   Falling back to CPU processing...")
                return "cpu"
            else:
                return "cuda"
        return device
    
    def _load_models(self) -> None:
        """
        Load Whisper and alignment models.
        """
        try:
            print(f"Loading Whisper model '{self.model_name}' on {self.device}...")
            
            # Load Faster Whisper
            self.whisper_model = WhisperModel(
                self.model_name, 
                device=self.device,
                compute_type="float16" if self.device == "cuda" else "int8"
            )
            
            print("Whisper model loaded successfully.")
            
            # Load WhisperX alignment model if available
            if whisperx is not None:
                try:
                    print("Loading WhisperX alignment model...")
                    self.alignment_model = whisperx.load_align_model(
                        language_code="en", device=self.device
                    )
                    print("Alignment model loaded successfully.")
                except Exception as e:
                    print(f"Warning: Could not load alignment model: {e}")
                    print("Falling back to Whisper-only transcription (no word-level alignment)")
                    self.alignment_model = None
            else:
                print("Warning: WhisperX not available, using Whisper-only transcription.")
                self.alignment_model = None
                
        except Exception as e:
            raise RuntimeError(f"Failed to load transcription models: {str(e)}")
    
    def _preprocess_for_conversation(self, audio_path: Path, output_path: Path) -> Path:
        """
        Transform rap vocals to sound more like conversation for better Whisper accuracy.
        
        Multiple techniques to make rap sound conversational:
        1. Slow down by 50% (half speed) - KEY FIX for timing
        2. Dynamic range expansion - make quiet parts audible
        3. Noise gate - reduce music bleed 
        4. Volume normalization - consistent levels
        5. Pitch neutralization - reduce vocal effects
        6. Frequency emphasis - boost speech frequencies
        
        Args:
            audio_path: Original vocals file
            output_path: Where to save processed vocals
            
        Returns:
            Path to processed vocals file
        """
        if librosa is None:
            print("    ⚠️ Librosa not available, skipping rap preprocessing")
            return audio_path
            
        try:
            print(f"    🎤 Preprocessing rap vocals for better transcription...")
            
            # Load audio
            audio, sr = librosa.load(audio_path, sr=None)
            processed = audio.copy()
            
            # 1. MOST IMPORTANT: Slow down by 50% while preserving pitch
            print(f"    🐌 Slowing vocals to 50% speed (KEY timing fix)...")
            processed = librosa.effects.time_stretch(processed, rate=0.5)
            
            # 2. Dynamic range expansion (make quiet parts more audible)
            print(f"    📢 Expanding dynamic range...")
            # Calculate RMS energy in overlapping windows
            hop_length = 512
            frame_length = 2048
            rms = librosa.feature.rms(y=processed, frame_length=frame_length, hop_length=hop_length)[0]
            
            # Smooth the RMS to avoid artifacts
            if scipy is not None:
                rms_smooth = ndimage.uniform_filter1d(rms, size=10)
            else:
                rms_smooth = rms
                
            # Apply dynamic expansion
            for i in range(len(processed)):
                frame_idx = min(i // hop_length, len(rms_smooth) - 1)
                current_rms = rms_smooth[frame_idx]
                
                if current_rms < 0.05:  # Very quiet - boost significantly
                    processed[i] *= 3.0
                elif current_rms < 0.15:  # Quiet - boost moderately  
                    processed[i] *= 2.0
                elif current_rms > 0.7:  # Loud - gentle limiting
                    processed[i] *= 0.8
            
            # 3. Simple noise gate to reduce music bleed
            print(f"    🔇 Applying noise gate...")
            gate_threshold = 0.015
            processed[np.abs(processed) < gate_threshold] *= 0.2
            
            # 4. Normalize volume
            print(f"    🎚️ Normalizing volume...")
            peak = np.max(np.abs(processed))
            if peak > 0:
                processed = processed * (0.8 / peak)  # Leave headroom
            
            # 5. Boost speech frequencies (1-4kHz) to make vocals clearer
            print(f"    🗣️ Boosting speech frequencies...")
            if librosa is not None:
                # Simple high-pass filter to reduce low-end rumble
                processed = librosa.effects.preemphasis(processed, coef=0.97)
            
            # 6. Slight pitch correction to neutralize vocal effects
            print(f"    🎵 Neutralizing vocal effects...")
            try:
                # Very subtle pitch shift to reduce autotune artifacts
                processed = librosa.effects.pitch_shift(processed, sr=sr, n_steps=0.05)
            except:
                pass  # Skip if pitch shifting fails
            
            # Save processed audio
            import soundfile as sf
            sf.write(output_path, processed, sr)
            
            duration_orig = len(audio) / sr
            duration_proc = len(processed) / sr
            
            print(f"    ✅ Vocal preprocessing complete!")
            print(f"       Original: {duration_orig:.1f}s → Processed: {duration_proc:.1f}s")
            print(f"       Saved: {output_path}")
            
            return output_path
            
        except Exception as e:
            print(f"    ⚠️ Vocal preprocessing failed: {e}")
            return audio_path  # Fall back to original
    
    def _scale_timestamps_back(self, word_segments: List[WordSegment], speed_factor: float = 2.0) -> List[WordSegment]:
        """
        Scale timestamps back to original speed after processing slowed audio.
        
        Args:
            word_segments: Word segments from slowed audio
            speed_factor: Factor to scale back (2.0 for half-speed processing)
            
        Returns:
            Word segments with corrected timestamps for original speed
        """
        scaled_segments = []
        
        print(f"    🎯 Scaling {len(word_segments)} timestamps back by {speed_factor}x...")
        
        for segment in word_segments:
            # Scale timestamps back to original speed
            original_start = segment.start / speed_factor
            original_end = segment.end / speed_factor
            
            scaled_segment = WordSegment(
                start=original_start,
                end=original_end,
                word=segment.word,
                confidence=segment.confidence
            )
            
            scaled_segments.append(scaled_segment)
        
        print(f"    ✅ Timestamps scaled back to original speed")
        return scaled_segments

    def transcribe(
        self, 
        audio_path: Union[str, Path], 
        target_sr: int = 16000
    ) -> List[TranscriptionSegment]:
        """
        Transcribe audio file into segments.
        
        Args:
            audio_path: Path to audio file
            target_sr: Target sample rate for transcription
            
        Returns:
            List of transcription segments
        """
        try:
            print(f"Transcribing audio: {audio_path}")
            
            # Load and preprocess audio
            audio, sr = load_audio(audio_path, sr=target_sr, mono=True)
            
            # Save temporary file if needed
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                save_audio(audio, tmp.name, target_sr)
                temp_path = tmp.name
            
            try:
                # Transcribe with Faster Whisper
                segments, info = self.whisper_model.transcribe(
                    temp_path,
                    word_timestamps=True,
                    language="en"
                )
                
                # Convert to our segment format
                transcription_segments = []
                for segment in segments:
                    transcription_segments.append(
                        TranscriptionSegment(
                            start=segment.start,
                            end=segment.end,
                            text=segment.text.strip(),
                            confidence=getattr(segment, 'avg_logprob', 1.0)
                        )
                    )
                
                print(f"Transcribed {len(transcription_segments)} segments.")
                return transcription_segments
                
            finally:
                # Clean up temp file
                Path(temp_path).unlink(missing_ok=True)
                
        except Exception as e:
            raise RuntimeError(f"Transcription failed: {str(e)}")
    
    def align_words(
        self, 
        audio_path: Union[str, Path], 
        transcription_segments: List[TranscriptionSegment],
        target_sr: int = 16000
    ) -> List[WordSegment]:
        """
        Get word-level alignments for transcribed segments.
        
        Args:
            audio_path: Path to audio file
            transcription_segments: Transcription segments from transcribe()
            target_sr: Target sample rate
            
        Returns:
            List of word segments with precise timing
        """
        if self.alignment_model is None:
            # Fallback: estimate word timings
            return self._estimate_word_timings(transcription_segments)
        
        try:
            print("Performing word-level alignment...")
            
            # Load audio
            audio, sr = load_audio(audio_path, sr=target_sr, mono=True)
            
            # Prepare transcription for WhisperX
            whisperx_segments = [
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text
                }
                for seg in transcription_segments
            ]
            
            # Perform alignment
            result = whisperx.align(
                whisperx_segments, 
                self.alignment_model, 
                {"language": "en", "sampling_rate": sr},
                audio, 
                device=self.device,
                return_char_alignments=False
            )
            
                # Extract word segments with detailed logging
            word_segments = []
            aligned_words = []
            
            for segment in result.get("segments", []):
                for word_info in segment.get("words", []):
                    if "start" in word_info and "end" in word_info:
                        word_segment = WordSegment(
                            start=word_info["start"],
                            end=word_info["end"],
                            word=word_info["word"],
                            confidence=word_info.get("score", 1.0)
                        )
                        word_segments.append(word_segment)
                        
                        # Log aligned word
                        aligned_words.append({
                            'word': word_info["word"],
                            'start': word_info["start"],
                            'end': word_info["end"],
                            'confidence': word_info.get("score", 1.0),
                            'alignment_method': 'whisperx'
                        })
            
            # Log aligned words
            if aligned_words:
                self._log_aligned_words(aligned_words, str(audio_path))
            print(f"Aligned {len(word_segments)} words.")
            return word_segments
            
        except Exception as e:
            print(f"Warning: Word alignment failed, falling back to estimation: {e}")
            return self._estimate_word_timings(transcription_segments)
    
    def _estimate_word_timings(
        self, 
        segments: List[TranscriptionSegment]
    ) -> List[WordSegment]:
        """
        Improved fallback method for rap-friendly word timing estimation.

        Args:
            segments: Transcription segments
            
        Returns:
            Estimated word segments with better rap timing
        """
        word_segments = []
        
        for segment in segments:
            # Clean up text and split into words
            clean_text = segment.text.strip()
            words = clean_text.split()
            if not words:
                continue
                
            duration = segment.end - segment.start
            
            # RAP-OPTIMIZED timing estimation
            print(f"    🎤 Estimating timing for rap segment: '{clean_text}' ({duration:.2f}s, {len(words)} words)")
            
            # For rap: assume faster delivery, shorter words
            avg_word_duration = duration / len(words)
            
            # Detect if this seems like rapid rap (many short words, long segment)
            is_rapid_rap = (len(words) > 5 and avg_word_duration < 0.8) or avg_word_duration < 0.5
            
            if is_rapid_rap:
                print(f"    ⚡ Detected rapid rap delivery - using compressed timing")
                # For rapid rap: more even distribution, shorter words
                base_word_duration = min(0.6, duration / len(words))
                
                current_time = segment.start
                for i, word in enumerate(words):
                    # Slightly vary word length based on actual word length
                    word_length_factor = len(word) / 6.0  # Normalize to ~6 chars
                    word_duration = base_word_duration * (0.7 + 0.6 * word_length_factor)
                    
                    # Ensure we don't exceed segment boundary
                    if current_time + word_duration > segment.end:
                        word_duration = segment.end - current_time
                    
                    end_time = current_time + word_duration
                    
                    # Clean word and create segment
                    clean_word = word.strip('.,!?;:"()[]')
                    if clean_word:
                        word_segments.append(
                            WordSegment(
                                start=current_time,
                                end=end_time,
                                word=clean_word,
                                confidence=segment.confidence
                            )
                        )
                        print(f"      '{clean_word}': {current_time:.2f}s-{end_time:.2f}s ({word_duration:.2f}s)")
                    
                    current_time = end_time
            else:
                print(f"    🗣️ Standard speech pacing - using proportional timing")
                # Standard timing for slower/clearer speech
                word_lengths = [len(word) for word in words]
                total_chars = sum(word_lengths)
                
                current_time = segment.start
                for i, word in enumerate(words):
                    # Proportional timing based on word length
                    if total_chars > 0:
                        word_duration = (word_lengths[i] / total_chars) * duration
                    else:
                        word_duration = duration / len(words)
                    
                    # Reasonable bounds for word duration
                    word_duration = max(0.15, min(1.5, word_duration))
                    
                    end_time = current_time + word_duration
                    
                    # Clean word of punctuation for better matching
                    clean_word = word.strip('.,!?;:"()[]')
                    if clean_word:  # Only add non-empty words
                        word_segments.append(
                            WordSegment(
                                start=current_time,
                                end=end_time,
                                word=clean_word,
                                confidence=segment.confidence
                            )
                        )
                        print(f"      '{clean_word}': {current_time:.2f}s-{end_time:.2f}s ({word_duration:.2f}s)")
                    
                    current_time = end_time
        
        print(f"    ✅ Estimated timing for {len(word_segments)} words total")
        return word_segments
    
    def _log_transcribed_words(self, words: List[dict], audio_path: str) -> None:
        """
        Log all transcribed words with timestamps to a detailed log file.
        
        Args:
            words: List of word dictionaries with timing info
            audio_path: Path to the audio file being transcribed
        """
        import json
        from datetime import datetime
        from pathlib import Path
        
        # Create logs directory
        logs_dir = Path("data/logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate log filename
        audio_name = Path(audio_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"{audio_name}_transcription_{timestamp}.json"
        
        # Create comprehensive log entry
        log_data = {
            "metadata": {
                "audio_file": str(audio_path),
                "transcription_timestamp": datetime.now().isoformat(),
                "model": self.model_name,
                "device": self.device,
                "total_words": len(words)
            },
            "word_timeline": []
        }
        
        # Add each word with detailed timing
        for i, word_info in enumerate(words):
            clean_word = word_info['word'].strip('.,!?;:"()[]{}"\'’‘“”')
            
            word_entry = {
                "index": i + 1,
                "word": word_info['word'],  # Original word with punctuation
                "clean_word": clean_word,   # Cleaned word for matching
                "start_time": round(word_info['start'], 3),
                "end_time": round(word_info['end'], 3),
                "duration": round(word_info['end'] - word_info['start'], 3),
                "confidence": round(word_info['confidence'], 3),
                "segment_id": word_info.get('segment_id', 0)
            }
            log_data["word_timeline"].append(word_entry)
        
        # Save detailed log
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        print(f"  📋 Word timeline logged: {log_file}")
        
        # Also create a simple text version for easy reading
        text_log = logs_dir / f"{audio_name}_words_{timestamp}.txt"
        with open(text_log, 'w', encoding='utf-8') as f:
            f.write(f"Word Timeline for: {audio_path}\n")
            f.write(f"Transcribed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
            
            for word_info in log_data["word_timeline"]:
                f.write(f"{word_info['index']:3d}. {word_info['start_time']:7.3f}s - {word_info['end_time']:7.3f}s | {word_info['word']:<15} | conf: {word_info['confidence']:.3f}\n")
        
        print(f"  📄 Text timeline saved: {text_log}")
    
    def transcribe_and_align(
        self, 
        audio_path: Union[str, Path], 
        target_sr: int = 16000
    ) -> List[WordSegment]:
        """
        Convenience method to transcribe and align in one step.
        
        Args:
            audio_path: Path to audio file
            target_sr: Target sample rate
            
        Returns:
            List of word segments with timing information
        """
        # First transcribe
        segments = self.transcribe(audio_path, target_sr)
        
        # Then align words
        words = self.align_words(audio_path, segments, target_sr)
        
        return words


def transcribe_audio(
    audio_path: Union[str, Path],
    model: str = "large",
    device: Optional[str] = None,
    target_sr: int = 16000,
    use_rap_preprocessing: bool = False  # Disabled by default - hurts detection accuracy
) -> List[WordSegment]:
    """
    Convenience function to transcribe audio with word-level timing.
    
    Args:
        audio_path: Path to audio file
        model: Whisper model size
        device: Device to use
        target_sr: Target sample rate
        use_rap_preprocessing: Enable rap preprocessing (disabled - reduces detection accuracy)
        
    Returns:
        List of word segments
    """
    transcriber = AudioTranscriber(model, device)
    
    if use_rap_preprocessing:
        print(f"🎤 Using rap-optimized transcription with vocal preprocessing...")
        
        # Apply preprocessing
        audio_path = Path(audio_path)
        processed_path = audio_path.parent / f"{audio_path.stem}_rap_processed.wav"
        
        try:
            # Preprocess vocals for better timing
            processed_audio_path = transcriber._preprocess_for_conversation(audio_path, processed_path)
            
            # Transcribe the processed audio
            word_segments = transcriber.transcribe_and_align(processed_audio_path, target_sr)
            
            # Scale timestamps back to original speed (2x because we slowed by 50%)
            word_segments = transcriber._scale_timestamps_back(word_segments, speed_factor=2.0)
            
            # Clean up temporary file
            try:
                if processed_path.exists():
                    processed_path.unlink()
                    print(f"    🗑️ Cleaned up temporary file")
            except:
                pass
                
            return word_segments
            
        except Exception as e:
            print(f"    ⚠️ Rap preprocessing failed, falling back to standard transcription: {e}")
            # Fall back to standard transcription
            return transcriber.transcribe_and_align(audio_path, target_sr)
    else:
        return transcriber.transcribe_and_align(audio_path, target_sr)
