// Background service worker for audio capture
let captureStream = null;
let audioContext = null;
let websocket = null;
let isCapturing = false;
let currentTabId = null;
let pendingTabId = null; // Tab waiting for audio to start

const DESKTOP_APP_URL = 'ws://localhost:8765';

// Connect to desktop application
function connectToDesktop() {
  return new Promise((resolve, reject) => {
    console.log('[Extension] Connecting to desktop app at', DESKTOP_APP_URL);
    
    websocket = new WebSocket(DESKTOP_APP_URL);
    
    websocket.onopen = () => {
      console.log('[Extension] ✓ Connected to desktop app');
      resolve();
    };
    
    websocket.onerror = (error) => {
      console.error('[Extension] WebSocket error:', error);
      reject(error);
    };
    
    websocket.onclose = () => {
      console.log('[Extension] Disconnected from desktop app');
      websocket = null;
      stopCapture();
    };
    
    websocket.onmessage = (event) => {
      console.log('[Extension] Message from desktop:', event.data);
    };
  });
}

// Start capturing audio from current tab
async function startCapture(tabId) {
  try {
    console.log('[Extension] Preparing to capture tab', tabId);
    
    // Connect to desktop app first
    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
      await connectToDesktop();
    }
    
    // Try to capture immediately
    captureStream = await new Promise((resolve, reject) => {
      chrome.tabCapture.capture({
        audio: true,
        video: false
      }, (stream) => {
        if (chrome.runtime.lastError) {
          // Tab is not playing audio yet - that's okay, we'll wait
          console.log('[Extension] Tab not playing audio yet, will wait for audio to start...');
          resolve(null);
        } else if (!stream) {
          resolve(null);
        } else {
          resolve(stream);
        }
      });
    });
    
    // If we got a stream immediately, great!
    if (captureStream) {
      const audioTracks = captureStream.getAudioTracks();
      if (audioTracks.length > 0) {
        console.log('[Extension] ✓ Tab audio captured immediately');
        await setupAudioPipeline();
        isCapturing = true;
        currentTabId = tabId;
        return { success: true, message: 'Capturing audio' };
      }
    }
    
    // Otherwise, wait for audio to start
    pendingTabId = tabId;
    console.log('[Extension] ✓ Ready to capture - waiting for audio to play...');
    
    // Create audio context
    audioContext = new AudioContext({
      sampleRate: 16000  // Whisper expects 16kHz
    });
    
    const source = audioContext.createMediaStreamSource(captureStream);
    
    // Create ScriptProcessor for audio processing (deprecated but works)
    // TODO: Migrate to AudioWorklet for better performance
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    
    processor.onaudioprocess = (e) => {
      if (websocket && websocket.readyState === WebSocket.OPEN) {
        const audioData = e.inputBuffer.getChannelData(0);
        
        // Convert Float32Array to Int16Array for efficiency
        const int16Data = new Int16Array(audioData.length);
        for (let i = 0; i < audioData.length; i++) {
          // Convert float [-1, 1] to int16 [-32768, 32767]
          const s = Math.max(-1, Math.min(1, audioData[i]));
          int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        // Send to desktop app
        websocket.send(int16Data.buffer);
      }
    };
    
    source.connect(processor);
    processor.connect(audioContext.destination);
    
    isCapturing = true;
    currentTabId = tabId;
    
    console.log('[Extension] ✓ Audio streaming to desktop app');
    
    return { success: true };
    
  } catch (error) {
    console.error('[Extension] Capture failed:', error);
    stopCapture();
    return { success: false, error: error.message };
  }
}

// Stop capturing audio
function stopCapture() {
  console.log('[Extension] Stopping capture');
  
  if (captureStream) {
    captureStream.getTracks().forEach(track => track.stop());
    captureStream = null;
  }
  
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
  
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.close();
  }
  
  isCapturing = false;
  currentTabId = null;
  
  console.log('[Extension] Capture stopped');
}

// Get capture status
function getStatus() {
  return {
    isCapturing,
    currentTabId,
    connected: websocket && websocket.readyState === WebSocket.OPEN
  };
}

// Handle messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[Extension] Received message:', request);
  
  if (request.action === 'startCapture') {
    startCapture(request.tabId).then(sendResponse);
    return true; // Keep channel open for async response
  }
  
  if (request.action === 'stopCapture') {
    stopCapture();
    sendResponse({ success: true });
    return true;
  }
  
  if (request.action === 'getStatus') {
    sendResponse(getStatus());
    return true;
  }
});

// Clean up when extension is disabled/unloaded
chrome.runtime.onSuspend.addListener(() => {
  console.log('[Extension] Suspending - cleaning up');
  stopCapture();
});

console.log('[Extension] Background service worker loaded');
