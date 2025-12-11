/*
  ==============================================================================

    LyricsAlignment.cpp
    Created: 10 Dec 2024
    Author: Explicitly Audio Systems

    Implementation of lyrics fetching and alignment.

  ==============================================================================
*/

#include "LyricsAlignment.h"
#include <juce_core/juce_core.h>
#include <iostream>
#include <sstream>
#include <regex>
#include <algorithm>

// Normalize text: lowercase, remove punctuation, trim whitespace
std::string LyricsAlignment::normalizeText(const std::string& text)
{
    std::string result = text;
    
    // Convert to lowercase
    std::transform(result.begin(), result.end(), result.begin(), ::tolower);
    
    // Remove punctuation (keep only alphanumeric and spaces)
    result.erase(std::remove_if(result.begin(), result.end(), 
        [](char c) { return !std::isalnum(c) && !std::isspace(c); }), result.end());
    
    // Remove extra whitespace
    std::istringstream iss(result);
    std::string word;
    std::vector<std::string> words;
    while (iss >> word)
        words.push_back(word);
    
    result.clear();
    for (size_t i = 0; i < words.size(); ++i)
    {
        if (i > 0) result += " ";
        result += words[i];
    }
    
    return result;
}

// Split text into individual words
std::vector<std::string> LyricsAlignment::splitIntoWords(const std::string& text)
{
    std::string normalized = normalizeText(text);
    std::istringstream iss(normalized);
    std::string word;
    std::vector<std::string> words;
    
    while (iss >> word)
        words.push_back(word);
    
    return words;
}

// Fetch lyrics from lyrics.ovh API
SongInfo LyricsAlignment::fetchLyrics(const std::string& artist, const std::string& title)
{
    std::cout << "[Lyrics] Fetching lyrics for: " << artist << " - " << title << std::endl;
    
    // URL encode artist and title
    juce::String encodedArtist = juce::URL::addEscapeChars(artist, false);
    juce::String encodedTitle = juce::URL::addEscapeChars(title, false);
    
    // Build API URL
    juce::String apiUrl = "https://api.lyrics.ovh/v1/" + encodedArtist + "/" + encodedTitle;
    juce::URL url(apiUrl);
    
    std::cout << "[Lyrics] Request URL: " << apiUrl << std::endl;
    
    // Make HTTP request with timeout
    juce::URL::InputStreamOptions options = juce::URL::InputStreamOptions(juce::URL::ParameterHandling::inAddress)
        .withConnectionTimeoutMs(10000)
        .withNumRedirectsToFollow(5);
    
    std::unique_ptr<juce::InputStream> stream = url.createInputStream(options);
    
    if (!stream)
    {
        std::cout << "[Lyrics] Failed to connect to API" << std::endl;
        return SongInfo();
    }
    
    // Read response
    juce::String response = stream->readEntireStreamAsString();
    
    if (response.isEmpty())
    {
        std::cout << "[Lyrics] Empty response from API" << std::endl;
        return SongInfo();
    }
    
    // Parse JSON response
    juce::var json = juce::JSON::parse(response);
    
    if (!json.isObject())
    {
        std::cout << "[Lyrics] Invalid JSON response" << std::endl;
        return SongInfo();
    }
    
    // Extract lyrics
    juce::var lyricsVar = json["lyrics"];
    
    if (lyricsVar.isVoid())
    {
        std::cout << "[Lyrics] No lyrics found in response" << std::endl;
        return SongInfo();
    }
    
    std::string lyrics = lyricsVar.toString().toStdString();
    
    if (lyrics.empty())
    {
        std::cout << "[Lyrics] Lyrics field is empty" << std::endl;
        return SongInfo();
    }
    
    std::cout << "[Lyrics] Successfully fetched " << lyrics.length() << " characters" << std::endl;
    
    return SongInfo(artist, title, lyrics);
}

// Calculate edit distance matrix using dynamic programming
std::vector<std::vector<int>> LyricsAlignment::calculateEditDistance(
    const std::vector<std::string>& seq1,
    const std::vector<std::string>& seq2)
{
    int m = seq1.size();
    int n = seq2.size();
    
    // Create matrix (m+1) x (n+1)
    std::vector<std::vector<int>> matrix(m + 1, std::vector<int>(n + 1, 0));
    
    // Initialize first row and column
    for (int i = 0; i <= m; ++i)
        matrix[i][0] = i;
    for (int j = 0; j <= n; ++j)
        matrix[0][j] = j;
    
    // Fill matrix using dynamic programming
    for (int i = 1; i <= m; ++i)
    {
        for (int j = 1; j <= n; ++j)
        {
            if (seq1[i-1] == seq2[j-1])
            {
                // Words match - no cost
                matrix[i][j] = matrix[i-1][j-1];
            }
            else
            {
                // Words differ - take minimum of insert, delete, replace
                matrix[i][j] = 1 + std::min({
                    matrix[i-1][j],     // Delete
                    matrix[i][j-1],     // Insert
                    matrix[i-1][j-1]    // Replace
                });
            }
        }
    }
    
    return matrix;
}

// Backtrack through edit distance matrix to create aligned segments
std::vector<WordSegment> LyricsAlignment::backtrackAlignment(
    const std::vector<std::vector<int>>& matrix,
    const std::vector<std::string>& transcribedWords,
    const std::vector<std::string>& lyricsWords,
    const std::vector<WordSegment>& originalSegments)
{
    std::vector<WordSegment> correctedSegments;
    
    int i = transcribedWords.size();
    int j = lyricsWords.size();
    
    // Backtrack from bottom-right to top-left
    std::vector<std::pair<int, int>> alignments;  // (transcribed_idx, lyrics_idx)
    
    while (i > 0 || j > 0)
    {
        if (i > 0 && j > 0 && transcribedWords[i-1] == lyricsWords[j-1])
        {
            // Match - use this alignment
            alignments.push_back({i-1, j-1});
            i--; j--;
        }
        else if (i > 0 && j > 0 && matrix[i][j] == matrix[i-1][j-1] + 1)
        {
            // Replace - align these positions
            alignments.push_back({i-1, j-1});
            i--; j--;
        }
        else if (j > 0 && matrix[i][j] == matrix[i][j-1] + 1)
        {
            // Insert from lyrics - create estimated timing
            alignments.push_back({-1, j-1});
            j--;
        }
        else if (i > 0)
        {
            // Delete from transcription - skip this word
            i--;
        }
    }
    
    // Reverse alignments (we backtracked from end to start)
    std::reverse(alignments.begin(), alignments.end());
    
    // Create corrected segments
    for (const auto& [trans_idx, lyrics_idx] : alignments)
    {
        if (trans_idx >= 0 && lyrics_idx >= 0)
        {
            // Use timing from transcribed word, text from lyrics
            const WordSegment& original = originalSegments[trans_idx];
            correctedSegments.emplace_back(
                lyricsWords[lyrics_idx],
                original.start,
                original.end,
                original.confidence * 0.95  // Slightly lower confidence for corrections
            );
        }
        else if (lyrics_idx >= 0)
        {
            // Lyrics word not in transcription - estimate timing
            double estimatedStart = 0.0;
            double estimatedEnd = 0.3;  // Average word duration
            
            if (!correctedSegments.empty())
            {
                estimatedStart = correctedSegments.back().end;
                estimatedEnd = estimatedStart + 0.3;
            }
            
            correctedSegments.emplace_back(
                lyricsWords[lyrics_idx],
                estimatedStart,
                estimatedEnd,
                0.5  // Low confidence for estimated timing
            );
        }
    }
    
    return correctedSegments;
}

// Main alignment function
std::vector<WordSegment> LyricsAlignment::alignLyricsToTranscription(
    const std::vector<WordSegment>& transcribedWords,
    const std::string& lyrics)
{
    if (lyrics.empty() || transcribedWords.empty())
    {
        std::cout << "[Lyrics Alignment] Empty input - returning original transcription" << std::endl;
        return transcribedWords;
    }
    
    // Extract normalized words from transcription
    std::vector<std::string> transcribedText;
    for (const auto& seg : transcribedWords)
        transcribedText.push_back(normalizeText(seg.word));
    
    // Split lyrics into normalized words
    std::vector<std::string> lyricsWords = splitIntoWords(lyrics);
    
    std::cout << "[Lyrics Alignment] Transcribed: " << transcribedText.size() << " words" << std::endl;
    std::cout << "[Lyrics Alignment] Lyrics: " << lyricsWords.size() << " words" << std::endl;
    
    if (lyricsWords.empty())
    {
        std::cout << "[Lyrics Alignment] No valid words in lyrics" << std::endl;
        return transcribedWords;
    }
    
    // Calculate edit distance matrix
    std::vector<std::vector<int>> matrix = calculateEditDistance(transcribedText, lyricsWords);
    
    // Backtrack to create aligned segments
    std::vector<WordSegment> correctedSegments = backtrackAlignment(
        matrix, transcribedText, lyricsWords, transcribedWords
    );
    
    std::cout << "[Lyrics Alignment] Corrected: " << correctedSegments.size() << " words" << std::endl;
    
    // Count corrections
    int corrections = 0;
    for (size_t i = 0; i < std::min(correctedSegments.size(), transcribedWords.size()); ++i)
    {
        if (normalizeText(correctedSegments[i].word) != normalizeText(transcribedWords[i].word))
            corrections++;
    }
    
    std::cout << "[Lyrics Alignment] Corrections made: " << corrections << std::endl;
    
    return correctedSegments;
}
