"""
Stem separation using Demucs for isolating vocals from instrumentals.

    def __init__(
        self, 
        model_name: str = "htdemucs_ft",   # Demucs model variant (improved quality)
        device: Optional[str] = None       # Processing device preference
    ):module implements AI-powered audio source separation, which is the first
step in the Explicitly pipeline. It uses Facebook's Demucs models to separate
a mixed audio file into its component "stems" (individual audio sources).

Why stem separation is essential:
1. Profanity detection only works on vocals (speech), not instruments
2. Censoring the full mix would also mute instruments during profane words
3. Separating allows us to censor only vocals, then remix with clean instrumentals
4. This preserves musical backing while removing offensive speech

Demucs AI models:
- htdemucs: Hybrid Transformer Demucs (best quality, recommended)
- hdemucs: Hybrid Demucs (good quality, faster)
- mdx models: Various specialized models

Typical output stems:
- vocals: All human speech and singing
- drums: Drum kit and percussion
- bass: Bass guitar and low-frequency instruments  
- other: Everything else (guitars, keyboards, effects, etc.)

The separation process:
1. Load mixed audio file
2. Convert to format expected by Demucs (stereo, correct sample rate)
3. Run AI model to predict individual stems
4. Save separated stems as individual WAV files
5. Return paths to vocals and instrumental (other) stems
"""

# Force CPU usage to avoid CUDA/cuDNN library issues
# This prevents GPU-related errors when CUDA isn't properly installed
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Hide CUDA devices
os.environ["TORCH_USE_CUDA_DSA"] = "0"    # Disable CUDA assertions

# Standard library imports
import tempfile               # Temporary file handling during processing
from pathlib import Path      # Modern path operations
from typing import Dict, Union, Optional  # Type hints for clarity

# Core processing libraries
import numpy as np           # Numerical arrays for audio data
import torch                 # PyTorch for AI model execution

# Demucs AI source separation library
from demucs import pretrained        # Pre-trained model loading
from demucs.apply import apply_model # Model inference engine
from demucs.audio import convert_audio  # Audio format conversion

# Internal audio utilities
from .utils_audio import load_audio, save_audio


class StemSeparator:
    """
    Handles audio stem separation using Facebook's Demucs AI models.
    
    This class manages the complete stem separation pipeline from loading
    pre-trained AI models to processing audio files and saving the results.
    It handles device management, audio format conversion, and graceful
    error handling.
    
    The separation process uses deep learning models trained on thousands
    of songs to predict what each instrument/voice should sound like when
    isolated from the mix. This is computationally intensive but produces
    high-quality results.
    
    Key features:
    - Multiple Demucs model support (htdemucs recommended for best quality)
    - Automatic device selection (GPU for speed, CPU for compatibility)
    - Audio format handling (converts to model requirements automatically)
    - Multiple output stems (vocals, drums, bass, other)
    - Error handling with informative messages
    """
    
    def __init__(
        self, 
        model_name: str = "mdx_extra_q",      # Demucs model variant
        device: Optional[str] = None       # Processing device preference
    ):
        """
        Initialize the stem separator with model and device configuration.
        
        Loads the specified Demucs model and prepares it for audio processing.
        The model is loaded immediately to catch any configuration issues early.
        
        Args:
            model_name: Demucs model to use for separation:
                       - "htdemucs_ft": Fine-tuned Hybrid Transformer (best quality) [DEFAULT]
                       - "htdemucs": Hybrid Transformer (excellent quality)
                       - "htdemucs_6s": 6-stem model (higher quality, slower)
                       - "mdx_extra_q": MDX Extra Quality (audiophile choice)
                       - "hdemucs": Hybrid model (good quality, faster)
            device: Processing device preference:
                   - None: Auto-detect best available device
                   - "cpu": Force CPU processing (slower but always works)
                   - "cuda": Force GPU processing (much faster with NVIDIA GPU)
                   - "auto": Automatically choose best available device
        """
        # Store configuration
        self.model_name = model_name            # Which Demucs model to use
        self.device = self._get_device(device)  # Resolved processing device
        self.model = None                       # Will store loaded model
        
        # Load the AI model immediately
        self._load_model()
    
    def _get_device(self, device: Optional[str]) -> str:
        """
        Determine the best processing device with intelligent fallbacks.

        Device selection is crucial for performance:
        - GPU (CUDA): 5-10x faster than CPU, but requires NVIDIA GPU + CUDA installation
        - CPU: Slower but works on any system, good fallback option
        
        This method checks hardware availability and provides helpful guidance
        if the requested device isn't available.

        Args:
            device: User's device preference ("cpu", "cuda", "auto", or None)
            
        Returns:
            str: The actual device to use ("cpu" or "cuda")
        """
        if device is None or device == "auto":
            # Auto-detect best available device
            if torch.cuda.is_available():
                # CUDA is available - use GPU for much faster processing
                print("GPU (CUDA) detected and available for stem separation")
                return "cuda"
            else:
                # No CUDA - use CPU (slower but works everywhere)
                print("Using CPU processing (CUDA not available)")
                return "cpu"
        elif device == "cuda":
            # User specifically requested CUDA
            if not torch.cuda.is_available():
                # CUDA not available - show helpful installation instructions
                print("⚠️  Warning: CUDA requested but not available. Install CUDA-enabled PyTorch:")
                print("   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")
                print("   Falling back to CPU processing...")
                return "cpu"  # Graceful fallback
            else:
                # CUDA is available - show GPU info and use it
                print(f"Using GPU: {torch.cuda.get_device_name(0)}")
                return "cuda"
        # Return whatever device was requested (usually "cpu")
        return device
    
    def _load_model(self) -> None:
        """
        Load and initialize the pre-trained Demucs AI model.
        
        Downloads the model weights if not already cached locally.
        Models are typically 200-500MB and stored in ~/.cache/torch/hub/checkpoints/
        
        The loading process:
        1. Download model weights (first time only)
        2. Load model architecture and weights into memory
        3. Move model to specified device (CPU/GPU)
        4. Set to evaluation mode (disable training-specific layers)
        
        Raises:
            RuntimeError: If model loading fails (network issues, corrupted files, etc.)
        """
        try:
            print(f"Loading Demucs model '{self.model_name}' on {self.device}...")
            
            # Download and load pre-trained model weights
            # This will download ~200-500MB on first run
            self.model = pretrained.get_model(self.model_name)
            
            # Move model to processing device (CPU or CUDA GPU)
            self.model.to(self.device)
            
            # Set to evaluation mode (disables dropout, batch norm training mode)
            self.model.eval()
            
            print("Model loaded successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to load Demucs model: {str(e)}")
    
    def separate(
        self, 
        audio_path: Union[str, Path], 
        output_dir: Union[str, Path]
    ) -> Dict[str, str]:
        """
        Separate audio into individual stems using the loaded Demucs model.
        
        This is the core separation method that handles the entire pipeline:
        1. Load audio file and convert to proper format
        2. Run AI model inference to predict individual stems
        3. Save each stem as a separate WAV file
        4. Return paths to all generated stem files
        
        The separation process is computationally intensive and may take
        1-5 minutes per song depending on length and processing device.
        
        Args:
            audio_path: Path to input audio file (MP3, WAV, FLAC, etc.)
            output_dir: Directory to save separated stem files
            
        Returns:
            Dictionary mapping stem names to their file paths:
            {
                'vocals': '/path/to/song_vocals.wav',
                'drums': '/path/to/song_drums.wav', 
                'bass': '/path/to/song_bass.wav',
                'other': '/path/to/song_other.wav'
            }
            
        Raises:
            RuntimeError: If separation fails (corrupted audio, insufficient memory, etc.)
        """
        try:
            print(f"Separating stems for: {audio_path}")
            
            # Load and prepare audio
            audio, sr = load_audio(audio_path, sr=None, mono=False)
            
            # Convert to torch tensor
            if len(audio.shape) == 1:
                # Mono to stereo
                audio = audio[None, :].repeat(2, axis=0)
            
            # Ensure correct format for Demucs
            audio_tensor = torch.from_numpy(audio).float().to(self.device)
            if len(audio_tensor.shape) == 2:
                audio_tensor = audio_tensor.unsqueeze(0)  # Add batch dimension
            
            # Convert audio to model's expected sample rate and format
            audio_tensor = convert_audio(
                audio_tensor, sr, self.model.samplerate, self.model.audio_channels
            )
            
            # Apply separation
            with torch.no_grad():
                stems = apply_model(
                    self.model, 
                    audio_tensor, 
                    device=self.device,
                    progress=True
                )
            
            # Save stems
            output_paths = {}
            stem_names = self.model.sources
            
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            base_name = Path(audio_path).stem
            
            for i, stem_name in enumerate(stem_names):
                stem_audio = stems[0, i].cpu().numpy()  # Remove batch dim, get stem
                
                # Convert back to original sample rate if needed
                if self.model.samplerate != sr:
                    from .utils_audio import resample_audio
                    if len(stem_audio.shape) == 2:
                        # Handle stereo
                        resampled = []
                        for channel in range(stem_audio.shape[0]):
                            resampled.append(
                                resample_audio(
                                    stem_audio[channel], 
                                    self.model.samplerate, 
                                    sr
                                )
                            )
                        stem_audio = np.stack(resampled)
                    else:
                        stem_audio = resample_audio(
                            stem_audio, self.model.samplerate, sr
                        )
                
                # Save stem
                stem_path = output_dir / f"{base_name}_{stem_name}.wav"
                
                # Transpose for soundfile (channels_last)
                if len(stem_audio.shape) == 2:
                    stem_audio = stem_audio.T
                
                save_audio(stem_audio, stem_path, sr)
                output_paths[stem_name] = str(stem_path)
                
                print(f"Saved {stem_name} stem: {stem_path}")
            
            return output_paths
            
        except Exception as e:
            raise RuntimeError(f"Stem separation failed: {str(e)}")
    
    def separate_vocals_instrumental(
        self, 
        audio_path: Union[str, Path], 
        output_dir: Union[str, Path]
    ) -> Dict[str, str]:
        """
        Convenience method focused on vocals vs instrumentals separation.
        
        This method is specifically designed for the profanity filtering use case
        where we only need vocals (for processing) and instrumentals (for mixing).
        It simplifies the full stem separation into just two components.
        
        The method:
        1. Runs full stem separation (vocals, drums, bass, other)
        2. Keeps vocals stem as-is
        3. Uses 'other' stem as instrumental (or combines if needed)
        4. Returns simplified vocal/instrumental mapping
        
        This is the preferred method for Explicitly's workflow since we don't
        need individual instrument stems - just speech vs everything else.
        
        Args:
            audio_path: Path to input audio file (any supported format)
            output_dir: Directory to save the two output files
            
        Returns:
            Dictionary with exactly two entries:
            {
                'vocals': '/path/to/song_vocals.wav',      # Speech/singing only
                'instrumental': '/path/to/song_other.wav'   # All instruments
            }
        """
        all_stems = self.separate(audio_path, output_dir)
        
        # Map stems to vocals/instrumental
        result = {}
        
        if 'vocals' in all_stems:
            result['vocals'] = all_stems['vocals']
        
        # Combine non-vocal stems into instrumental
        instrumental_stems = [
            stem for stem_name, stem in all_stems.items() 
            if stem_name != 'vocals'
        ]
        
        if instrumental_stems:
            # If multiple instrumental stems, we should mix them
            # For now, just use the first non-vocal stem or 'other' if available
            if 'other' in all_stems:
                result['instrumental'] = all_stems['other']
            elif len(instrumental_stems) == 1:
                result['instrumental'] = instrumental_stems[0]
            else:
                # Mix multiple stems - this would require additional logic
                # For MVP, just use the first one
                result['instrumental'] = instrumental_stems[0]
        
        return result


def separate_audio(
    input_path: Union[str, Path],
    output_dir: Union[str, Path],
    model_name: str = "htdemucs_ft",  # Default to higher quality model
    device: Optional[str] = None
) -> Dict[str, str]:
    """
    One-shot convenience function for audio stem separation.
    
    This is a simple wrapper that creates a StemSeparator instance,
    runs separation, and returns the results. Useful for quick scripts
    or one-off separations without managing the separator object.
    
    For batch processing multiple files, it's more efficient to create
    a single StemSeparator instance and reuse it (avoids reloading the
    model for each file).
    
    Args:
        input_path: Path to input audio file to separate
        output_dir: Directory where separated stems will be saved
        model_name: Demucs model variant ("htdemucs" recommended)
        device: Processing device (None for auto, "cpu", or "cuda")
        
    Returns:
        Dictionary with 'vocals' and 'instrumental' file paths
        
    Example:
        >>> stems = separate_audio("song.mp3", "output/", "htdemucs")
        >>> print(stems['vocals'])    # "output/song_vocals.wav"
        >>> print(stems['instrumental'])  # "output/song_other.wav"
    """
    separator = StemSeparator(model_name, device)
    return separator.separate_vocals_instrumental(input_path, output_dir)
