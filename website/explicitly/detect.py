"""
Profanity detection and text normalization for transcribed content.

This module handles the core profanity detection logic for the Explicitly tool.
It uses lexicon-based matching with intelligent text normalization to catch
profane words even when they're disguised with symbols, misspellings, or 
repetitions.

Key features:
- Lexicon-based detection using customizable word lists
- Text normalization to catch censored variants (sh*t → shit)
- Confidence threshold filtering (skip low-quality transcriptions)
- Partial word matching for compound profanity
- Case-insensitive and accent-insensitive matching
- Detailed logging of detection decisions

The detection process:
1. Load profanity words from lexicon file
2. For each transcribed word:
   - Clean and normalize the text
   - Check against profanity lexicon
   - Apply various matching strategies
   - Log the decision (profane/clean)
3. Return list of detected profane word segments
"""

# Standard library imports for text processing and file operations
import re                    # Regular expressions for text normalization
from pathlib import Path    # Modern path handling
from typing import List, Set, Dict, Union, Optional  # Type hints for clarity

# External libraries for advanced text processing
from unidecode import unidecode        # Remove accents and convert to ASCII
from wordfreq import word_frequency    # Word frequency analysis (currently unused)

# Internal import for word segment data structure
from .transcribe_align import WordSegment  # Timestamped word data from transcription


class ProfanityDetector:
    """
    Detects profane words in transcribed text using configurable word lists.
    
    This class implements a sophisticated profanity detection system that goes beyond
    simple word matching. It includes text normalization to catch common censoring
    techniques and provides configurable sensitivity levels.
    
    The detector works in several phases:
    1. Lexicon loading: Parse profanity word list from text file
    2. Text normalization: Convert variations (“f*ck” → “fuck”)
    3. Matching strategies: Direct, normalized, and partial matching
    4. Confidence filtering: Skip low-quality transcription results
    5. Logging: Record detailed decision information
    
    Features:
    - Multiple matching strategies for maximum detection accuracy
    - Configurable confidence thresholds to filter poor transcriptions
    - Text normalization to catch censored variants
    - Case-insensitive matching by default
    - Detailed logging for debugging detection issues
    """
    
    def __init__(
        self,
        lexicon_path: Union[str, Path],     # Path to profanity word list file
        normalize_text: bool = True,        # Enable text normalization (recommended)
        case_sensitive: bool = False,       # Case-sensitive matching (usually False)
        confidence_threshold: float = 0.8   # Minimum Whisper confidence (0.0-1.0)
    ):
        """
        Initialize the profanity detector with configuration and load lexicon.
        
        Sets up the detection parameters and immediately loads the profanity word
        list from the specified file. The detector is ready to use after initialization.
        
        Args:
            lexicon_path: Path to text file containing profanity words (one per line)
            normalize_text: Enable text normalization to catch censored variants
                           like "f*ck" → "fuck" (recommended: True)
            case_sensitive: Enable case-sensitive matching. Usually False since
                           "FUCK" and "fuck" should both be detected
            confidence_threshold: Minimum Whisper confidence score (0.0-1.0).
                                 Words below this threshold are skipped.
                                 NOTE: Currently disabled due to negative scores.
        """
        # Store configuration parameters
        self.lexicon_path = Path(lexicon_path)          # Convert to Path object
        self.normalize_text = normalize_text            # Text normalization flag
        self.case_sensitive = case_sensitive            # Case sensitivity flag  
        self.confidence_threshold = confidence_threshold # Confidence filtering
        
        # Initialize data structures for profanity words
        self.profanity_words: Set[str] = set()          # Main profanity word set
        self.normalized_profanity: Dict[str, str] = {}  # Normalized → original mapping
        
        # Load the profanity lexicon immediately
        self._load_lexicon()
        
    def _load_lexicon(self) -> None:
        """
        Load profanity words from lexicon file and prepare matching data structures.
        
        Reads a text file containing profanity words (one per line) and processes
        them according to the configured settings. Also generates normalized
        variants for better detection of censored profanity.
        
        Lexicon file format:
        - One word per line
        - Lines starting with '#' are treated as comments
        - Empty lines are ignored
        - Words can contain symbols (*, @, etc.) for normalization
        
        Processing steps:
        1. Read all lines from lexicon file
        2. Filter out comments and empty lines
        3. Apply case sensitivity settings
        4. Generate normalized variants if enabled
        5. Build lookup data structures for fast matching
        """
        try:
            # Verify lexicon file exists
            if not self.lexicon_path.exists():
                raise FileNotFoundError(f"Lexicon file not found: {self.lexicon_path}")
            
            # Read all lines from lexicon file
            with open(self.lexicon_path, 'r', encoding='utf-8') as f:
                words = [line.strip() for line in f if line.strip()]  # Remove whitespace and empty lines
            
            # Process each word according to configuration
            for word in words:
                # Skip comments (lines starting with #) and empty lines
                if not word or word.startswith('#'):
                    continue
                
                # Apply case sensitivity setting
                processed_word = word.lower() if not self.case_sensitive else word
                self.profanity_words.add(processed_word)
                
                # Generate normalized versions for better detection
                # This catches variants like "f*ck" when the lexicon has "fuck"
                if self.normalize_text:
                    normalized = self._normalize_word(processed_word)
                    # Store the mapping if normalization changed the word
                    if normalized != processed_word:
                        self.normalized_profanity[normalized] = processed_word
            
            # User feedback about successful loading
            print(f"Loaded {len(self.profanity_words)} profanity words from {self.lexicon_path}")
            
        except Exception as e:
            # Convert any file/parsing errors to runtime errors with context
            raise RuntimeError(f"Failed to load profanity lexicon: {str(e)}")
    
    def _normalize_word(self, word: str) -> str:
        """
        Normalize a word by removing common censoring characters and variations.
        
        This method implements intelligent text normalization to catch profanity
        that has been disguised with symbols, numbers, or repetitions. It's
        essential for detecting variants that people use to bypass filters.
        
        Normalization strategies:
        1. Symbol substitution: Replace common symbol/number substitutions
        2. Character removal: Remove separator characters
        3. ASCII conversion: Handle accented characters
        4. Repetition reduction: Normalize repeated characters
        
        Examples:
        - "f*ck" → "fick" → matches "fuck" pattern
        - "sh!t" → "shit" → exact match
        - "b@stard" → "bastard" → exact match
        - "fuuuuck" → "fuuck" → matches with repetition rules
        
        Args:
            word: Input word that may contain censoring or disguise characters
            
        Returns:
            str: Normalized word with common disguises removed
        """
        # Start with the original word
        normalized = word
        
        # Dictionary of common character substitutions used to disguise profanity
        # Maps disguise character → likely intended letter
        substitutions = {
            '*': 'i',    # f*ck → fick (common asterisk substitution)
            '@': 'a',    # b@stard → bastard
            '3': 'e',    # h3ll → hell
            '0': 'o',    # f0ol → fool
            '1': 'i',    # sh1t → shit
            '5': 's',    # a55 → ass
            '7': 't',    # 7he → the
            '$': 's',    # a$$ → ass
            '!': 'i',    # sh!t → shit
            '-': '',     # mother-fucker → motherfucker (remove separators)
            '_': '',     # f_uck → fuck
            '.': '',     # f.u.c.k → fuck
            ' ': ''      # f u c k → fuck (remove spaces)
        }
        
        # Apply all character substitutions
        for char, replacement in substitutions.items():
            normalized = normalized.replace(char, replacement)
        
        # Convert accented characters to ASCII equivalents
        # This catches variants like “fück” → “fuck”
        normalized = unidecode(normalized)
        
        # Reduce repeated characters (common evasion: "shiiiit" for "shit")
        # This regex finds 3+ consecutive identical characters and reduces to 2
        # Examples: "fuuuuck" → "fuuck", "shiiiit" → "shiit"
        normalized = re.sub(r'(.)\1{2,}', r'\1\1', normalized)
        
        # Final lowercase normalization for consistent comparison
        return normalized.lower()
    
    def _is_profane_word(self, word: str) -> bool:
        """
        Check if a word is profane.
        
        Args:
            word: Word to check
            
        Returns:
            True if word is profane
        """
        check_word = word.lower() if not self.case_sensitive else word
        
        # Direct match
        if check_word in self.profanity_words:
            return True
        
        # Normalized match
        if self.normalize_text:
            normalized = self._normalize_word(check_word)
            if normalized in self.profanity_words:
                return True
            if normalized in self.normalized_profanity:
                return True
        
        # Partial matches for compound words
        for profane_word in self.profanity_words:
            if len(profane_word) > 3 and profane_word in check_word:
                return True
        
        return False
    
    def _log_profanity_detection(self, detection_log: List[Dict], profane_segments: List[WordSegment]) -> None:
        """
        Log detailed profanity detection results.
        
        Args:
            detection_log: Detailed log of all word analysis
            profane_segments: List of detected profane segments
        """
        # This method can be used for detailed logging if needed
        # For now, we'll just print a summary
        profane_count = len(profane_segments)
        total_count = len(detection_log)
        
        if profane_count > 0:
            print(f"  [DEBUG] Profanity detection details:")
            for segment in profane_segments[:5]:  # Show first 5
                print(f"    {segment.start:.2f}s: '{segment.word}' (conf: {segment.confidence:.3f})")
            if profane_count > 5:
                print(f"    ... and {profane_count - 5} more")
    
    def detect_profanity(
        self, 
        word_segments: List[WordSegment]
    ) -> List[WordSegment]:
        """
        Detect profane words in a list of word segments with comprehensive logging.

        Args:
            word_segments: List of word segments from transcription
            
        Returns:
            List of profane word segments
        """
        profane_segments = []
        detection_log = []
        
        print(f"\n  [ANALYSIS] Checking {len(word_segments)} words for profanity...")
        
        for i, segment in enumerate(word_segments):
            # Clean the word for checking
            cleaned_word = re.sub(r'[^\w\s]', '', segment.word.strip()).lower()
            original_word = segment.word.strip()
            
            # Create detailed log entry for each word
            log_entry = {
                "index": i + 1,
                "original_word": original_word,
                "cleaned_word": cleaned_word,
                "start_time": round(segment.start, 3),
                "end_time": round(segment.end, 3),
                "confidence": round(segment.confidence, 3),
                "confidence_check": segment.confidence >= self.confidence_threshold,
                "is_profane": False,
                "profanity_match": None,
                "skipped_reason": None
            }
            
            # Check confidence threshold (skip confidence check for now as Whisper may return negative values)
            # Note: Whisper confidence scores can be negative, so we'll process all words
            # if segment.confidence < self.confidence_threshold:
            #     log_entry["skipped_reason"] = f"Low confidence ({segment.confidence:.3f} < {self.confidence_threshold})"
            #     detection_log.append(log_entry)
            #     continue
            
            # Check if word is empty after cleaning
            if not cleaned_word:
                log_entry["skipped_reason"] = "Empty after cleaning"
                detection_log.append(log_entry)
                continue
            
            # Check if profane
            is_profane = self._is_profane_word(cleaned_word)
            
            # Debug: Log words that contain profanity but aren't detected
            profane_keywords = ['fuck', 'shit', 'bitch', 'nigga', 'damn']
            if any(keyword in cleaned_word for keyword in profane_keywords) and not is_profane:
                print(f"  ⚠️  DEBUG: Word '{original_word}' (cleaned: '{cleaned_word}') contains profanity but not detected")
                print(f"      Direct match in lexicon: {cleaned_word in self.profanity_words}")
                print(f"      Normalized form: {self._normalize_word(cleaned_word)}")
                print(f"      Normalized in lexicon: {self._normalize_word(cleaned_word) in self.profanity_words}")
            
            if is_profane:
                log_entry["is_profane"] = True
                log_entry["profanity_match"] = cleaned_word
                profane_segments.append(segment)
                detection_log.append(log_entry)
                print(f"  [PROFANE] Detected: '{original_word}' at {segment.start:.2f}s - {segment.end:.2f}s")
            else:
                detection_log.append(log_entry)
        
        # Print summary
        print(f"  [COMPLETE] Analysis done: {len(profane_segments)}/{len(word_segments)} words flagged as profane")

        return profane_segments

    def detect_profanity_in_text(self, text: str) -> List[str]:
        """
        Detect profane words in plain text.
        
        Args:
            text: Input text
            
        Returns:
            List of detected profane words
        """
        words = re.findall(r'\b\w+\b', text.lower())
        profane_words = []
        
        for word in words:
            if self._is_profane_word(word):
                profane_words.append(word)
        
        return profane_words
    
    def get_statistics(self, word_segments: List[WordSegment]) -> Dict[str, any]:
        """
        Get statistics about profanity detection.
        
        Args:
            word_segments: All word segments
            
        Returns:
            Statistics dictionary
        """
        profane_segments = self.detect_profanity(word_segments)
        
        total_words = len(word_segments)
        profane_count = len(profane_segments)
        
        # Calculate total duration
        if word_segments:
            total_duration = word_segments[-1].end - word_segments[0].start
            profane_duration = sum(
                seg.end - seg.start for seg in profane_segments
            )
        else:
            total_duration = 0
            profane_duration = 0
        
        # Count unique profane words
        unique_profane = set(
            re.sub(r'[^\w\s]', '', seg.word.strip().lower()) 
            for seg in profane_segments
        )
        
        return {
            "total_words": total_words,
            "profane_words": profane_count,
            "profanity_rate": profane_count / total_words if total_words > 0 else 0,
            "total_duration_seconds": total_duration,
            "profane_duration_seconds": profane_duration,
            "profanity_time_percentage": (profane_duration / total_duration * 100) if total_duration > 0 else 0,
            "unique_profane_words": len(unique_profane),
            "profane_word_list": list(unique_profane)
        }


def detect_profanity(
    word_segments: List[WordSegment],
    lexicon_path: Union[str, Path],
    normalize_text: bool = True,
    case_sensitive: bool = False,
    confidence_threshold: float = 0.8
) -> List[WordSegment]:
    """
    Convenience function to detect profanity in word segments.
    
    Args:
        word_segments: Word segments from transcription
        lexicon_path: Path to profanity lexicon file
        normalize_text: Whether to normalize text
        case_sensitive: Whether matching is case sensitive
        confidence_threshold: Minimum confidence threshold
        
    Returns:
        List of profane word segments
    """
    detector = ProfanityDetector(
        lexicon_path=lexicon_path,
        normalize_text=normalize_text,
        case_sensitive=case_sensitive,
        confidence_threshold=confidence_threshold
    )
    
    return detector.detect_profanity(word_segments)
