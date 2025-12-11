"""
Lyrics-based transcription correction.

This module improves transcription accuracy by comparing Whisper's output
with user-provided lyrics and correcting misheard words.
"""

from typing import List, Tuple
from difflib import SequenceMatcher
import re

from .transcribe_align import WordSegment


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    # Convert to lowercase
    text = text.lower()
    # Remove punctuation
    text = re.sub(r'[^\w\s]', '', text)
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text


def split_into_words(text: str) -> List[str]:
    """Split text into individual words."""
    normalized = normalize_text(text)
    return normalized.split()


def align_lyrics_to_transcription(
    transcribed_words: List[WordSegment],
    lyrics: str
) -> List[WordSegment]:
    """
    Align user-provided lyrics with transcribed word segments.
    
    Uses sequence matching to align lyrics with Whisper transcription,
    correcting misheard words while preserving timing information.
    
    Args:
        transcribed_words: Word segments from Whisper
        lyrics: User-provided lyrics text
        
    Returns:
        Corrected word segments with lyrics text and original timestamps
    """
    if not lyrics or not transcribed_words:
        return transcribed_words
    
    # Extract words from transcription
    transcribed_text = [seg.word for seg in transcribed_words]
    
    # Split lyrics into words
    lyrics_words = split_into_words(lyrics)
    
    print(f"[Lyrics Alignment] Transcribed: {len(transcribed_text)} words")
    print(f"[Lyrics Alignment] Lyrics: {len(lyrics_words)} words")
    
    # Use sequence matcher to align
    matcher = SequenceMatcher(None, 
                             [normalize_text(w) for w in transcribed_text],
                             lyrics_words)
    
    corrected_segments = []
    lyrics_idx = 0
    
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == 'equal':
            # Words match - use lyrics version with original timing
            for trans_idx in range(i1, i2):
                if lyrics_idx < len(lyrics_words):
                    original = transcribed_words[trans_idx]
                    corrected = WordSegment(
                        word=lyrics_words[lyrics_idx],
                        start=original.start,
                        end=original.end,
                        confidence=original.confidence
                    )
                    corrected_segments.append(corrected)
                    lyrics_idx += 1
                    
        elif opcode == 'replace':
            # Words differ - replace with lyrics
            trans_count = i2 - i1
            lyrics_count = j2 - j1
            
            if trans_count == lyrics_count:
                # Same number of words - direct replacement
                for idx, trans_idx in enumerate(range(i1, i2)):
                    if lyrics_idx < len(lyrics_words):
                        original = transcribed_words[trans_idx]
                        corrected = WordSegment(
                            word=lyrics_words[lyrics_idx],
                            start=original.start,
                            end=original.end,
                            confidence=original.confidence * 0.9  # Slightly lower confidence
                        )
                        corrected_segments.append(corrected)
                        lyrics_idx += 1
            else:
                # Different word counts - distribute timing proportionally
                if trans_count > 0:
                    start_time = transcribed_words[i1].start
                    end_time = transcribed_words[i2-1].end
                    total_duration = end_time - start_time
                    
                    for idx in range(lyrics_count):
                        if lyrics_idx < len(lyrics_words):
                            # Distribute time evenly across lyrics words
                            word_duration = total_duration / lyrics_count
                            word_start = start_time + (idx * word_duration)
                            word_end = word_start + word_duration
                            
                            corrected = WordSegment(
                                word=lyrics_words[lyrics_idx],
                                start=word_start,
                                end=word_end,
                                confidence=0.7  # Lower confidence for estimated timing
                            )
                            corrected_segments.append(corrected)
                            lyrics_idx += 1
                            
        elif opcode == 'delete':
            # Word in transcription but not lyrics - skip it
            pass
            
        elif opcode == 'insert':
            # Word in lyrics but not transcription - estimate timing
            if corrected_segments:
                # Use timing from last word
                last_seg = corrected_segments[-1]
                avg_duration = 0.3  # Average word duration
                
                for idx in range(j2 - j1):
                    if lyrics_idx < len(lyrics_words):
                        corrected = WordSegment(
                            word=lyrics_words[lyrics_idx],
                            start=last_seg.end,
                            end=last_seg.end + avg_duration,
                            confidence=0.5  # Low confidence for inserted words
                        )
                        corrected_segments.append(corrected)
                        lyrics_idx += 1
    
    print(f"[Lyrics Alignment] Corrected: {len(corrected_segments)} words")
    print(f"[Lyrics Alignment] Corrections made: {sum(1 for i, seg in enumerate(corrected_segments) if i < len(transcribed_words) and seg.word != transcribed_words[i].word)}")
    
    return corrected_segments


def compare_transcription_to_lyrics(
    transcribed_words: List[WordSegment],
    lyrics: str
) -> Tuple[List[dict], float]:
    """
    Compare transcription to lyrics and identify differences.
    
    Args:
        transcribed_words: Word segments from Whisper
        lyrics: User-provided lyrics
        
    Returns:
        Tuple of (list of differences, accuracy percentage)
    """
    if not lyrics or not transcribed_words:
        return [], 0.0
    
    transcribed_text = [normalize_text(seg.word) for seg in transcribed_words]
    lyrics_words = split_into_words(lyrics)
    
    matcher = SequenceMatcher(None, transcribed_text, lyrics_words)
    accuracy = matcher.ratio() * 100
    
    differences = []
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == 'replace':
            differences.append({
                'type': 'mismatch',
                'transcribed': ' '.join(transcribed_words[i].word for i in range(i1, i2)),
                'lyrics': ' '.join(lyrics_words[j1:j2]),
                'timestamp': transcribed_words[i1].start if i1 < len(transcribed_words) else 0
            })
        elif opcode == 'delete':
            differences.append({
                'type': 'extra_in_transcription',
                'transcribed': ' '.join(transcribed_words[i].word for i in range(i1, i2)),
                'timestamp': transcribed_words[i1].start if i1 < len(transcribed_words) else 0
            })
        elif opcode == 'insert':
            differences.append({
                'type': 'missing_in_transcription',
                'lyrics': ' '.join(lyrics_words[j1:j2])
            })
    
    return differences, accuracy
