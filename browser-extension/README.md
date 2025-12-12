# Explicitly Browser Extension

Browser extension for capturing tab audio and sending it to Explicitly Desktop for real-time censorship.

## Installation

1. **Open Chrome/Edge Extension Page**
   - Chrome: Go to `chrome://extensions/`
   - Edge: Go to `edge://extensions/`

2. **Enable Developer Mode**
   - Toggle "Developer mode" in the top right

3. **Load Extension**
   - Click "Load unpacked"
   - Select the `browser-extension` folder

4. **Verify Installation**
   - You should see "Explicitly Audio Capture" in your extensions list
   - Pin the extension to your toolbar for easy access

## Usage

1. **Start Desktop App**
   - Launch "Explicitly Desktop.exe"
   - The app will start a WebSocket server on port 8765

2. **Open Audio Content**
   - Navigate to YouTube Music, Spotify Web Player, or any audio tab

3. **Start Capturing**
   - Click the Explicitly extension icon
   - Click "Start Capturing This Tab"
   - Audio will stream to desktop app for processing

4. **Stop Capturing**
   - Click extension icon again
   - Click "Stop Capturing"

## How It Works

```
Browser Tab Audio → Extension → WebSocket → Desktop App → Whisper → Censor → Speakers
```

1. Extension captures tab audio using `chrome.tabCapture` API
2. Audio is resampled to 16kHz (Whisper requirement)
3. Sent to desktop app via WebSocket in real-time
4. Desktop app processes and censors audio
5. Clean audio plays through speakers

## Troubleshooting

**Connection Failed:**
- Make sure Explicitly Desktop is running
- Check that port 8765 is not blocked by firewall

**No Audio:**
- Make sure the tab is actually playing audio
- Try refreshing the tab and starting capture again

**Extension Not Working:**
- Check browser console (F12 → Console) for errors
- Make sure you granted tab capture permissions

## Icon Requirements

The extension needs three icon sizes. For now, use placeholder images:
- icon16.png (16x16)
- icon48.png (48x48)
- icon128.png (128x128)

You can create these using any image editor or online tool.
