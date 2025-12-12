cmake_minimum_required(VERSION 3.16)

project(ExplicitlyHardware VERSION 1.0.0 LANGUAGES CXX)

# C++ Standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Compiler flags for ARM optimization
if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64" OR CMAKE_SYSTEM_PROCESSOR MATCHES "arm")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -march=armv8-a -mtune=cortex-a53")
    set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3 -DNDEBUG")
    message(STATUS "Building for ARM64 with Cortex-A53 optimizations")
endif()

# Find required packages
find_package(Threads REQUIRED)
find_package(ALSA REQUIRED)

# Whisper.cpp path
set(WHISPER_DIR "${CMAKE_SOURCE_DIR}/../whisper.cpp" CACHE PATH "Path to whisper.cpp")
if(NOT EXISTS "${WHISPER_DIR}/whisper.h")
    message(FATAL_ERROR "whisper.cpp not found at ${WHISPER_DIR}. Clone from https://github.com/ggerganov/whisper.cpp")
endif()

# Include directories
include_directories(
    ${CMAKE_SOURCE_DIR}/src
    ${WHISPER_DIR}
    ${ALSA_INCLUDE_DIRS}
)

# Source files - Core processing components (reused from desktop)
set(CORE_SOURCES
    src/AudioProcessor.cpp
    src/AlsaAudioEngine.cpp
    src/HttpApiServer.cpp
    src/main.cpp
)

# Copy profanity filter and other helpers from desktop
# Note: You'll need to copy these files manually or update paths
set(DESKTOP_SOURCES
    ../desktop/Source/ProfanityFilter.cpp
    ../desktop/Source/VocalFilter.cpp
    ../desktop/Source/TimestampRefiner.cpp
    ../desktop/Source/LyricsAlignment.cpp
)

# Check if desktop sources exist, otherwise exclude
foreach(SOURCE_FILE ${DESKTOP_SOURCES})
    if(EXISTS "${CMAKE_SOURCE_DIR}/${SOURCE_FILE}")
        list(APPEND CORE_SOURCES ${SOURCE_FILE})
    else()
        message(WARNING "Desktop source not found: ${SOURCE_FILE} - will need to be copied manually")
    endif()
endforeach()

# Create executable
add_executable(explicitly-daemon ${CORE_SOURCES})

# Link libraries
target_link_libraries(explicitly-daemon
    PRIVATE
        ${CMAKE_THREAD_LIBS_INIT}
        ${ALSA_LIBRARIES}
        ${WHISPER_DIR}/libwhisper.a
        m  # Math library
)

# Installation
install(TARGETS explicitly-daemon DESTINATION /usr/local/bin)
install(FILES ${CMAKE_SOURCE_DIR}/config.yaml.example 
        DESTINATION /etc/explicitly 
        RENAME config.yaml
        PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ)
install(FILES ${CMAKE_SOURCE_DIR}/explicitly.service 
        DESTINATION /etc/systemd/system)
install(DIRECTORY DESTINATION /usr/share/explicitly/models)
install(FILES ${CMAKE_SOURCE_DIR}/../desktop/Models/profanity_en.txt 
        DESTINATION /usr/share/explicitly
        OPTIONAL)

# Post-install message
install(CODE "message(\"
==========================================
Explicitly Hardware Installation Complete
==========================================

Next steps:

1. Download Whisper model:
   cd /usr/share/explicitly/models
   wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin

2. Edit configuration:
   sudo nano /etc/explicitly/config.yaml

3. Enable and start service:
   sudo systemctl daemon-reload
   sudo systemctl enable explicitly
   sudo systemctl start explicitly

4. Check status:
   sudo systemctl status explicitly
   curl http://localhost:8080/api/status

==========================================
\")")

# Print build info
message(STATUS "Building Explicitly Hardware for Orange Pi Zero 3")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ compiler: ${CMAKE_CXX_COMPILER}")
message(STATUS "Whisper.cpp: ${WHISPER_DIR}")
message(STATUS "ALSA: ${ALSA_LIBRARIES}")
