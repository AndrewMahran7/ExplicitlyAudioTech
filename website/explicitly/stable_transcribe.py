"""
Stable-ts based word-level alignment for production-quality timestamps.

This module uses stable-ts to refine Whisper's word timestamps with VAD,
providing highly accurate synchronization between audio and text.

Installation:
    pip install stable-ts openai-whisper torch soundfile

Dependencies:
    - stable-ts: Improved Whisper timestamping
    - openai-whisper: Base ASR model
    - torch: PyTorch backend
    - soundfile: Audio I/O
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import stable_whisper
    STABLE_TS_AVAILABLE = True
except ImportError:
    STABLE_TS_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class StableTranscriptionError(Exception):
    """Raised when stable-ts transcription fails."""
    pass


def check_dependencies() -> Dict[str, bool]:
    """
    Check if required dependencies are available.
    
    Returns:
        Dictionary with availability status of each dependency
    """
    return {
        "stable_ts": STABLE_TS_AVAILABLE,
        "torch": TORCH_AVAILABLE,
        "cuda": torch.cuda.is_available() if TORCH_AVAILABLE else False
    }


def transcribe_with_stable_ts(
    audio_path: str,
    model_name: str = "small",
    device: str = "auto",
    language: str = "en",
    vad: bool = True,
    demucs: bool = False
) -> Dict[str, Any]:
    """
    Transcribe audio with stable-ts for highly accurate word-level timestamps.
    
    This is the primary transcription function that combines Whisper ASR
    with stable-ts timestamp refinement in a single pass.
    
    Args:
        audio_path: Path to audio file
        model_name: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
        device: Device to use ('cpu', 'cuda', or 'auto')
        language: Language code ('en' for English)
        vad: Use Voice Activity Detection for better timestamps
        demucs: Use Demucs for audio preprocessing (slower but better)
        
    Returns:
        Dictionary with transcription results including word-level timestamps
        
    Raises:
        StableTranscriptionError: If transcription fails or dependencies missing
    """
    if not STABLE_TS_AVAILABLE:
        raise StableTranscriptionError(
            "stable-ts not installed. Run: pip install stable-ts openai-whisper torch soundfile"
        )
    
    if not TORCH_AVAILABLE:
        raise StableTranscriptionError(
            "PyTorch not installed. Run: pip install torch"
        )
    
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise StableTranscriptionError(f"Audio file not found: {audio_path}")
    
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    try:
        model = stable_whisper.load_model(model_name, device=device)
        
        result = model.transcribe(
            str(audio_path),
            language=language,
            vad=vad,
            demucs=demucs,
            word_timestamps=True
        )
        
        return result
        
    except Exception as e:
        raise StableTranscriptionError(f"stable-ts transcription failed: {str(e)}")


def extract_word_segments(result) -> List[Dict[str, Any]]:
    """
    Extract word-level segments from stable-ts result.
    
    Args:
        result: stable-ts transcription result object
        
    Returns:
        List of word segments with start, end, text, and confidence
    """
    word_segments = []
    word_index = 1
    
    for segment in result.segments:
        for word in segment.words:
            word_segments.append({
                "index": word_index,
                "word": word.word.strip(),
                "start": float(word.start),
                "end": float(word.end),
                "confidence": float(word.probability) if hasattr(word, 'probability') else 1.0
            })
            word_index += 1
    
    return word_segments


def extract_sentence_segments(result) -> List[Dict[str, Any]]:
    """
    Extract sentence/segment-level timestamps from stable-ts result.
    
    Args:
        result: stable-ts transcription result object
        
    Returns:
        List of sentence segments with start, end, and text
    """
    sentence_segments = []
    
    for i, segment in enumerate(result.segments, 1):
        sentence_segments.append({
            "index": i,
            "text": segment.text.strip(),
            "start": float(segment.start),
            "end": float(segment.end)
        })
    
    return sentence_segments


def export_to_json(
    result,
    output_path: Optional[str] = None,
    include_words: bool = True,
    include_segments: bool = True
) -> Dict[str, Any]:
    """
    Export stable-ts result to JSON format compatible with frontend.
    
    Args:
        result: stable-ts transcription result object
        output_path: Optional path to save JSON file
        include_words: Include word-level timestamps
        include_segments: Include sentence-level timestamps
        
    Returns:
        Dictionary with complete transcription data
    """
    output = {
        "text": result.text.strip(),
        "language": result.language if hasattr(result, 'language') else "en",
        "duration": float(result.segments[-1].end) if result.segments else 0.0
    }
    
    if include_words:
        output["words"] = extract_word_segments(result)
        output["word_count"] = len(output["words"])
    
    if include_segments:
        output["segments"] = extract_sentence_segments(result)
        output["segment_count"] = len(output["segments"])
    
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
    
    return output


def convert_to_word_segment_objects(result) -> List:
    """
    Convert stable-ts result to WordSegment objects for pipeline compatibility.
    
    Args:
        result: stable-ts transcription result object
        
    Returns:
        List of WordSegment objects
    """
    from .transcribe_align import WordSegment
    
    word_segments = []
    
    for segment in result.segments:
        for word in segment.words:
            word_segments.append(
                WordSegment(
                    word=word.word.strip(),
                    start=float(word.start),
                    end=float(word.end),
                    confidence=float(word.probability) if hasattr(word, 'probability') else 1.0
                )
            )
    
    return word_segments


def transcribe_and_export(
    audio_path: str,
    output_json_path: str,
    model_name: str = "small",
    device: str = "auto",
    vad: bool = True
) -> Dict[str, Any]:
    """
    Complete transcription pipeline: transcribe and export to JSON.
    
    This is a convenience function that combines transcription and export.
    
    Args:
        audio_path: Path to audio file
        output_json_path: Path to save JSON output
        model_name: Whisper model size
        device: Device to use
        vad: Use Voice Activity Detection
        
    Returns:
        Complete transcription data dictionary
    """
    result = transcribe_with_stable_ts(
        audio_path=audio_path,
        model_name=model_name,
        device=device,
        vad=vad
    )
    
    output = export_to_json(
        result=result,
        output_path=output_json_path,
        include_words=True,
        include_segments=True
    )
    
    return output


def align_lyrics_with_audio(
    audio_path: str,
    lyrics: str,
    model_name: str = "base.en",
    device: str = "auto",
    language: str = "en"
) -> Dict[str, Any]:
    """
    Force-align provided lyrics to audio using stable-ts.
    
    This bypasses transcription and uses the user's lyrics as ground truth,
    only using the AI model to find where each word occurs in the audio.
    This gives 100% word accuracy when lyrics are correct.
    
    Args:
        audio_path: Path to audio file
        lyrics: User-provided lyrics text
        model_name: Whisper model for alignment
        device: Device to use ('cpu', 'cuda', or 'auto')
        language: Language code
        
    Returns:
        Alignment result with word-level timestamps from lyrics
        
    Raises:
        StableTranscriptionError: If alignment fails
    """
    if not STABLE_TS_AVAILABLE:
        raise StableTranscriptionError(
            "stable-ts not installed. Run: pip install stable-ts"
        )
    
    if not TORCH_AVAILABLE:
        raise StableTranscriptionError(
            "PyTorch not installed. Run: pip install torch"
        )
    
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise StableTranscriptionError(f"Audio file not found: {audio_path}")
    
    if not lyrics or not lyrics.strip():
        raise StableTranscriptionError("No lyrics provided for alignment")
    
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Detailed logging
    print("\n" + "="*80)
    print("FORCED ALIGNMENT MODE - Using User Lyrics as Ground Truth")
    print("="*80)
    lyrics_word_count = len(lyrics.split())
    lyrics_preview = lyrics[:200] + "..." if len(lyrics) > 200 else lyrics
    print(f"Lyrics length: {len(lyrics)} characters, ~{lyrics_word_count} words")
    print(f"Lyrics preview: {lyrics_preview}")
    print(f"Model: {model_name} | Device: {device}")
    print()
    
    try:
        print(f"[Forced Alignment] Loading model {model_name} on {device}...")
        model = stable_whisper.load_model(model_name, device=device)
        
        print(f"[Forced Alignment] Aligning {len(lyrics.split())} words to audio...")
        print(f"[Forced Alignment] Audio file: {audio_path}")
        result = model.align(
            str(audio_path),
            text=lyrics,
            language=language
        )
        
        # Log alignment results
        total_words = sum(len(segment.words) for segment in result.segments)
        print("\n" + "="*80)
        print("FORCED ALIGNMENT COMPLETE")
        print("="*80)
        print(f"[SUCCESS] Aligned {total_words} words from lyrics to audio")
        print(f"Total segments: {len(result.segments)}")
        if result.segments:
            print(f"Duration: {result.segments[-1].end:.2f}s")
        
        # Show first 10 aligned words as example
        if result.segments and result.segments[0].words:
            print("\nFirst 10 aligned words:")
            word_count = 0
            for segment in result.segments:
                for word in segment.words:
                    if word_count >= 10:
                        break
                    print(f"  {word.start:6.2f}s - {word.end:6.2f}s | '{word.word.strip()}'")
                    word_count += 1
                if word_count >= 10:
                    break
            print()
        
        return result
        
    except Exception as e:
        raise StableTranscriptionError(f"Forced alignment failed: {str(e)}")
