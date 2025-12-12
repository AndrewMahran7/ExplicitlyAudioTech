/*
  ==============================================================================

    HttpApiServer.h
    Created: 12 Dec 2024
    Author: Explicitly Audio Systems

    Lightweight HTTP REST API for controlling the Explicitly engine.
    Uses cpp-httplib (single-header library).

  ==============================================================================
*/

#pragma once

#include <string>
#include <functional>
#include <atomic>
#include <thread>
#include <memory>

// Forward declaration (cpp-httplib will be included in .cpp)
namespace httplib { class Server; }

class AlsaAudioEngine;  // Forward declaration

class HttpApiServer
{
public:
    struct Config
    {
        std::string bindAddress = "0.0.0.0";
        int port = 8080;
        bool enableCors = true;
    };
    
    HttpApiServer(AlsaAudioEngine* engine);
    ~HttpApiServer();
    
    bool start(const Config& config);
    void stop();
    
    bool isRunning() const { return running.load(); }
    int getPort() const { return config.port; }

private:
    AlsaAudioEngine* engine;
    Config config;
    
    std::unique_ptr<httplib::Server> server;
    std::thread serverThread;
    std::atomic<bool> running{false};
    
    // Route handlers
    void setupRoutes();
    void handleGetStatus(const httplib::Request& req, httplib::Response& res);
    void handlePostStart(const httplib::Request& req, httplib::Response& res);
    void handlePostStop(const httplib::Request& req, httplib::Response& res);
    void handlePostConfig(const httplib::Request& req, httplib::Response& res);
    void handleGetHealth(const httplib::Request& req, httplib::Response& res);
};
