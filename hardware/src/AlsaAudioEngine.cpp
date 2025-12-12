/*
  ==============================================================================

    AlsaAudioEngine.cpp
    Created: 12 Dec 2024
    Author: Explicitly Audio Systems

    ALSA audio engine implementation for Orange Pi Zero 3.

  ==============================================================================
*/

#include "AlsaAudioEngine.h"
#include "AudioProcessor.h"
#include <iostream>
#include <cstring>
#include <chrono>
#include <fstream>

AlsaAudioEngine::AlsaAudioEngine()
{
}

AlsaAudioEngine::~AlsaAudioEngine()
{
    stop();
    closeAlsaDevices();
}

bool AlsaAudioEngine::initialize(const Config& cfg)
{
    config = cfg;
    
    // Open input device
    if (!openAlsaDevice(config.inputDevice, SND_PCM_STREAM_CAPTURE, 
                       &captureHandle, config.sampleRate, 
                       config.channels, config.periodSize))
    {
        lastError = "Failed to open ALSA capture device: " + config.inputDevice;
        return false;
    }
    
    // Open output device
    if (!openAlsaDevice(config.outputDevice, SND_PCM_STREAM_PLAYBACK, 
                       &playbackHandle, config.sampleRate, 
                       config.channels, config.periodSize))
    {
        lastError = "Failed to open ALSA playback device: " + config.outputDevice;
        closeAlsaDevices();
        return false;
    }
    
    // Initialize audio processor
    processor = std::make_unique<AudioProcessor>();
    AudioProcessor::Config procConfig;
    procConfig.sampleRate = config.sampleRate;
    procConfig.channels = config.channels;
    procConfig.modelPath = config.modelPath;
    procConfig.profanityLexicon = config.profanityLexicon;
    procConfig.censorMode = (config.censorMode == CensorMode::Reverse) 
                           ? AudioProcessor::CensorMode::Reverse 
                           : AudioProcessor::CensorMode::Mute;
    procConfig.enableVocalFilter = config.enableVocalFilter;
    procConfig.enableTimestampRefiner = config.enableTimestampRefiner;
    
    if (!processor->initialize(procConfig))
    {
        lastError = "Failed to initialize audio processor: " + processor->getLastError();
        closeAlsaDevices();
        return false;
    }
    
    reportStatus("initialized", "ALSA engine ready");
    return true;
}

bool AlsaAudioEngine::start()
{
    if (running.load())
    {
        lastError = "Already running";
        return false;
    }
    
    if (!captureHandle || !playbackHandle || !processor)
    {
        lastError = "Not initialized - call initialize() first";
        return false;
    }
    
    shouldStop.store(false);
    running.store(true);
    
    // Start processor
    processor->start();
    
    // Launch audio thread
    audioThread = std::make_unique<std::thread>(&AlsaAudioEngine::audioThreadFunc, this);
    
    // Set thread priority (requires CAP_SYS_NICE or running as root)
    struct sched_param param;
    param.sched_priority = 80; // High priority for real-time audio
    if (pthread_setschedparam(audioThread->native_handle(), SCHED_FIFO, &param) != 0)
    {
        std::cerr << "Warning: Could not set real-time thread priority. "
                  << "Run as root or grant CAP_SYS_NICE capability for best performance." << std::endl;
    }
    
    reportStatus("started", "Audio processing active");
    return true;
}

void AlsaAudioEngine::stop()
{
    if (!running.load())
        return;
    
    shouldStop.store(true);
    
    if (audioThread && audioThread->joinable())
        audioThread->join();
    
    if (processor)
        processor->stop();
    
    running.store(false);
    reportStatus("stopped", "Audio processing halted");
}

bool AlsaAudioEngine::openAlsaDevice(const std::string& deviceName, 
                                     snd_pcm_stream_t stream,
                                     snd_pcm_t** handle, 
                                     unsigned int sampleRate,
                                     unsigned int channels, 
                                     unsigned int periodSize)
{
    int err;
    
    // Open PCM device
    err = snd_pcm_open(handle, deviceName.c_str(), stream, 0);
    if (err < 0)
    {
        std::cerr << "Cannot open ALSA device " << deviceName << ": " 
                  << snd_strerror(err) << std::endl;
        return false;
    }
    
    // Allocate hardware parameters
    snd_pcm_hw_params_t* hwParams;
    snd_pcm_hw_params_alloca(&hwParams);
    
    // Initialize parameters
    err = snd_pcm_hw_params_any(*handle, hwParams);
    if (err < 0)
    {
        std::cerr << "Cannot initialize hardware parameters: " 
                  << snd_strerror(err) << std::endl;
        return false;
    }
    
    // Set access type to interleaved
    err = snd_pcm_hw_params_set_access(*handle, hwParams, SND_PCM_ACCESS_RW_INTERLEAVED);
    if (err < 0)
    {
        std::cerr << "Cannot set access type: " << snd_strerror(err) << std::endl;
        return false;
    }
    
    // Set sample format (32-bit float)
    err = snd_pcm_hw_params_set_format(*handle, hwParams, SND_PCM_FORMAT_FLOAT);
    if (err < 0)
    {
        std::cerr << "Cannot set sample format: " << snd_strerror(err) << std::endl;
        return false;
    }
    
    // Set sample rate
    unsigned int actualRate = sampleRate;
    err = snd_pcm_hw_params_set_rate_near(*handle, hwParams, &actualRate, 0);
    if (err < 0 || actualRate != sampleRate)
    {
        std::cerr << "Cannot set sample rate to " << sampleRate 
                  << " (got " << actualRate << "): " << snd_strerror(err) << std::endl;
        return false;
    }
    
    // Set channel count
    err = snd_pcm_hw_params_set_channels(*handle, hwParams, channels);
    if (err < 0)
    {
        std::cerr << "Cannot set channel count: " << snd_strerror(err) << std::endl;
        return false;
    }
    
    // Set period size
    snd_pcm_uframes_t actualPeriodSize = periodSize;
    err = snd_pcm_hw_params_set_period_size_near(*handle, hwParams, &actualPeriodSize, 0);
    if (err < 0)
    {
        std::cerr << "Cannot set period size: " << snd_strerror(err) << std::endl;
        return false;
    }
    
    // Set buffer size (4 periods)
    snd_pcm_uframes_t bufferSize = periodSize * config.periods;
    err = snd_pcm_hw_params_set_buffer_size_near(*handle, hwParams, &bufferSize);
    if (err < 0)
    {
        std::cerr << "Cannot set buffer size: " << snd_strerror(err) << std::endl;
        return false;
    }
    
    // Apply hardware parameters
    err = snd_pcm_hw_params(*handle, hwParams);
    if (err < 0)
    {
        std::cerr << "Cannot apply hardware parameters: " << snd_strerror(err) << std::endl;
        return false;
    }
    
    // Prepare device
    err = snd_pcm_prepare(*handle);
    if (err < 0)
    {
        std::cerr << "Cannot prepare device: " << snd_strerror(err) << std::endl;
        return false;
    }
    
    std::cout << "ALSA device " << deviceName << " opened successfully: "
              << sampleRate << "Hz, " << channels << " channels, "
              << periodSize << " frames per period" << std::endl;
    
    return true;
}

void AlsaAudioEngine::audioThreadFunc()
{
    const size_t bufferSizeFrames = config.periodSize;
    const size_t bufferSizeSamples = bufferSizeFrames * config.channels;
    
    std::vector<float> inputBuffer(bufferSizeSamples);
    std::vector<float> outputBuffer(bufferSizeSamples);
    
    std::cout << "Audio thread started (buffer: " << bufferSizeFrames << " frames)" << std::endl;
    
    auto lastCpuCheck = std::chrono::steady_clock::now();
    auto processingStart = lastCpuCheck;
    long long totalProcessingNs = 0;
    long long totalSamples = 0;
    
    while (!shouldStop.load())
    {
        // Read from input device
        int err = snd_pcm_readi(captureHandle, inputBuffer.data(), bufferSizeFrames);
        
        if (err == -EPIPE)
        {
            // Buffer overrun
            std::cerr << "Input buffer overrun" << std::endl;
            snd_pcm_prepare(captureHandle);
            continue;
        }
        else if (err < 0)
        {
            std::cerr << "Read error: " << snd_strerror(err) << std::endl;
            continue;
        }
        else if (err != (int)bufferSizeFrames)
        {
            std::cerr << "Short read: expected " << bufferSizeFrames 
                      << ", got " << err << std::endl;
        }
        
        // Process audio
        processingStart = std::chrono::steady_clock::now();
        processAudio(inputBuffer.data(), outputBuffer.data(), bufferSizeFrames);
        auto processingEnd = std::chrono::steady_clock::now();
        totalProcessingNs += std::chrono::duration_cast<std::chrono::nanoseconds>(
            processingEnd - processingStart).count();
        totalSamples += bufferSizeFrames;
        
        // Write to output device
        err = snd_pcm_writei(playbackHandle, outputBuffer.data(), bufferSizeFrames);
        
        if (err == -EPIPE)
        {
            // Buffer underrun
            std::cerr << "Output buffer underrun" << std::endl;
            snd_pcm_prepare(playbackHandle);
            continue;
        }
        else if (err < 0)
        {
            std::cerr << "Write error: " << snd_strerror(err) << std::endl;
            continue;
        }
        else if (err != (int)bufferSizeFrames)
        {
            std::cerr << "Short write: expected " << bufferSizeFrames 
                      << ", got " << err << std::endl;
        }
        
        // Update CPU usage every second
        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration_cast<std::chrono::seconds>(now - lastCpuCheck).count() >= 1)
        {
            double elapsedSec = (double)totalSamples / config.sampleRate;
            double processingMsec = totalProcessingNs / 1000000.0;
            cpuUsage.store((float)(processingMsec / (elapsedSec * 1000.0)));
            
            lastCpuCheck = now;
            totalProcessingNs = 0;
            totalSamples = 0;
        }
    }
    
    std::cout << "Audio thread stopped" << std::endl;
}

void AlsaAudioEngine::processAudio(float* inputBuffer, float* outputBuffer, 
                                   unsigned int frames)
{
    if (!processor)
    {
        // Passthrough if no processor
        memcpy(outputBuffer, inputBuffer, frames * config.channels * sizeof(float));
        return;
    }
    
    processor->process(inputBuffer, outputBuffer, frames);
    
    // Update profanity count
    profanityCount.store(processor->getProfanityCount());
}

void AlsaAudioEngine::closeAlsaDevices()
{
    if (captureHandle)
    {
        snd_pcm_close(captureHandle);
        captureHandle = nullptr;
    }
    
    if (playbackHandle)
    {
        snd_pcm_close(playbackHandle);
        playbackHandle = nullptr;
    }
}

double AlsaAudioEngine::getCurrentLatency() const
{
    if (!processor)
        return 0.0;
    
    return processor->getCurrentLatency();
}

float AlsaAudioEngine::getBufferFill() const
{
    if (!processor)
        return 0.0f;
    
    return processor->getBufferFill();
}

float AlsaAudioEngine::getCpuUsage() const
{
    return cpuUsage.load();
}

float AlsaAudioEngine::getMemoryUsageMB() const
{
    // Read from /proc/self/status
    std::ifstream statusFile("/proc/self/status");
    std::string line;
    float vmRssMB = 0.0f;
    
    while (std::getline(statusFile, line))
    {
        if (line.substr(0, 6) == "VmRSS:")
        {
            size_t pos = line.find_first_of("0123456789");
            if (pos != std::string::npos)
            {
                long vmRssKB = std::stol(line.substr(pos));
                vmRssMB = vmRssKB / 1024.0f;
                break;
            }
        }
    }
    
    return vmRssMB;
}

void AlsaAudioEngine::setCensorMode(CensorMode mode)
{
    config.censorMode = mode;
    
    if (processor)
    {
        processor->setCensorMode((mode == CensorMode::Reverse) 
                                ? AudioProcessor::CensorMode::Reverse 
                                : AudioProcessor::CensorMode::Mute);
    }
}

void AlsaAudioEngine::reportStatus(const std::string& status, const std::string& details)
{
    if (statusCallback)
        statusCallback(status, details);
}
