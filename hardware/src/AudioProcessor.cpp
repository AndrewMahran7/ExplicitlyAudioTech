/*
  ==============================================================================

    AudioProcessor.cpp
    Created: 12 Dec 2024
    Author: Explicitly Audio Systems

    Full audio processing implementation for Orange Pi Zero 3 (4GB RAM).
    Adapted from desktop/Source/AudioEngine.cpp with JUCE removed.

  ==============================================================================
*/

#include "AudioProcessor.h"
#include <iostream>
#include <algorithm>
#include <cmath>
#include <chrono>
#include <iomanip>
#include <regex>
#include <cstring>

// Helper function to clean Whisper transcript text
std::string AudioProcessor::cleanTranscriptText(const std::string& text)
{
    std::string cleaned = text;
    
    // Remove parenthetical content
    cleaned = std::regex_replace(cleaned, std::regex("\\([^)]*\\)"), "");
    
    // Fix Unicode quote characters
    cleaned = std::regex_replace(cleaned, std::regex("\xC3\x96\xAC"), "'");
    cleaned = std::regex_replace(cleaned, std::regex("\xE2\x80\x98"), "'");
    cleaned = std::regex_replace(cleaned, std::regex("\xE2\x80\x99"), "'");
    cleaned = std::regex_replace(cleaned, std::regex("\xE2\x80\x9C"), "\"");
    cleaned = std::regex_replace(cleaned, std::regex("\xE2\x80\x9D"), "\"");
    
    // Keep only alphanumeric, apostrophes, hyphens, spaces
    std::string filtered;
    for (char c : cleaned)
    {
        if (std::isalnum(static_cast<unsigned char>(c)) || c == '\'' || c == '-' || c == ' ')
            filtered += c;
    }
    cleaned = filtered;
    
    // Trim whitespace
    cleaned.erase(0, cleaned.find_first_not_of(" \t\n\r"));
    cleaned.erase(cleaned.find_last_not_of(" \t\n\r") + 1);
    
    return cleaned;
}

AudioProcessor::AudioProcessor()
{
}

AudioProcessor::~AudioProcessor()
{
    stop();
}

bool AudioProcessor::initialize(const Config& cfg)
{
    config = cfg;
    
    std::cout << "[AudioProcessor] Initializing with 4GB RAM - full features enabled" << std::endl;
    
    // Load profanity filter
    if (!profanityFilter.loadLexicon(config.profanityLexicon))
    {
        lastError = "Failed to load profanity lexicon: " + config.profanityLexicon;
        std::cerr << lastError << std::endl;
        return false;
    }
    std::cout << "[AudioProcessor] Profanity filter loaded" << std::endl;
    
    // Initialize vocal filter
    vocalFilter.initialize(config.sampleRate);
    std::cout << "[AudioProcessor] Vocal filter initialized" << std::endl;
    
    // Load Whisper model
    whisper_context_params cparams = whisper_context_default_params();
    cparams.use_gpu = false;  // CPU only on Orange Pi
    cparams.dtw_token_timestamps = true;
    cparams.dtw_aheads_preset = WHISPER_AHEADS_TINY_EN;
    
    whisperCtx = whisper_init_from_file_with_params(config.modelPath.c_str(), cparams);
    
    if (whisperCtx == nullptr)
    {
        lastError = "Failed to load Whisper model: " + config.modelPath;
        std::cerr << lastError << std::endl;
        return false;
    }
    std::cout << "[AudioProcessor] Whisper tiny.en model loaded" << std::endl;
    
    // Allocate buffers
    int audioBufferSize = (int)(config.sampleRate * config.chunkSeconds);
    audioBuffer.resize(audioBufferSize, 0.0f);
    processingBuffer.resize(audioBufferSize, 0.0f);
    
    // Delay buffer: 20 seconds capacity (with 4GB RAM we can afford this)
    delayBufferSize = (int)(config.sampleRate * (config.initialDelaySeconds + 10.0f));
    delayBuffer.resize(config.channels);
    for (auto& channel : delayBuffer)
        channel.resize(delayBufferSize, 0.0f);
    
    std::cout << "[AudioProcessor] Delay buffer: " << delayBufferSize << " samples ("
              << (delayBufferSize / config.sampleRate) << "s capacity)" << std::endl;
    std::cout << "[AudioProcessor] Will buffer " << config.initialDelaySeconds 
              << "s before playback starts" << std::endl;
    
    return true;
}

bool AudioProcessor::start()
{
    if (shouldStopThread.load())
    {
        lastError = "Already running";
        return false;
    }
    
    // Reset state
    bufferWritePos = 0;
    transcriptionInterval = 0;
    streamTime = 0.0;
    playbackStarted.store(false);
    wasWaiting = false;
    debugCounter = 0;
    profanityCount.store(0);
    bufferUnderrun.store(false);
    
    delayWritePos.store(0);
    delayReadPos.store(0);
    
    // Clear buffers
    for (auto& channel : delayBuffer)
        std::fill(channel.begin(), channel.end(), 0.0f);
    
    // Start Whisper thread
    shouldStopThread.store(false);
    hasNewBuffer.store(false);
    whisperThread = std::thread(&AudioProcessor::whisperThreadFunction, this);
    
    std::cout << "[AudioProcessor] Started - Whisper thread running" << std::endl;
    return true;
}

void AudioProcessor::stop()
{
    if (!shouldStopThread.load())
        return;
    
    shouldStopThread.store(true);
    bufferReady.notify_one();
    
    if (whisperThread.joinable())
    {
        std::cout << "[AudioProcessor] Waiting for Whisper thread..." << std::endl;
        whisperThread.join();
        std::cout << "[AudioProcessor] Whisper thread stopped" << std::endl;
    }
    
    if (whisperCtx)
    {
        whisper_free(whisperCtx);
        whisperCtx = nullptr;
    }
    
    std::cout << "[AudioProcessor] Stopped" << std::endl;
}

void AudioProcessor::process(float* inputBuffer, float* outputBuffer, unsigned int frames)
{
    // Calculate RMS level
    float rmsSum = 0.0f;
    for (unsigned int i = 0; i < frames; ++i)
    {
        float sample = inputBuffer[i * config.channels];  // First channel
        rmsSum += sample * sample;
    }
    float rms = std::sqrt(rmsSum / frames);
    currentInputLevel.store(rms);
    
    // Accumulate audio for Whisper (mono downmix)
    for (unsigned int i = 0; i < frames; ++i)
    {
        float monoSample = 0.0f;
        for (int ch = 0; ch < config.channels; ++ch)
            monoSample += inputBuffer[i * config.channels + ch];
        monoSample /= config.channels;
        
        if (bufferWritePos < (int)audioBuffer.size())
        {
            audioBuffer[bufferWritePos] = monoSample;
            bufferWritePos++;
        }
    }
    
    // Check if we have enough audio for Whisper
    transcriptionInterval += frames;
    
    if (transcriptionInterval >= (config.sampleRate * config.chunkSeconds) && !hasNewBuffer.load())
    {
        // Send to Whisper thread
        {
            std::lock_guard<std::mutex> lock(bufferMutex);
            
            int samplesToProcess = std::min(bufferWritePos, (int)(config.sampleRate * config.chunkSeconds));
            std::copy(audioBuffer.begin(), audioBuffer.begin() + samplesToProcess, 
                     processingBuffer.begin());
            
            bufferCaptureTime = (double)delayWritePos.load();
            
            int writePos = delayWritePos.load();
            int readPos = delayReadPos.load();
            int chunkStartPos = (writePos - (int)(config.sampleRate * config.chunkSeconds) + delayBufferSize) % delayBufferSize;
            
            std::cout << "[CAPTURE] Sending chunk | chunkStart=" << chunkStartPos 
                      << ", chunkEnd=" << writePos << ", readPos=" << readPos << std::endl;
            
            if (wasWaiting)
            {
                std::cout << "[FLOW] Whisper finished! Sending next chunk" << std::endl;
                wasWaiting = false;
            }
            
            hasNewBuffer.store(true);
            bufferReady.notify_one();
        }
        
        bufferWritePos = 0;
        transcriptionInterval = 0;
    }
    else if (transcriptionInterval >= (config.sampleRate * config.chunkSeconds) && hasNewBuffer.load())
    {
        // Whisper still busy
        if (++debugCounter % 100 == 0)
        {
            double extraTime = (transcriptionInterval - (config.sampleRate * config.chunkSeconds)) / config.sampleRate;
            std::cout << "[FLOW] Waiting for Whisper... (" << std::fixed << std::setprecision(2) 
                      << extraTime << "s extra)" << std::endl;
            wasWaiting = true;
        }
    }
    
    // Delay buffer management
    int writePos = delayWritePos.load();
    int readPos = delayReadPos.load();
    
    for (unsigned int i = 0; i < frames; ++i)
    {
        // Write input to delay buffer
        for (int ch = 0; ch < config.channels; ++ch)
        {
            float sample = inputBuffer[i * config.channels + ch];
            delayBuffer[ch][writePos] = sample;
        }
        
        // Calculate buffer fill
        int currentGap = (writePos - readPos + delayBufferSize) % delayBufferSize;
        double bufferSeconds = (double)currentGap / config.sampleRate;
        
        // Start playback when buffer reaches target
        bool canPlay;
        if (!playbackStarted.load())
        {
            canPlay = (bufferSeconds >= config.initialDelaySeconds);
            if (canPlay)
            {
                playbackStarted.store(true);
                std::cout << "\n[AudioProcessor] ✓ " << config.initialDelaySeconds 
                          << " SECONDS BUFFERED - PLAYBACK STARTING!\n" << std::endl;
            }
        }
        else
        {
            // Dynamic buffering
            static bool wasPaused = false;
            double pauseThreshold = config.initialDelaySeconds - 2.0;
            double resumeThreshold = config.initialDelaySeconds;
            
            if (bufferSeconds < pauseThreshold && !wasPaused)
            {
                wasPaused = true;
                std::cout << "\n[AudioProcessor] ⚠ Buffer low (" << bufferSeconds 
                          << "s) - PAUSING\n" << std::endl;
            }
            else if (bufferSeconds >= resumeThreshold && wasPaused)
            {
                wasPaused = false;
                std::cout << "\n[AudioProcessor] ✓ Buffer recovered (" << bufferSeconds 
                          << "s) - RESUMING\n" << std::endl;
            }
            
            canPlay = !wasPaused;
        }
        
        // Read from delay buffer or output silence
        for (int ch = 0; ch < config.channels; ++ch)
        {
            if (canPlay)
                outputBuffer[i * config.channels + ch] = delayBuffer[ch][readPos];
            else
                outputBuffer[i * config.channels + ch] = 0.0f;
        }
        
        // Advance positions
        writePos = (writePos + 1) % delayBufferSize;
        if (canPlay)
            readPos = (readPos + 1) % delayBufferSize;
    }
    
    delayWritePos.store(writePos);
    delayReadPos.store(readPos);
    
    streamTime += (double)frames / config.sampleRate;
}

void AudioProcessor::whisperThreadFunction()
{
    std::cout << "[AudioProcessor] Whisper thread started" << std::endl;
    
    std::vector<float> localBuffer(config.sampleRate * 5);
    
    while (!shouldStopThread.load())
    {
        std::unique_lock<std::mutex> lock(bufferMutex);
        
        bufferReady.wait(lock, [this] { 
            return hasNewBuffer.load() || shouldStopThread.load(); 
        });
        
        if (shouldStopThread.load())
            break;
        
        if (hasNewBuffer.load())
        {
            std::cout << "[AudioProcessor] Processing 5s chunk..." << std::endl;
            
            std::copy(processingBuffer.begin(), processingBuffer.end(), localBuffer.begin());
            double captureTime = bufferCaptureTime;
            hasNewBuffer.store(false);
            
            lock.unlock();
            
            processTranscription(localBuffer, captureTime);
        }
    }
    
    std::cout << "[AudioProcessor] Whisper thread exiting" << std::endl;
}

std::vector<float> AudioProcessor::resampleTo16kHz(const std::vector<float>& input)
{
    if (config.sampleRate == 16000)
        return input;
    
    double ratio = (double)config.sampleRate / 16000.0;
    size_t outputSize = (size_t)(input.size() / ratio);
    std::vector<float> output(outputSize);
    
    for (size_t i = 0; i < outputSize; ++i)
    {
        double srcPos = i * ratio;
        size_t srcIndex = (size_t)srcPos;
        double frac = srcPos - srcIndex;
        
        if (srcIndex + 1 < input.size())
            output[i] = input[srcIndex] * (1.0f - frac) + input[srcIndex + 1] * frac;
        else
            output[i] = input[srcIndex];
    }
    
    return output;
}

void AudioProcessor::processTranscription(const std::vector<float>& buffer, double captureTime)
{
    if (!whisperCtx)
        return;
    
    auto startTime = std::chrono::high_resolution_clock::now();
    
    // Process buffer
    int samplesToProcess = config.sampleRate * 5;
    std::vector<float> bufferCopy(buffer.begin(), buffer.begin() + samplesToProcess);
    
    // Apply vocal filter if enabled
    if (config.enableVocalFilter)
    {
        vocalFilter.processBuffer(bufferCopy);
        std::cout << "[AudioProcessor] Vocal filter applied" << std::endl;
    }
    
    audioBuffer16k = resampleTo16kHz(bufferCopy);
    std::cout << "[AudioProcessor] Resampled to 16kHz: " << audioBuffer16k.size() << " samples" << std::endl;
    
    // Configure Whisper
    whisper_full_params wparams = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
    wparams.print_realtime = false;
    wparams.print_progress = false;
    wparams.print_timestamps = true;
    wparams.print_special = false;
    wparams.translate = false;
    wparams.language = "en";
    wparams.n_threads = 4;  // Use all 4 cores on Orange Pi
    wparams.single_segment = false;
    wparams.max_len = 1;
    wparams.audio_ctx = 0;
    wparams.temperature = 0.0f;
    wparams.entropy_thold = 2.4f;
    wparams.logprob_thold = -1.0f;
    
    // Run Whisper
    int result = whisper_full(whisperCtx, wparams, audioBuffer16k.data(), (int)audioBuffer16k.size());
    
    if (result != 0)
    {
        std::cerr << "[AudioProcessor] Whisper failed with code " << result << std::endl;
        return;
    }
    
    whisper_reset_timings(whisperCtx);
    
    // Extract word segments
    int numSegments = whisper_full_n_segments(whisperCtx);
    std::vector<WordSegment> transcribedWords;
    
    for (int i = 0; i < numSegments; ++i)
    {
        int64_t segmentStart = whisper_full_get_segment_t0(whisperCtx, i);
        int64_t segmentEnd = whisper_full_get_segment_t1(whisperCtx, i);
        double segStartSec = segmentStart * 0.01;
        double segEndSec = segmentEnd * 0.01;
        
        int numTokens = whisper_full_n_tokens(whisperCtx, i);
        std::vector<std::string> segmentWords;
        
        for (int j = 0; j < numTokens; ++j)
        {
            whisper_token_data token = whisper_full_get_token_data(whisperCtx, i, j);
            
            if (token.id >= whisper_token_eot(whisperCtx))
                continue;
            
            const char* tokenText = whisper_full_get_token_text(whisperCtx, i, j);
            std::string word = cleanTranscriptText(tokenText);
            
            if (!word.empty())
                segmentWords.push_back(word);
        }
        
        // Distribute words across segment
        if (!segmentWords.empty())
        {
            double segmentDuration = segEndSec - segStartSec;
            double wordDuration = segmentDuration / segmentWords.size();
            
            for (size_t k = 0; k < segmentWords.size(); ++k)
            {
                double wordStart = segStartSec + (k * wordDuration);
                double wordEnd = wordStart + wordDuration;
                
                wordStart = std::max(0.0, std::min(5.0, wordStart));
                wordEnd = std::max(wordStart + 0.05, std::min(5.0, wordEnd));
                
                transcribedWords.emplace_back(segmentWords[k], wordStart, wordEnd, 0.9f);
            }
        }
    }
    
    std::cout << "[AudioProcessor] Extracted " << transcribedWords.size() << " words" << std::endl;
    
    // Refine timestamps if enabled
    if (config.enableTimestampRefiner)
    {
        std::cout << "[AudioProcessor] Refining timestamps..." << std::endl;
        for (auto& word : transcribedWords)
            timestampRefiner.refineWordTimestamp(word, bufferCopy, config.sampleRate);
    }
    
    // Check profanity and apply censorship
    std::cout << "[AudioProcessor] ========== TRANSCRIPT ==========" << std::endl;
    std::string fullTranscript;
    std::vector<std::string> detectedWords;
    
    int chunkEndPos = (int)captureTime;
    int chunkStartPos = (chunkEndPos - (config.sampleRate * 5) + delayBufferSize) % delayBufferSize;
    
    for (size_t idx = 0; idx < transcribedWords.size(); ++idx)
    {
        const auto& wordSeg = transcribedWords[idx];
        fullTranscript += wordSeg.word + " ";
        
        // Check single word profanity
        std::string normalizedWord = LyricsAlignment::normalizeText(wordSeg.word);
        
        if (profanityFilter.containsProfanity(normalizedWord))
        {
            if (bufferUnderrun.load())
            {
                std::cout << "[AudioProcessor] Profanity \"" << wordSeg.word 
                          << "\" SKIPPED (buffer underrun)" << std::endl;
                continue;
            }
            
            detectedWords.push_back(wordSeg.word);
            profanityCount.fetch_add(1);
            
            // Calculate buffer positions with asymmetric padding
            double paddingBefore = 0.4;  // 400ms before
            double paddingAfter = 0.1;   // 100ms after
            
            int startSample = (int)((wordSeg.start - paddingBefore) * config.sampleRate);
            int endSample = (int)((wordSeg.end + paddingAfter) * config.sampleRate);
            
            startSample = std::max(0, std::min(startSample, config.sampleRate * 5));
            endSample = std::max(startSample, std::min(endSample, config.sampleRate * 5));
            
            int numSamplesToCensor = endSample - startSample;
            int fadeSamples = std::min(480, numSamplesToCensor / 4);
            
            std::cout << "[AudioProcessor] *** PROFANITY: \"" << wordSeg.word << "\" ***" << std::endl;
            std::cout << "[AudioProcessor]     Timestamp: " << wordSeg.start << "s - " << wordSeg.end << "s" << std::endl;
            std::cout << "[AudioProcessor]     Censoring " << numSamplesToCensor << " samples" << std::endl;
            
            // Apply censorship
            if (config.censorMode == CensorMode::Mute)
            {
                for (int ch = 0; ch < config.channels; ++ch)
                {
                    for (int i = startSample; i < endSample; ++i)
                    {
                        int delayPos = (chunkStartPos + i) % delayBufferSize;
                        delayBuffer[ch][delayPos] = 0.0f;
                    }
                }
                std::cout << "[AudioProcessor]     ✓ MUTED" << std::endl;
            }
            else if (config.censorMode == CensorMode::Reverse)
            {
                for (int ch = 0; ch < config.channels; ++ch)
                {
                    std::vector<float> tempBuffer(numSamplesToCensor);
                    for (int i = 0; i < numSamplesToCensor; ++i)
                    {
                        int delayPos = (chunkStartPos + startSample + i) % delayBufferSize;
                        tempBuffer[i] = delayBuffer[ch][delayPos];
                    }
                    
                    std::reverse(tempBuffer.begin(), tempBuffer.end());
                    
                    for (int i = 0; i < numSamplesToCensor; ++i)
                    {
                        float sample = tempBuffer[i];
                        float volumeReduction = 0.5f;
                        
                        if (i < fadeSamples)
                            sample *= ((float)i / fadeSamples) * volumeReduction;
                        else if (i >= numSamplesToCensor - fadeSamples)
                            sample *= ((float)(numSamplesToCensor - i) / fadeSamples) * volumeReduction;
                        else
                            sample *= volumeReduction;
                        
                        int delayPos = (chunkStartPos + startSample + i) % delayBufferSize;
                        delayBuffer[ch][delayPos] = sample;
                    }
                }
                std::cout << "[AudioProcessor]     ✓ REVERSED" << std::endl;
            }
        }
        
        // Check multi-word profanity
        if (idx + 1 < transcribedWords.size())
        {
            const auto& nextWord = transcribedWords[idx + 1];
            std::string combined = LyricsAlignment::normalizeText(wordSeg.word + nextWord.word);
            
            if (profanityFilter.containsProfanity(combined))
            {
                if (bufferUnderrun.load())
                    continue;
                
                detectedWords.push_back(wordSeg.word + " " + nextWord.word);
                profanityCount.fetch_add(1);
                
                double paddingBefore = 0.4;
                double paddingAfter = 0.1;
                
                int startSample = (int)((wordSeg.start - paddingBefore) * config.sampleRate);
                int endSample = (int)((nextWord.end + paddingAfter) * config.sampleRate);
                
                startSample = std::max(0, std::min(startSample, config.sampleRate * 5));
                endSample = std::max(startSample, std::min(endSample, config.sampleRate * 5));
                
                int numSamplesToCensor = endSample - startSample;
                int fadeSamples = std::min(480, numSamplesToCensor / 4);
                
                std::cout << "[AudioProcessor] *** MULTI-WORD: \"" << wordSeg.word << " " << nextWord.word << "\" ***" << std::endl;
                
                // Apply censorship (same logic as single word)
                if (config.censorMode == CensorMode::Mute)
                {
                    for (int ch = 0; ch < config.channels; ++ch)
                    {
                        for (int i = startSample; i < endSample; ++i)
                        {
                            int delayPos = (chunkStartPos + i) % delayBufferSize;
                            delayBuffer[ch][delayPos] = 0.0f;
                        }
                    }
                }
                else if (config.censorMode == CensorMode::Reverse)
                {
                    for (int ch = 0; ch < config.channels; ++ch)
                    {
                        std::vector<float> tempBuffer(numSamplesToCensor);
                        for (int i = 0; i < numSamplesToCensor; ++i)
                        {
                            int delayPos = (chunkStartPos + startSample + i) % delayBufferSize;
                            tempBuffer[i] = delayBuffer[ch][delayPos];
                        }
                        
                        std::reverse(tempBuffer.begin(), tempBuffer.end());
                        
                        for (int i = 0; i < numSamplesToCensor; ++i)
                        {
                            float sample = tempBuffer[i] * 0.5f;
                            if (i < fadeSamples)
                                sample *= (float)i / fadeSamples;
                            else if (i >= numSamplesToCensor - fadeSamples)
                                sample *= (float)(numSamplesToCensor - i) / fadeSamples;
                            
                            int delayPos = (chunkStartPos + startSample + i) % delayBufferSize;
                            delayBuffer[ch][delayPos] = sample;
                        }
                    }
                }
                
                idx++;  // Skip next word
            }
        }
    }
    
    std::cout << "[AudioProcessor] \"" << fullTranscript << "\"" << std::endl;
    
    if (!detectedWords.empty())
    {
        std::cout << "[AudioProcessor] *** DETECTED: ";
        for (const auto& w : detectedWords)
            std::cout << "\"" << w << "\" ";
        std::cout << "***" << std::endl;
    }
    
    whisper_reset_timings(whisperCtx);
    
    // Timing
    auto endTime = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime);
    double seconds = duration.count() / 1000.0;
    double realTimeFactor = seconds / 5.0;
    
    std::cout << "[TIMING] Processed 5.0s in " << seconds << "s (RTF: " 
              << std::fixed << std::setprecision(2) << realTimeFactor << "x)";
    
    if (realTimeFactor > 1.0)
        std::cout << " [WARNING: Slower than real-time!]";
    
    std::cout << std::endl;
    std::cout << "[AudioProcessor] ========================================" << std::endl;
}

void AudioProcessor::setCensorMode(CensorMode mode)
{
    config.censorMode = mode;
    std::cout << "[AudioProcessor] Censor mode changed to: " 
              << (mode == CensorMode::Mute ? "MUTE" : "REVERSE") << std::endl;
}

double AudioProcessor::getCurrentLatency() const
{
    return config.initialDelaySeconds * 1000.0;
}

float AudioProcessor::getBufferFill() const
{
    int writePos = delayWritePos.load();
    int readPos = delayReadPos.load();
    int gap = (writePos - readPos + delayBufferSize) % delayBufferSize;
    return (float)gap / delayBufferSize;
}
