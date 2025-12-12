/*
  ==============================================================================

    main.cpp
    Created: 12 Dec 2024
    Author: Explicitly Audio Systems

    Headless daemon entry point for Orange Pi Zero 3.
    
    Usage:
        explicitly-daemon [config_file]
        
    If no config file is specified, uses /etc/explicitly/config.yaml

  ==============================================================================
*/

#include "AlsaAudioEngine.h"
#include "HttpApiServer.h"
#include <iostream>
#include <csignal>
#include <fstream>
#include <sstream>
#include <unistd.h>

// Global engine instance for signal handling
AlsaAudioEngine* g_engine = nullptr;
HttpApiServer* g_apiServer = nullptr;

void signalHandler(int signal)
{
    std::cout << "\nReceived signal " << signal << ", shutting down..." << std::endl;
    
    if (g_apiServer)
        g_apiServer->stop();
    
    if (g_engine)
        g_engine->stop();
    
    exit(0);
}

// Simple YAML parser (only supports flat key: value pairs)
bool loadConfig(const std::string& path, AlsaAudioEngine::Config& engineConfig, 
                HttpApiServer::Config& apiConfig)
{
    std::ifstream file(path);
    if (!file.is_open())
    {
        std::cerr << "Could not open config file: " << path << std::endl;
        return false;
    }
    
    std::string line;
    std::string currentSection;
    
    while (std::getline(file, line))
    {
        // Trim whitespace
        line.erase(0, line.find_first_not_of(" \t"));
        line.erase(line.find_last_not_of(" \t\r\n") + 1);
        
        // Skip empty lines and comments
        if (line.empty() || line[0] == '#')
            continue;
        
        // Check for section headers
        if (line.back() == ':' && line.find(' ') == std::string::npos)
        {
            currentSection = line.substr(0, line.length() - 1);
            continue;
        }
        
        // Parse key: value
        size_t colonPos = line.find(':');
        if (colonPos == std::string::npos)
            continue;
        
        std::string key = line.substr(0, colonPos);
        std::string value = line.substr(colonPos + 1);
        
        // Trim key and value
        key.erase(0, key.find_first_not_of(" \t"));
        key.erase(key.find_last_not_of(" \t") + 1);
        value.erase(0, value.find_first_not_of(" \t\""));
        value.erase(value.find_last_not_of(" \t\"") + 1);
        
        // Apply settings based on section
        if (currentSection == "audio")
        {
            if (key == "input_device") engineConfig.inputDevice = value;
            else if (key == "output_device") engineConfig.outputDevice = value;
            else if (key == "sample_rate") engineConfig.sampleRate = std::stoi(value);
            else if (key == "buffer_size") engineConfig.periodSize = std::stoi(value);
        }
        else if (currentSection == "processing")
        {
            if (key == "model_path") engineConfig.modelPath = value;
            else if (key == "profanity_lexicon") engineConfig.profanityLexicon = value;
            else if (key == "censor_mode")
            {
                if (value == "mute") engineConfig.censorMode = AlsaAudioEngine::CensorMode::Mute;
                else engineConfig.censorMode = AlsaAudioEngine::CensorMode::Reverse;
            }
            else if (key == "enable_vocal_filter") engineConfig.enableVocalFilter = (value == "true");
            else if (key == "enable_timestamp_refiner") engineConfig.enableTimestampRefiner = (value == "true");
        }
        else if (currentSection == "api")
        {
            if (key == "port") apiConfig.port = std::stoi(value);
            else if (key == "bind_address") apiConfig.bindAddress = value;
            else if (key == "enable_cors") apiConfig.enableCors = (value == "true");
        }
    }
    
    return true;
}

void printUsage(const char* programName)
{
    std::cout << "Explicitly Audio Profanity Filter - Headless Daemon\n"
              << "Usage: " << programName << " [options]\n\n"
              << "Options:\n"
              << "  -c, --config FILE    Configuration file (default: /etc/explicitly/config.yaml)\n"
              << "  -h, --help           Show this help message\n"
              << "  -v, --version        Show version information\n\n"
              << "Controls:\n"
              << "  HTTP API:  http://localhost:8080/api/\n"
              << "  Systemd:   sudo systemctl start/stop explicitly\n"
              << "  Signal:    SIGTERM or SIGINT to gracefully shutdown\n"
              << std::endl;
}

int main(int argc, char* argv[])
{
    std::cout << "==========================================\n"
              << "  Explicitly Audio Profanity Filter\n"
              << "  Orange Pi Zero 3 Edition\n"
              << "  Version 1.0.0\n"
              << "==========================================\n" << std::endl;
    
    // Parse command line arguments
    std::string configPath = "/etc/explicitly/config.yaml";
    
    for (int i = 1; i < argc; ++i)
    {
        std::string arg = argv[i];
        
        if (arg == "-h" || arg == "--help")
        {
            printUsage(argv[0]);
            return 0;
        }
        else if (arg == "-v" || arg == "--version")
        {
            std::cout << "Version 1.0.0" << std::endl;
            return 0;
        }
        else if (arg == "-c" || arg == "--config")
        {
            if (i + 1 < argc)
            {
                configPath = argv[++i];
            }
            else
            {
                std::cerr << "Error: --config requires an argument" << std::endl;
                return 1;
            }
        }
        else
        {
            std::cerr << "Unknown option: " << arg << std::endl;
            printUsage(argv[0]);
            return 1;
        }
    }
    
    // Load configuration
    AlsaAudioEngine::Config engineConfig;
    HttpApiServer::Config apiConfig;
    
    std::cout << "Loading configuration from: " << configPath << std::endl;
    if (!loadConfig(configPath, engineConfig, apiConfig))
    {
        std::cerr << "Warning: Could not load config file, using defaults" << std::endl;
        
        // Set default paths for Orange Pi
        engineConfig.modelPath = "/usr/share/explicitly/models/ggml-tiny.en.bin";
        engineConfig.profanityLexicon = "/usr/share/explicitly/profanity_en.txt";
    }
    
    // Print configuration
    std::cout << "\nConfiguration:" << std::endl;
    std::cout << "  Audio Input:  " << engineConfig.inputDevice << std::endl;
    std::cout << "  Audio Output: " << engineConfig.outputDevice << std::endl;
    std::cout << "  Sample Rate:  " << engineConfig.sampleRate << " Hz" << std::endl;
    std::cout << "  Buffer Size:  " << engineConfig.periodSize << " frames" << std::endl;
    std::cout << "  Model:        " << engineConfig.modelPath << std::endl;
    std::cout << "  Censor Mode:  " << (engineConfig.censorMode == AlsaAudioEngine::CensorMode::Mute ? "Mute" : "Reverse") << std::endl;
    std::cout << "  API Port:     " << apiConfig.port << std::endl;
    std::cout << std::endl;
    
    // Initialize audio engine
    AlsaAudioEngine engine;
    g_engine = &engine;
    
    std::cout << "Initializing audio engine..." << std::endl;
    if (!engine.initialize(engineConfig))
    {
        std::cerr << "Error: " << engine.getLastError() << std::endl;
        return 1;
    }
    
    // Setup signal handlers
    signal(SIGINT, signalHandler);
    signal(SIGTERM, signalHandler);
    
    // Start HTTP API server
    HttpApiServer apiServer(&engine);
    g_apiServer = &apiServer;
    
    std::cout << "Starting HTTP API server..." << std::endl;
    if (!apiServer.start(apiConfig))
    {
        std::cerr << "Error: Could not start HTTP API server" << std::endl;
        return 1;
    }
    
    std::cout << "\n========================================" << std::endl;
    std::cout << "Explicitly daemon is running!" << std::endl;
    std::cout << "HTTP API: http://localhost:" << apiConfig.port << "/api/" << std::endl;
    std::cout << "Press Ctrl+C to stop" << std::endl;
    std::cout << "========================================\n" << std::endl;
    
    // Status reporting callback
    engine.setStatusCallback([](const std::string& status, const std::string& details) {
        std::cout << "[Status] " << status << ": " << details << std::endl;
    });
    
    // Main loop - monitor and log status
    while (true)
    {
        sleep(10);  // Check every 10 seconds
        
        if (engine.isRunning())
        {
            std::cout << "[Monitor] "
                      << "Latency: " << engine.getCurrentLatency() << "ms, "
                      << "CPU: " << (engine.getCpuUsage() * 100.0f) << "%, "
                      << "Memory: " << engine.getMemoryUsageMB() << "MB, "
                      << "Profanity: " << engine.getProfanityCount() << " detections"
                      << std::endl;
        }
    }
    
    return 0;
}
