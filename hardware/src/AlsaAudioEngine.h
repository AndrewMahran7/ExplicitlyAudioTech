/*
  ==============================================================================

    AlsaAudioEngine.h
    Created: 12 Dec 2024
    Author: Explicitly Audio Systems

    ALSA-based audio engine for Orange Pi Zero 3 (headless Linux).
    
    Replaces JUCE audio I/O with direct ALSA API calls for minimal overhead.
    Maintains lock-free design from desktop version.
    
    Thread Safety:
    - Audio callback runs on ALSA real-time thread
    - Uses lock-free communication with Whisper processing thread

  ==============================================================================
*/

#pragma once

#include <alsa/asoundlib.h>
#include <atomic>
#include <thread>
#include <vector>
#include <functional>
#include <string>
#include <memory>

class AlsaAudioEngine
{
public:
    enum class CensorMode
    {
        Reverse,
        Mute
    };
    
    struct Config
    {
        std::string inputDevice = "hw:1,0";    // USB audio input
        std::string outputDevice = "hw:1,0";   // USB audio output
        unsigned int sampleRate = 48000;
        unsigned int channels = 2;
        unsigned int periodSize = 512;         // Buffer size in frames
        unsigned int periods = 4;              // Number of periods (buffers)
        CensorMode censorMode = CensorMode::Reverse;
        std::string modelPath = "/usr/share/explicitly/models/ggml-tiny.en.bin";
        std::string profanityLexicon = "/usr/share/explicitly/profanity_en.txt";
        bool enableVocalFilter = true;
        bool enableTimestampRefiner = true;
    };
    
    /**
        Callback for status updates (e.g., for HTTP API).
    */
    using StatusCallback = std::function<void(const std::string& status, const std::string& details)>;
    
    AlsaAudioEngine();
    ~AlsaAudioEngine();
    
    /**
        Initialize with configuration.
        
        @param config       Configuration structure
        @return            true if initialization succeeded
    */
    bool initialize(const Config& config);
    
    /**
        Start audio processing.
        
        @return     true if started successfully
    */
    bool start();
    
    /**
        Stop audio processing.
    */
    void stop();
    
    /**
        Check if engine is currently running.
    */
    bool isRunning() const { return running.load(); }
    
    /**
        Get current latency in milliseconds.
    */
    double getCurrentLatency() const;
    
    /**
        Get current buffer fill percentage (0.0 - 1.0).
    */
    float getBufferFill() const;
    
    /**
        Get current CPU usage estimate (0.0 - 1.0).
    */
    float getCpuUsage() const;
    
    /**
        Get total profanity detections since start.
    */
    int getProfanityCount() const { return profanityCount.load(); }
    
    /**
        Get current memory usage in MB.
    */
    float getMemoryUsageMB() const;
    
    /**
        Set callback for status updates.
    */
    void setStatusCallback(StatusCallback callback) { statusCallback = callback; }
    
    /**
        Change censor mode at runtime.
    */
    void setCensorMode(CensorMode mode);
    
    /**
        Get last error message.
    */
    std::string getLastError() const { return lastError; }

private:
    // ALSA handles
    snd_pcm_t* captureHandle = nullptr;
    snd_pcm_t* playbackHandle = nullptr;
    
    // Configuration
    Config config;
    
    // Thread control
    std::atomic<bool> running{false};
    std::atomic<bool> shouldStop{false};
    std::unique_ptr<std::thread> audioThread;
    
    // Processing components (forward declarations)
    class AudioProcessor;
    std::unique_ptr<AudioProcessor> processor;
    
    // Statistics
    std::atomic<int> profanityCount{0};
    std::atomic<float> cpuUsage{0.0f};
    
    // Status
    std::string lastError;
    StatusCallback statusCallback;
    
    // Private methods
    bool openAlsaDevice(const std::string& deviceName, snd_pcm_stream_t stream, 
                       snd_pcm_t** handle, unsigned int sampleRate, 
                       unsigned int channels, unsigned int periodSize);
    void audioThreadFunc();
    void processAudio(float* inputBuffer, float* outputBuffer, unsigned int frames);
    void closeAlsaDevices();
    void reportStatus(const std::string& status, const std::string& details);
};
