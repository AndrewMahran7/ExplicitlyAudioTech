/*
  ==============================================================================

    LyricsAlignment.h
    Created: 10 Dec 2024
    Author: Explicitly Audio Systems

    Lyrics alignment for improved transcription accuracy.
    Fetches lyrics from lyrics.ovh API and aligns with Whisper timestamps.

  ==============================================================================
*/

#pragma once

#include <string>
#include <vector>
#include <algorithm>
#include <cctype>

/**
    Word segment with timing information from Whisper.
*/
struct WordSegment
{
    std::string word;
    double start;       // Start time in seconds
    double end;         // End time in seconds
    double confidence;  // 0.0-1.0
    
    WordSegment(const std::string& w, double s, double e, double c = 1.0)
        : word(w), start(s), end(e), confidence(c) {}
};

/**
    Song metadata from lyrics search.
*/
struct SongInfo
{
    std::string artist;
    std::string title;
    std::string lyrics;
    
    SongInfo() = default;
    SongInfo(const std::string& a, const std::string& t, const std::string& l)
        : artist(a), title(t), lyrics(l) {}
};

/**
    Lyrics fetcher and aligner.
    
    Fetches lyrics from lyrics.ovh API and aligns them with Whisper word timestamps
    using sequence matching algorithm (similar to Python's difflib.SequenceMatcher).
*/
class LyricsAlignment
{
public:
    LyricsAlignment() = default;
    ~LyricsAlignment() = default;
    
    /**
        Fetch lyrics from lyrics.ovh API.
        
        @param artist       Artist name
        @param title        Song title
        @return             Song info with lyrics, or empty if failed
    */
    static SongInfo fetchLyrics(const std::string& artist, const std::string& title);
    
    /**
        Align lyrics with transcribed word segments.
        
        Uses sequence matching to correct misheard words while preserving
        original Whisper timestamps.
        
        @param transcribedWords     Word segments from Whisper
        @param lyrics               User-provided or fetched lyrics
        @return                     Corrected word segments with lyrics text
    */
    static std::vector<WordSegment> alignLyricsToTranscription(
        const std::vector<WordSegment>& transcribedWords,
        const std::string& lyrics
    );
    
    /**
        Normalize text for comparison (lowercase, remove punctuation).
        
        @param text     Input text
        @return         Normalized text
    */
    static std::string normalizeText(const std::string& text);
    
    /**
        Split text into individual words.
        
        @param text     Input text
        @return         Vector of words
    */
    static std::vector<std::string> splitIntoWords(const std::string& text);

private:
    /**
        Calculate edit distance matrix for sequence alignment.
        
        @param seq1     First sequence
        @param seq2     Second sequence
        @return         2D edit distance matrix
    */
    static std::vector<std::vector<int>> calculateEditDistance(
        const std::vector<std::string>& seq1,
        const std::vector<std::string>& seq2
    );
    
    /**
        Backtrack through edit distance matrix to find alignment operations.
        
        @param matrix               Edit distance matrix
        @param seq1                 First sequence
        @param seq2                 Second sequence
        @param transcribedWords     Original word segments with timing
        @return                     Aligned word segments with corrected text
    */
    static std::vector<WordSegment> backtrackAlignment(
        const std::vector<std::vector<int>>& matrix,
        const std::vector<std::string>& seq1,
        const std::vector<std::string>& seq2,
        const std::vector<WordSegment>& transcribedWords
    );
};
