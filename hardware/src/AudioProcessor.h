/*
  ==============================================================================

    AudioProcessor.h
    Created: 12 Dec 2024
    Author: Explicitly Audio Systems

    Core audio processing logic for Orange Pi Zero 3 (4GB RAM).
    Full implementation with all features from desktop version.
    
    No simplifications - complete delay buffering, Whisper processing,
    timestamp refinement, profanity detection, and censorship.

  ==============================================================================
*/

#pragma once

#include <whisper.h>
#include <vector>
#include <atomic>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <string>
#include "ProfanityFilter.h"
#include "VocalFilter.h"
#include "TimestampRefiner.h"
#include "LyricsAlignment.h"

class AudioProcessor
{
public:
    enum class CensorMode
    {
        Reverse,
        Mute
    };
    
    struct Config
    {
        int sampleRate = 48000;
        int channels = 2;
        std::string modelPath;
        std::string profanityLexicon;
        CensorMode censorMode = CensorMode::Reverse;
        bool enableVocalFilter = true;
        bool enableTimestampRefiner = true;
        float initialDelaySeconds = 10.0f;
        float chunkSeconds = 5.0f;
    };
    
    AudioProcessor();
    ~AudioProcessor();
    
    bool initialize(const Config& config);
    bool start();
    void stop();
    
    // Called from audio thread to process samples
    void process(float* inputBuffer, float* outputBuffer, unsigned int frames);
    
    // Runtime configuration
    void setCensorMode(CensorMode mode);
    
    // Statistics
    double getCurrentLatency() const;
    float getBufferFill() const;
    int getProfanityCount() const { return profanityCount.load(); }
    std::string getLastError() const { return lastError; }
    
private:
    Config config;
    std::string lastError;
    
    // Whisper
    whisper_context* whisperCtx = nullptr;
    std::vector<float> audioBuffer16k;  // Resampled audio for Whisper
    
    // Processing components
    ProfanityFilter profanityFilter;
    VocalFilter vocalFilter;
    TimestampRefiner timestampRefiner;
    
    // Delay buffer (full 20 seconds for 4GB RAM)
    std::vector<std::vector<float>> delayBuffer;  // [channel][sample]
    int delayBufferSize = 0;
    std::atomic<int> delayWritePos{0};
    std::atomic<int> delayReadPos{0};
    std::atomic<bool> playbackStarted{false};
    
    // Accumulation buffer for Whisper (5 seconds)
    std::vector<float> audioBuffer;
    std::vector<float> processingBuffer;
    int bufferWritePos = 0;
    int transcriptionInterval = 0;
    double bufferCaptureTime = 0.0;
    
    // Whisper processing thread
    std::thread whisperThread;
    std::atomic<bool> shouldStopThread{false};
    std::atomic<bool> hasNewBuffer{false};
    std::mutex bufferMutex;
    std::condition_variable bufferReady;
    
    // Statistics
    std::atomic<int> profanityCount{0};
    std::atomic<bool> bufferUnderrun{false};
    std::atomic<float> currentInputLevel{0.0f};
    double streamTime = 0.0;
    double lastUnderrunWarningTime = 0.0;
    bool wasWaiting = false;
    int debugCounter = 0;
    
    // Private methods
    void whisperThreadFunction();
    void processTranscription(const std::vector<float>& buffer, double captureTime);
    std::vector<float> resampleTo16kHz(const std::vector<float>& input);
    std::string cleanTranscriptText(const std::string& text);
};
