// Popup UI controller
let currentTab = null;

// Get current tab info
async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

// Check if desktop app is running by asking background script
async function checkDesktopConnection() {
  try {
    // Ask background script about connection status
    const status = await chrome.runtime.sendMessage({ action: 'getStatus' });
    return status.connected;
  } catch (error) {
    // If background script says not connected, assume desktop is available
    // (it will try to connect when user clicks start)
    return true;
  }
}

// Update UI based on status
async function updateUI(status) {
  const connectionIndicator = document.getElementById('connectionIndicator');
  const connectionText = document.getElementById('connectionText');
  const captureStatus = document.getElementById('captureStatus');
  const startButton = document.getElementById('startButton');
  const stopButton = document.getElementById('stopButton');
  
  // Check desktop connection
  const desktopConnected = await checkDesktopConnection();
  
  // Connection status
  if (desktopConnected || status.connected) {
    connectionIndicator.classList.remove('inactive');
    connectionIndicator.classList.add('active');
    connectionText.textContent = 'Connected';
  } else {
    connectionIndicator.classList.remove('active');
    connectionIndicator.classList.add('inactive');
    connectionText.textContent = 'Disconnected';
  }
  
  // Capture status
  if (status.isCapturing) {
    captureStatus.textContent = 'Active';
    startButton.style.display = 'none';
    stopButton.style.display = 'block';
  } else {
    captureStatus.textContent = 'Idle';
    startButton.style.display = 'block';
    stopButton.style.display = 'none';
  }
  
  // Enable/disable start button based on desktop connection
  startButton.disabled = !desktopConnected;
}

// Show error message
function showError(message) {
  const errorDiv = document.getElementById('errorMessage');
  errorDiv.textContent = message;
  errorDiv.style.display = 'block';
  
  setTimeout(() => {
    errorDiv.style.display = 'none';
  }, 5000);
}

// Start capture
async function startCapture() {
  try {
    console.log('[Popup] Starting capture for tab', currentTab.id);
    
    const response = await chrome.runtime.sendMessage({
      action: 'startCapture',
      tabId: currentTab.id
    });
    
    if (response.success) {
      console.log('[Popup] ✓ Capture started');
      await refreshStatus();
    } else {
      showError('Failed to start capture: ' + response.error);
    }
  } catch (error) {
    console.error('[Popup] Start capture error:', error);
    showError('Error: ' + error.message);
  }
}

// Stop capture
async function stopCapture() {
  try {
    console.log('[Popup] Stopping capture');
    
    await chrome.runtime.sendMessage({
      action: 'stopCapture'
    });
    
    console.log('[Popup] ✓ Capture stopped');
    await refreshStatus();
  } catch (error) {
    console.error('[Popup] Stop capture error:', error);
    showError('Error: ' + error.message);
  }
}

// Refresh status
async function refreshStatus() {
  try {
    const status = await chrome.runtime.sendMessage({
      action: 'getStatus'
    });
    
    updateUI(status);
  } catch (error) {
    console.error('[Popup] Status refresh error:', error);
  }
}

// Initialize popup
async function init() {
  currentTab = await getCurrentTab();
  
  // Display current tab info
  const tabInfo = document.getElementById('tabInfo');
  tabInfo.textContent = `📄 ${currentTab.title}`;
  
  // Set up event listeners
  document.getElementById('startButton').addEventListener('click', startCapture);
  document.getElementById('stopButton').addEventListener('click', stopCapture);
  
  // Initial status refresh
  await refreshStatus();
  
  // Auto-refresh status every 2 seconds
  setInterval(refreshStatus, 2000);
}

// Run when popup opens
document.addEventListener('DOMContentLoaded', init);
