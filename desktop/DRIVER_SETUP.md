# Virtual Audio Driver Setup Guide

## Overview

The Explicitly Desktop application requires a virtual audio device to capture audio from applications without affecting other system sounds. This guide covers setup for both quick development (using VB-Cable) and production deployment (custom driver).

## Quick Setup: VB-Cable (Recommended for Development)

### Installation

1. **Download VB-Cable**
   - Visit: https://vb-audio.com/Cable/
   - Download: `VBCABLE_Driver_Pack43.zip`
   - Extract to temporary folder

2. **Install Driver**
   ```powershell
   # Run as Administrator
   cd path\to\VBCABLE_Driver_Pack43
   .\VBCABLE_Setup_x64.exe
   
   # Or right-click > Run as Administrator
   ```

3. **Restart Computer**
   - **Important**: Restart required for driver to load properly
   
4. **Verify Installation**
   ```powershell
   # Open Sound Settings
   # Windows 11: Settings > System > Sound
   # Windows 10: Control Panel > Sound
   
   # You should see two new devices:
   # Output: "CABLE Input" (VB-Audio Virtual Cable)
   # Input: "CABLE Output" (VB-Audio Virtual Cable)
   ```

### Configuration for Explicitly

1. **Set Default Output in Explicitly App**
   - Launch `ExplicitlyDesktop.exe`
   - Click "Audio Settings"
   - **Input Device**: Select "CABLE Output"
   - **Output Device**: Select your real speakers/headphones

2. **Route Application Audio to VB-Cable**
   - Open application you want to filter (Spotify, Chrome, etc.)
   - Right-click speaker icon in system tray
   - Click "Open Volume Mixer"
   - For each app to filter:
     - Click dropdown under app name
     - Select "CABLE Input (VB-Audio Virtual Cable)"

3. **Start Processing**
   - Click "Start" in Explicitly app
   - Music will now play with 10-second delay, profanity filtered

### Audio Routing Diagram (VB-Cable)

```
┌─────────────────────┐
│  Spotify / Chrome   │
│  (Output Device:    │
│   CABLE Input)      │
└──────────┬──────────┘
           │ Audio Stream
           ↓
┌─────────────────────┐
│  VB-Cable Driver    │
│  (Virtual Device)   │
└──────────┬──────────┘
           │ Captured Audio
           ↓
┌─────────────────────┐
│ Explicitly Desktop  │
│ (Input: CABLE Out)  │
│ [10-sec buffer]     │
│ [ML Processing]     │
│ [Censorship]        │
└──────────┬──────────┘
           │ Filtered Audio
           ↓
┌─────────────────────┐
│ Real Speakers/      │
│ Headphones          │
└─────────────────────┘
```

## Production Setup: Custom Driver

### Overview

For production deployment, you should create a custom branded driver:
- Branded as "Explicitly Filter" (not VB-Cable)
- Signed with your code signing certificate
- Installable via standard Windows installer
- No third-party dependencies

### Prerequisites

1. **Windows Driver Kit (WDK)**
   ```powershell
   # Download from:
   # https://docs.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk
   
   # Or use Visual Studio Installer:
   # Modify VS 2022 > Individual Components
   # ☑ Windows 11 SDK
   # ☑ Windows Driver Kit
   ```

2. **Code Signing Certificate**
   ```powershell
   # Required for Windows 10/11 driver installation
   # Options:
   # - Purchase EV code signing cert ($300-500/year)
   #   Providers: DigiCert, Sectigo, GlobalSign
   # - Use test signing for development (no cert needed)
   ```

3. **Explicitly Driver Source**
   ```powershell
   cd C:\Users\andre\Desktop\Explicitly\desktop\Driver
   # Source files will be provided after ML integration is complete
   ```

### Building Custom Driver

1. **Open Driver Project**
   ```powershell
   # Open Visual Studio 2022
   # File > Open > Project/Solution
   # Navigate to: desktop\Driver\ExplicitlyDriver.sln
   ```

2. **Configure Driver**
   - Edit `driver.inf`:
     ```inf
     [Version]
     Signature="$WINDOWS NT$"
     Class=MEDIA
     ClassGuid={4d36e96c-e325-11ce-bfc1-08002be10318}
     Provider=%ProviderName%
     DriverVer=12/09/2024,1.0.0.0
     CatalogFile=explicitly.cat
     
     [Strings]
     ProviderName="Explicitly Audio Systems"
     DeviceName="Explicitly Filter"
     ```

3. **Build Driver**
   ```powershell
   # In Visual Studio:
   # Build > Configuration Manager
   # Active solution configuration: Release
   # Active solution platform: x64
   # Build > Build Solution (Ctrl+Shift+B)
   ```

4. **Test Signing (Development)**
   ```powershell
   # Enable test signing mode
   bcdedit /set testsigning on
   # Restart required
   
   # Sign driver
   cd desktop\Driver\x64\Release
   signtool sign /v /s PrivateCertStore /n "Test Certificate" /t http://timestamp.digicert.com ExplicitlyDriver.sys
   ```

5. **Install Driver**
   ```powershell
   # Run as Administrator
   cd desktop\Driver\x64\Release
   pnputil /add-driver explicitly.inf /install
   
   # Verify installation
   pnputil /enum-drivers | findstr "Explicitly"
   ```

### Production Signing

1. **Obtain EV Code Signing Certificate**
   - Purchase from certificate authority
   - Typically delivered on USB token
   - Cost: $300-500/year

2. **Sign Driver Package**
   ```powershell
   # Sign .sys file
   signtool sign /v /ac "DigiCert High Assurance EV Root CA.crt" `
     /n "Explicitly Audio Systems" `
     /t http://timestamp.digicert.com `
     /fd sha256 `
     ExplicitlyDriver.sys
   
   # Create catalog file
   inf2cat /driver:. /os:10_X64,10_X86
   
   # Sign catalog
   signtool sign /v /ac "DigiCert High Assurance EV Root CA.crt" `
     /n "Explicitly Audio Systems" `
     /t http://timestamp.digicert.com `
     /fd sha256 `
     explicitly.cat
   ```

3. **Submit for Microsoft Attestation** (Windows 10 1607+)
   ```powershell
   # Create submission package
   # https://partner.microsoft.com/dashboard/hardware/driver/create
   
   # Upload .cab file with:
   # - explicitly.sys
   # - explicitly.inf
   # - explicitly.cat
   
   # Microsoft will countersign and return signed package
   ```

### Creating Installer

1. **Setup WiX Toolset**
   ```powershell
   # Download from: https://wixtoolset.org/
   # Or use winget
   winget install WiX.Toolset
   ```

2. **Build Installer**
   ```powershell
   cd desktop\Installer
   
   # Compile installer
   candle ExplicitlySetup.wxs
   light ExplicitlySetup.wixobj -out ExplicitlySetup.msi
   
   # Sign installer
   signtool sign /v /n "Explicitly Audio Systems" `
     /t http://timestamp.digicert.com `
     /fd sha256 `
     ExplicitlySetup.msi
   ```

3. **Test Installation**
   ```powershell
   # Run as Administrator
   msiexec /i ExplicitlySetup.msi /l*v install.log
   
   # Verify
   # Control Panel > Sound > Playback Devices
   # Should see "Explicitly Filter"
   ```

## Troubleshooting

### Driver Not Appearing in Sound Settings

```powershell
# Check driver status
pnputil /enum-devices /class MEDIA

# Restart audio service
net stop audiosrv
net start audiosrv

# Check Event Viewer for errors
eventvwr.msc
# Windows Logs > System
# Look for errors from "Explicitly" or "Audio"
```

### "Driver is not digitally signed" Error

```powershell
# Enable test signing (development only)
bcdedit /set testsigning on
shutdown /r /t 0

# For production: Must use valid code signing certificate
```

### Audio Crackling/Dropouts

```powershell
# Increase buffer size in driver
# Edit driver.inf:
# [ExplicitlyDevice.AddReg]
# HKR,,BufferSize,0x00010001,4096  ; Increase from 2048
```

### Application Can't Find Virtual Device

```powershell
# Check device is enabled
# Sound Settings > Playback > Right-click device > Enable

# Verify app has audio permissions
# Settings > Privacy > Microphone/Audio
# ☑ Allow apps to access microphone
```

## Alternative Solutions

### Option: Virtual Audio Cable (VAC)

Similar to VB-Cable but paid ($25):
- https://vac.muzychenko.net/
- More stable than VB-Cable
- Better multi-channel support

### Option: VoiceMeeter

Free virtual mixer with multiple devices:
- https://vb-audio.com/Voicemeeter/
- More features but heavier
- Good for complex routing

### Option: OBS Virtual Camera

If you already use OBS:
- OBS Studio includes virtual audio device
- Tools > VirtualCam
- Can capture desktop audio

## Support

For driver issues:
- VB-Cable: https://vb-audio.com/Services/support.htm
- Custom driver: support@explicitly.audio
- GitHub: github.com/explicitly/desktop/issues
