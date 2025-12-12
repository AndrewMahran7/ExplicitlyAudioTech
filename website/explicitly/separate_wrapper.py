"""
Simple Demucs wrapper for C++ integration.
Separates vocals from mixed audio using Demucs.
Standalone version - doesn't require explicitly module.
"""

import argparse
import sys
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Separate vocals using Demucs')
    parser.add_argument('--input', required=True, help='Input audio file path')
    parser.add_argument('--output', required=True, help='Output directory path')
    parser.add_argument('--two-stems', default='vocals', help='Two-stem mode (vocals or other)')
    
    args = parser.parse_args()
    
    try:
        # Import demucs
        try:
            from demucs.pretrained import get_model
            from demucs.apply import apply_model
            from demucs.audio import AudioFile, save_audio
            import torch
        except ImportError as e:
            print(f"ERROR: Demucs not installed. Run: pip install demucs", file=sys.stderr)
            print(f"Import error: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Setup device
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {device}", file=sys.stderr)
        
        # Load model
        model = get_model('htdemucs_ft')
        model.to(device)
        
        # Load audio
        wav = AudioFile(args.input).read(
            streams=0,
            samplerate=model.samplerate,
            channels=model.audio_channels
        )
        
        # Add batch dimension
        wav = wav.unsqueeze(0).to(device)
        
        # Apply separation
        with torch.no_grad():
            sources = apply_model(model, wav, device=device)
        
        # Get vocals (index 3 in htdemucs_ft)
        vocals = sources[0, 3]  # batch=0, source=3 (vocals)
        
        # Create output directory structure
        output_path = Path(args.output) / 'htdemucs_ft' / Path(args.input).stem
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save vocals
        vocals_file = output_path / 'vocals.wav'
        save_audio(vocals.cpu(), vocals_file, model.samplerate)
        
        print(f"SUCCESS: Vocals saved to {vocals_file}", file=sys.stderr)
        sys.exit(0)
        
    except Exception as e:
        import traceback
        print(f"ERROR: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
