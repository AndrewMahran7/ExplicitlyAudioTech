"""
Word timeline logging system for Explicitly.

This module provides comprehensive logging of every word found in transcription
with precise timestamps for debugging and analysis purposes. It creates detailed
logs showing:
- Every transcribed word with exact timing
- Which words were detected as profane
- Confidence scores for each word
- Processing stages and statistics
- Multiple output formats (JSON, text timeline, summary report)

The logging system is essential for:
- Debugging why profanity detection might miss certain words
- Analyzing transcription quality and accuracy
- Providing detailed reports to users
- Troubleshooting processing issues
"""

# Standard library imports for data handling and file operations
import json                    # JSON serialization for structured log files
import re                      # Regular expressions for text cleaning
from datetime import datetime  # Timestamp generation for log entries
from pathlib import Path      # Modern path handling for cross-platform compatibility
from typing import List, Dict, Any, Optional  # Type hints for better code documentation

class WordLogger:
    """
    Handles comprehensive logging of word timelines and profanity detection.
    
    This class manages a complete logging session for processing a single audio file.
    It tracks every word that gets transcribed, which ones are detected as profane,
    and generates multiple types of reports for analysis.
    
    The logger maintains state throughout the processing pipeline:
    1. Session start - initialize logging for an audio file
    2. Word transcription - log all words with timestamps as they're found
    3. Profanity detection - mark which words are profane and update statuses
    4. Report generation - create comprehensive logs in multiple formats
    
    Key features:
    - Timeline tracking: Every word with precise start/end times
    - Status tracking: Clean vs profane word classification
    - Confidence tracking: Whisper confidence scores for each word
    - Stage tracking: Which processing step produced each word
    - Multiple outputs: JSON data, human-readable timeline, executive summary
    """
    
    def __init__(self, output_dir: str = "data/logs"):
        """
        Initialize the word logger with output directory and session tracking.
        
        Sets up the logging infrastructure and initializes a clean session state.
        The logger is designed to handle one audio file processing session at a time.
        
        Args:
            output_dir: Directory path where log files will be saved.
                       Defaults to "data/logs" for organized file structure.
        """
        # Set up output directory with automatic creation if it doesn't exist
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)  # Create full path, no error if exists
        
        # Initialize session state - this tracks everything for one audio file processing
        self.current_session = {
            "start_time": datetime.now(),    # When this logging session began
            "audio_file": None,             # Path to the audio file being processed
            "transcribed_words": [],        # List of all transcribed words with timing data
            "detected_profanity": [],       # List of words detected as profane
            "processing_stages": []         # Track which processing steps have been completed
        }
    
    def start_session(self, audio_file: str) -> None:
        """
        Start a new logging session for processing an audio file.
        
        This resets the logger state and begins tracking a new audio file.
        Each audio file gets its own complete logging session with separate
        timestamps, word lists, and processing stage tracking.
        
        Args:
            audio_file: Full path to the audio file being processed
        """
        # Reset session state for new audio file
        self.current_session = {
            "start_time": datetime.now(),    # Timestamp when processing this file began
            "audio_file": audio_file,        # Store the file path for reference in reports
            "transcribed_words": [],         # Will be filled as transcription progresses
            "detected_profanity": [],        # Will be filled when profanity detection runs
            "processing_stages": []          # Track completion of each processing step
        }
        
        # User feedback - show which file we're starting to process
        print(f"[LOG] Started word logging session for: {Path(audio_file).name}")
    
    def log_transcribed_words(self, word_segments: List[Dict], stage: str = "transcription") -> None:
        """
        Log all transcribed words with precise timing information.
        
        This method processes the output from speech recognition (Whisper) and stores
        every word with its timing data. It handles different input formats since
        different parts of the pipeline may pass data in various structures.
        
        The method creates standardized log entries for each word containing:
        - Original word text (as transcribed)
        - Cleaned word text (punctuation removed, lowercase)
        - Precise start and end timestamps
        - Duration calculation
        - Confidence score from Whisper
        - Processing stage identifier
        
        Args:
            word_segments: List of word data from transcription. Can be WordSegment
                          objects, dictionaries, or other formats with word timing.
            stage: Name of the processing stage (e.g., "whisper_transcription",
                  "alignment") for tracking where each word came from.
        """
        # Record this processing stage completion with metadata
        self.current_session["processing_stages"].append({
            "stage": stage,                           # Which processing step this is
            "timestamp": datetime.now().isoformat(), # When this stage completed
            "word_count": len(word_segments)         # How many words were processed
        })
        
        for i, word_data in enumerate(word_segments):
            # Handle different input formats
            if hasattr(word_data, 'to_dict'):
                # WordSegment object
                word_info = word_data.to_dict()
            elif isinstance(word_data, dict):
                # Dictionary
                word_info = word_data
            else:
                # Try to extract basic info
                word_info = {
                    "start": getattr(word_data, 'start', 0),
                    "end": getattr(word_data, 'end', 0),
                    "word": getattr(word_data, 'word', str(word_data)),
                    "confidence": getattr(word_data, 'confidence', 1.0)
                }
            
            # Clean and standardize the word entry
            clean_word = self._clean_word(word_info.get("word", ""))
            
            log_entry = {
                "index": len(self.current_session["transcribed_words"]) + 1,
                "original_word": word_info.get("word", ""),
                "clean_word": clean_word,
                "start_time": round(word_info.get("start", 0), 3),
                "end_time": round(word_info.get("end", 0), 3),
                "duration": round(word_info.get("end", 0) - word_info.get("start", 0), 3),
                "confidence": round(word_info.get("confidence", 1.0), 3),
                "stage": stage,
                "timestamp": datetime.now().isoformat()
            }
            
            self.current_session["transcribed_words"].append(log_entry)
        
        print(f"  [LOG] Logged {len(word_segments)} words from {stage} stage")
    
    def log_profanity_detection(self, profane_words: List[Dict], all_words: List[Dict] = None) -> None:
        """
        Log profanity detection results and update word timeline statuses.
        
        Args:
            profane_words: List of detected profane words
            all_words: Optional list of all analyzed words for context
        """
        detection_time = datetime.now()
        
        # Create set of profane words for quick lookup
        profane_matches = set()
        
        for word_data in profane_words:
            # Handle different input formats
            if hasattr(word_data, 'to_dict'):
                word_info = word_data.to_dict()
            elif isinstance(word_data, dict):
                word_info = word_data
            else:
                word_info = {
                    "start": getattr(word_data, 'start', 0),
                    "end": getattr(word_data, 'end', 0),
                    "word": getattr(word_data, 'word', str(word_data)),
                    "confidence": getattr(word_data, 'confidence', 1.0)
                }
            
            profanity_entry = {
                "word": word_info.get("word", ""),
                "clean_word": self._clean_word(word_info.get("word", "")),
                "start_time": round(word_info.get("start", 0), 3),
                "end_time": round(word_info.get("end", 0), 3),
                "confidence": round(word_info.get("confidence", 1.0), 3),
                "detection_time": detection_time.isoformat()
            }
            
            self.current_session["detected_profanity"].append(profanity_entry)
            
            # Add to profane matches set for timeline update
            clean_word = self._clean_word(word_info.get("word", ""))
            start_time = round(word_info.get("start", 0), 3)
            profane_matches.add((clean_word, start_time))
        
        # Update timeline to mark profane words
        # Use fuzzy time matching since timestamps may have slight differences
        updated_count = 0
        for i, transcribed_word in enumerate(self.current_session["transcribed_words"]):
            word_clean = transcribed_word["clean_word"]
            word_start = transcribed_word["start_time"]
            word_end = transcribed_word["end_time"]
            
            # Check if this word matches a detected profane word
            # Use time window matching (within 0.5 seconds) for robustness
            for prof_word, prof_start in profane_matches:
                time_diff = abs(word_start - prof_start)
                if word_clean == prof_word and time_diff < 0.5:
                    self.current_session["transcribed_words"][i]["is_profane"] = True
                    updated_count += 1
                    break
        
        print(f"  [PROFANE] Logged {len(profane_words)} profane words, updated {updated_count} timeline entries")
    
    def _clean_word(self, word: str) -> str:
        """
        Clean and normalize a word for consistent profanity matching.
        
        This method standardizes word text to improve profanity detection accuracy.
        It removes punctuation that might interfere with lexicon matching and
        converts to lowercase for case-insensitive comparison.
        
        Examples:
        - "Bitch!" → "bitch"
        - "mother-fucking" → "motherfucking"
        - "sh*t" → "sht" (would need further normalization in detect.py)
        
        Args:
            word: Original word text as transcribed by Whisper
            
        Returns:
            str: Cleaned word with punctuation removed and lowercase conversion
        """
        # Handle empty or None input gracefully
        if not word:
            return ""
        
        # Remove all non-word characters (punctuation, symbols) and normalize case
        # This regex keeps only letters, numbers, and whitespace
        cleaned = re.sub(r'[^\w\s]', '', word.strip()).lower()
        return cleaned
    
    def save_session_log(self, include_summary: bool = True) -> Dict[str, str]:
        """
        Save the current session log to files.
        
        Args:
            include_summary: Whether to create summary files
            
        Returns:
            Dictionary of created file paths
        """
        if not self.current_session["audio_file"]:
            print("⚠️  No audio file set for current session")
            return {}
        
        # Generate filenames
        audio_name = Path(self.current_session["audio_file"]).stem
        timestamp = self.current_session["start_time"].strftime("%Y%m%d_%H%M%S")
        
        created_files = {}
        
        # 1. Comprehensive JSON log
        json_file = self.output_dir / f"{audio_name}_complete_log_{timestamp}.json"
        
        complete_log = {
            "metadata": {
                "audio_file": self.current_session["audio_file"],
                "session_start": self.current_session["start_time"].isoformat(),
                "log_generated": datetime.now().isoformat(),
                "total_words": len(self.current_session["transcribed_words"]),
                "profane_words": len(self.current_session["detected_profanity"]),
                "processing_stages": self.current_session["processing_stages"]
            },
            "word_timeline": self.current_session["transcribed_words"],
            "profanity_detections": self.current_session["detected_profanity"]
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(complete_log, f, indent=2, ensure_ascii=False)
        
        created_files["json"] = str(json_file)
        print(f"  [SAVED] Complete log: {json_file}")
        
        # 2. Word timeline text file
        timeline_file = self.output_dir / f"{audio_name}_timeline_{timestamp}.txt"
        
        with open(timeline_file, 'w', encoding='utf-8') as f:
            f.write(f"WORD TIMELINE: {Path(self.current_session['audio_file']).name}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Total Words: {len(self.current_session['transcribed_words'])}\n")
            f.write(f"Profane Words: {len(self.current_session['detected_profanity'])}\n\n")
            
            if self.current_session["detected_profanity"]:
                f.write("PROFANE WORDS DETECTED:\n")
                f.write("-" * 40 + "\n")
                for p in self.current_session["detected_profanity"]:
                    f.write(f"{p['start_time']:7.3f}s - {p['end_time']:7.3f}s | '{p['word']}' (conf: {p['confidence']:.3f})\n")
                f.write("\n")
            
            f.write("COMPLETE WORD TIMELINE:\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'#':<4} {'Time':<15} {'Transcribed':<20} {'Normalized':<15} {'Conf':<6} {'Status':<10}\n")
            f.write("-" * 80 + "\n")
            f.write("Column Explanation:\n")
            f.write("  - Transcribed: What Whisper heard in the audio\n")
            f.write("  - Normalized: Cleaned version used for profanity detection\n")
            f.write("  - Conf: Whisper's confidence score (-∞ to 1.0, higher is better)\n")
            f.write("  - Status: Whether profanity was detected in this word\n")
            f.write("-" * 80 + "\n")
            
            for word in self.current_session["transcribed_words"]:
                # Check if word was marked as profane during detection
                is_profane = word.get("is_profane", False)
                status = "[PROFANE]" if is_profane else "[CLEAN]"
                f.write(
                    f"{word['index']:<4} "
                    f"{word['start_time']:6.3f}-{word['end_time']:<6.3f} "
                    f"{word['original_word']:<20} "
                    f"{word['clean_word']:<15} "
                    f"{word['confidence']:<6.3f} "
                    f"{status}\n"
                )
        
        created_files["timeline"] = str(timeline_file)
        print(f"  [SAVED] Timeline: {timeline_file}")
        
        # 3. Summary report
        if include_summary:
            summary_file = self.output_dir / f"{audio_name}_summary_{timestamp}.txt"
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(f"PROFANITY ANALYSIS SUMMARY\n")
                f.write(f"Audio: {Path(self.current_session['audio_file']).name}\n")
                f.write(f"Analyzed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                
                total_words = len(self.current_session["transcribed_words"])
                profane_count = len(self.current_session["detected_profanity"])
                clean_count = total_words - profane_count
                
                f.write(f"📊 STATISTICS:\n")
                f.write(f"  Total words transcribed: {total_words}\n")
                f.write(f"  Clean words: {clean_count}\n")
                f.write(f"  Profane words: {profane_count}\n")
                
                if total_words > 0:
                    profanity_rate = (profane_count / total_words) * 100
                    f.write(f"  Profanity rate: {profanity_rate:.2f}%\n")
                
                f.write("\n")
                
                if profane_count > 0:
                    f.write(f"[PROFANE] PROFANE CONTENT DETECTED:\n")
                    total_duration = sum(p['end_time'] - p['start_time'] for p in self.current_session["detected_profanity"])
                    f.write(f"  Total profane duration: {total_duration:.2f} seconds\n")
                    
                    f.write(f"\n  Profane words by timestamp:\n")
                    for p in sorted(self.current_session["detected_profanity"], key=lambda x: x['start_time']):
                        f.write(f"    {p['start_time']:7.3f}s: '{p['word']}'\n")
                else:
                    f.write(f"[CLEAN] NO PROFANITY DETECTED\n")
                    f.write(f"   This audio appears to be clean!\n")
            
            created_files["summary"] = str(summary_file)
            print(f"  [SAVED] Summary: {summary_file}")
        
        return created_files
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get statistics for the current session.
        
        Returns:
            Dictionary with session statistics
        """
        total_words = len(self.current_session["transcribed_words"])
        profane_words = len(self.current_session["detected_profanity"])
        
        if total_words > 0:
            profanity_rate = (profane_words / total_words) * 100
        else:
            profanity_rate = 0
        
        return {
            "total_words": total_words,
            "clean_words": total_words - profane_words,
            "profane_words": profane_words,
            "profanity_rate_percent": round(profanity_rate, 2),
            "session_start": self.current_session["start_time"].isoformat(),
            "audio_file": self.current_session["audio_file"]
        }


# Global logger instance
_word_logger = None

def get_word_logger() -> WordLogger:
    """Get the global word logger instance."""
    global _word_logger
    if _word_logger is None:
        _word_logger = WordLogger()
    return _word_logger

def log_words(word_segments: List, stage: str = "transcription") -> None:
    """Convenience function to log words."""
    logger = get_word_logger()
    logger.log_transcribed_words(word_segments, stage)

def log_profanity(profane_words: List) -> None:
    """Convenience function to log profanity detection."""
    logger = get_word_logger()
    logger.log_profanity_detection(profane_words)

def start_logging_session(audio_file: str) -> None:
    """Start a new logging session."""
    logger = get_word_logger()
    logger.start_session(audio_file)

def save_logs(include_summary: bool = True) -> Dict[str, str]:
    """Save current session logs."""
    logger = get_word_logger()
    return logger.save_session_log(include_summary)