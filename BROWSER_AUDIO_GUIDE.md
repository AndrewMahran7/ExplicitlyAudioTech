# Browser Audio Capture Guide

## The Simple Solution (RECOMMENDED)

The browser extension approach has limitations due to Chrome's `tabCapture` API requiring audio to be actively playing. Instead, use Windows' built-in per-app audio routing:

### One-Time Setup (30 seconds):

1. **Open Sound Settings:**
   - Right-click speaker icon in taskbar
   - Click "Open Sound settings"

2. **Navigate to App Volume:**
   - Scroll down to "Advanced"
   - Click "App volume and device preferences"

3. **Route Browser to VB-Cable:**
   - Find "Microsoft Edge" or "Google Chrome" in the list
   - Under "Output", select **"CABLE Input (VB-Audio Virtual Cable)"**
   - Leave other apps on "Default" (speakers)

4. **Done!**
   - Now ALL audio from your browser goes to VB-Cable
   - Desktop app captures from VB-Cable automatically
   - No extension needed, always works, zero latency

### Using the Desktop App:

1. Launch Explicitly Desktop
2. Set Input Device: **CABLE Output (VB-Audio Virtual Cable)**
3. Set Output Device: **Speakers** (or your preferred output)
4. Click "Start Processing"
5. Play music in your browser - it will be censored in real-time

## Why This Is Better Than the Extension:

| Manual Routing | Browser Extension |
|----------------|-------------------|
| ✓ Always works | ✗ Requires audio to be playing first |
| ✓ Zero setup after first time | ✗ Must click extension every time |
| ✓ No latency | ✗ ~10ms WebSocket overhead |
| ✓ Works with any browser tab | ✗ One tab at a time |
| ✓ No Chrome API limitations | ✗ Chrome can break it in updates |
| ✓ Lower CPU usage | ✗ Audio resampling overhead |

## What About Other Apps?

You can route **any app** to VB-Cable the same way:
- Spotify Desktop
- Discord
- Zoom
- VLC Media Player
- YouTube Music (browser)
- Apple Music (browser)

Just set that app's output to "CABLE Input" in Windows Sound Settings.

## Troubleshooting:

**"I don't see CABLE Input in the list"**
- VB-Cable isn't installed. Run the VB-Cable installer.

**"Browser audio goes to VB-Cable but I hear nothing"**
- Make sure Desktop app Input Device is "CABLE Output"
- Make sure Desktop app Output Device is "Speakers"
- Click "Start Processing" in the desktop app

**"I want to hear uncensored audio from other apps"**
- Only route the apps you want censored to VB-Cable
- Leave other apps on "Default" output (speakers)

## The Extension Is Optional

The browser extension was an experimental feature to avoid manual routing. However:
- Chrome's API makes it unreliable
- Manual routing is faster and more stable
- You only set it up once

**Recommendation:** Uninstall the extension and use manual routing instead.
