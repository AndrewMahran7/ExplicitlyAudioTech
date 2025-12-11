/*
  ==============================================================================

    AudioEngine.h
    Created: 9 Dec 2024
    Author: Explicitly Audio Systems

    Lock-free real-time audio processing engine.
    
    Responsibilities:
    - Capture audio from input device
    - Write to 300ms circular buffer
    - Push audio chunks to ASR thread via lock-free queue
    - Apply censorship based on ASR results
    - Output filtered audio to speakers
    
    Thread Safety:
    - audioDeviceIOCallback runs on real-time thread (no allocations, no locks)
    - Uses lock-free queues for ASR communication

  ==============================================================================
*/

#pragma once

#include <juce_audio_devices/juce_audio_devices.h>
#include <whisper.h>
#include <atomic>
#include <vector>
#include <thread>
#include "QualityAnalyzer.h"
#include <mutex>
#include <condition_variable>
#include "ProfanityFilter.h"
#include "LyricsAlignment.h"
#include "VocalFilter.h"
#include "TimestampRefiner.h"
#include "Types.h"

class AudioEngine : public juce::AudioIODeviceCallback
{
public:
    enum class CensorMode
    {
        Reverse,
        Mute
    };
    
    AudioEngine();
    ~AudioEngine() override;
    
    /**
        Start audio processing.
        
        @param inputDeviceName      Input device name (microphone, line-in)
        @param outputDeviceName     Output device name (speakers, headphones)
        @param mode                 Censorship mode (Reverse or Mute)
        @return                     true if started successfully
    */
    bool start(const juce::String& inputDeviceName,
               const juce::String& outputDeviceName,
               CensorMode mode);
    
    /**
        Stop audio processing.
    */
    void stop();
    
    /**
        Get current estimated latency in milliseconds.
        
        @return     Latency in ms, or -1.0 if not processing
    */
    double getCurrentLatency() const;
    
    /**
        Get current buffer capacity in seconds.
        
        Buffer starts at 5.1s and grows as processing accumulates (RTF < 1.0x).
        
        @return     Buffer size in seconds
    */
    double getCurrentBufferSize() const;
    
    /**
        Check if buffer is in underrun state (< 3 seconds).
        
        When buffer underruns, censorship is temporarily disabled to prevent glitches.
        
        @return     true if buffer is critically low
    */
    bool isBufferUnderrun() const;
    
    /**
        Phase 1: Get current input level (RMS).
        
        @return     RMS level 0.0-1.0
    */
    float getCurrentInputLevel() const;
    
    /**
        Get audio device manager (for device enumeration).
    */
    juce::AudioDeviceManager& getDeviceManager() { return deviceManager; }
    
    /**
        Get last error message.
    */
    juce::String getLastError() const { return lastError; }
    
    /**
        Phase 8: Get quality analyzer for statistics.
    */
    QualityAnalyzer& getQualityAnalyzer() { return qualityAnalyzer; }
    
    /**
        Set debug callback for UI updates.
    */
    void setDebugCallback(std::function<void(const juce::String&)> callback) 
    { 
        debugCallback = callback; 
    }
    
    /**
        Set lyrics callback for live display.
    */
    void setLyricsCallback(std::function<void(const juce::String&)> callback)
    {
        lyricsCallback = callback;
    }
    
    /**
        Set song info to fetch lyrics automatically.
        
        @param artist   Artist name
        @param title    Song title
        @return         true if lyrics fetched successfully
    */
    bool setSongInfo(const std::string& artist, const std::string& title);
    
    /**
        Set lyrics manually (skip API fetch).
        
        @param lyrics   Song lyrics text
    */
    void setManualLyrics(const std::string& lyrics);
    
    // AudioIODeviceCallback interface
    void audioDeviceIOCallbackWithContext(const float* const* inputChannelData,
                                         int numInputChannels,
                                         float* const* outputChannelData,
                                         int numOutputChannels,
                                         int numSamples,
                                         const juce::AudioIODeviceCallbackContext& context) override;
    
    void audioDeviceAboutToStart(juce::AudioIODevice* device) override;
    void audioDeviceStopped() override;

private:
    juce::AudioDeviceManager deviceManager;
    
    // Simple level tracking for Phase 1-2
    std::atomic<float> currentInputLevel {0.0f};
    
    // Phase 5: Whisper integration with background thread
    whisper_context* whisperCtx = nullptr;
    std::vector<float> audioBuffer;          // Accumulation buffer (audio callback writes here)
    std::vector<float> processingBuffer;     // Copy for background thread to process
    std::vector<float> audioBuffer16k;
    int bufferWritePos = 0;
    int transcriptionInterval = 0;
    ProfanityFilter profanityFilter;
    VocalFilter vocalFilter;
    TimestampRefiner timestampRefiner;  // Phase 6: Accurate timestamp refinement
    
    // Phase 6: Delay buffer for censorship (15 seconds to allow pipelined Whisper processing)
    std::vector<std::vector<float>> delayBuffer;  // Ring buffer for delayed audio
    int delayBufferSize = 0;                      // Size in samples (15 seconds)
    std::atomic<int> delayWritePos {0};           // Current write position in delay buffer (atomic for thread safety)
    std::atomic<int> delayReadPos {0};            // Current read position in delay buffer (atomic for thread safety)
    
    // Lyrics alignment
    std::string songLyrics;
    bool useLyricsAlignment = false;
    
    // Phase 6: Censorship
    double streamTime = 0.0;                // Current playback time in seconds
    CensorMode currentCensorMode = CensorMode::Mute;
    
    // Phase 8: Quality Analysis
    QualityAnalyzer qualityAnalyzer;
    std::atomic<bool> bufferUnderrun {false};  // Emergency flag: buffer critically low
    std::atomic<bool> playbackStarted {false};  // Track when 10s buffer filled and playback begins
    double lastUnderrunWarningTime = 0.0;      // Throttle warning messages
    
    // Phase 5: Threading
    std::thread whisperThread;
    std::mutex bufferMutex;
    std::condition_variable bufferReady;
    std::atomic<bool> shouldStopThread {false};
    std::atomic<bool> hasNewBuffer {false};
    double bufferCaptureTime = 0.0;  // When the current processing buffer was captured
    
    int sampleRate = 48000;
    int numChannels = 2;
    
    bool isRunning = false;
    juce::String lastError;
    std::function<void(const juce::String&)> debugCallback;
    std::function<void(const juce::String&)> lyricsCallback;
    
    // Phase 5 methods
    void whisperThreadFunction();
    void processTranscription(const std::vector<float>& buffer, double captureTime);
    std::vector<float> resampleTo16kHz(const std::vector<float>& input);

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (AudioEngine)
};
