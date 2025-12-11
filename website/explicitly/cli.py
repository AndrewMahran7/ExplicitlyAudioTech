"""
Command-line interface for the Explicitly profanity filtering tool.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml

from . import __version__
from .separate import separate_audio
from .transcribe_align import transcribe_audio
from .detect import detect_profanity
from .censor import AudioCensor
from .remix import remix_audio
from .utils_audio import get_audio_duration
from .word_logger import start_logging_session, log_words, log_profanity, save_logs, get_word_logger

# Create Typer app
app = typer.Typer(
    name="explicitly",
    help="Profanity filtering for audio files using AI-powered speech recognition.",
    add_completion=False
)


def check_device_compatibility(requested_device: str) -> str:
    """
    Check device compatibility and provide helpful messages to users.
    
    This function determines the best available processing device (CPU vs GPU)
    and provides clear guidance if the requested device isn't available.
    GPU processing is much faster but requires CUDA installation.
    
    Args:
        requested_device: User's requested device ("cpu", "cuda", or "auto")
        
    Returns:
        str: The actual device to use ("cpu" or "cuda")
    """
    import torch  # Import here to avoid circular imports
    
    if requested_device == "cuda":
        # User specifically requested CUDA (GPU) processing
        if not torch.cuda.is_available():
            # CUDA not available - show detailed troubleshooting info
            typer.echo("⚠️  CUDA requested but PyTorch not compiled with CUDA support!", err=True)
            typer.echo("\n🔧 To enable GPU acceleration:")
            typer.echo("   1. Check if you have an NVIDIA GPU: nvidia-smi")
            typer.echo("   2. Install CUDA-enabled PyTorch:")
            typer.echo("      pip uninstall torch torchvision torchaudio")
            typer.echo("      pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")
            typer.echo("\n🔄 Falling back to CPU processing (will be slower)...")
            return "cpu"  # Gracefully fall back to CPU
        else:
            # CUDA is available - show GPU name and use it
            typer.echo(f"✅ Using GPU: {torch.cuda.get_device_name(0)}")
            return "cuda"
    elif requested_device == "auto":
        # Auto-detect the best available device
        if torch.cuda.is_available():
            # GPU available - use it for faster processing
            typer.echo(f"✅ Auto-detected GPU: {torch.cuda.get_device_name(0)}")
            return "cuda"
        else:
            # No GPU - use CPU (slower but always works)
            typer.echo("ℹ️  Using CPU processing (no CUDA available)")
            return "cpu"
    else:
        # Return whatever the user requested (usually "cpu")
        return requested_device


def load_config(config_path: Optional[Path] = None) -> dict:
    """
    Load configuration settings from YAML file with fallback to defaults.
    
    This function loads processing parameters like fade durations, model names,
    thresholds, and output settings. It tries multiple locations to find the
    config file and provides sensible defaults if no config is found.
    
    Args:
        config_path: Optional specific path to config file. If None, searches
                    standard locations like config/settings.yaml
        
    Returns:
        dict: Configuration dictionary with all processing parameters
    """
    if config_path is None:
        # Search for config file in standard locations (order matters)
        possible_paths = [
            Path("config/settings.yaml"),           # Current directory config
            Path("../config/settings.yaml"),        # Parent directory config
            Path.cwd() / "config" / "settings.yaml" # Explicit current working directory
        ]
        
        # Find the first config file that exists
        for path in possible_paths:
            if path.exists():
                config_path = path
                break
    
    # Try to load the config file if we found one
    if config_path and config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)  # Parse YAML safely
                typer.echo(f"📋 Loaded config from: {config_path}")
                return config_data
        except Exception as e:
            # Config file exists but couldn't be parsed - warn user but continue
            typer.echo(f"Warning: Failed to load config from {config_path}: {e}", err=True)
    
    # Return sensible default configuration if no config file found
    # These values work well for most use cases
    default_config = {
        # Audio censoring parameters
        "fade_ms": 50,              # Smooth fade when muting (50ms prevents clicks)
        "pre_margin_ms": 100,       # Extra silence before profane word (100ms buffer)
        "post_margin_ms": 100,      # Extra silence after profane word (100ms buffer)
        
        # AI model selection (optimized for quality)
        "demucs_model": "htdemucs_ft",  # Fine-tuned Hybrid Demucs (improved quality)
        "whisper_model": "large",       # Large Whisper model (best accuracy)
        
        # Audio processing settings
        "target_sample_rate": 16000,   # 16kHz sample rate (Whisper requirement)
        
        # Profanity detection parameters
        "profanity_threshold": 0.8,    # Confidence threshold (0.8 = high confidence)
        "normalize_text": True,        # Clean up text (sh*t → shit)
        "case_sensitive": False,       # Ignore capitalization
        
        # Output file settings (optimized for quality)
        "output_format": "wav",        # Output format (WAV for best quality)
        "output_bitrate": "320k"       # High quality audio (320 kbps for MP3)
    }
    
    typer.echo("📋 Using default configuration (no config file found)")
    return default_config


def get_quality_config(quality_preset: str) -> dict:
    """
    Get quality configuration based on preset.
    
    Args:
        quality_preset: Quality preset name (fast/balanced/high/audiophile)
        
    Returns:
        Dictionary with quality settings
    """
    presets = {
        "fast": {
            "demucs_model": "htdemucs",
            "whisper_model": "base.en", 
            "output_format": "wav",
            "output_bitrate": "192k",
            "target_sample_rate": 16000
        },
        "balanced": {
            "demucs_model": "htdemucs_ft",
            "whisper_model": "large",
            "output_format": "wav", 
            "output_bitrate": "320k",
            "target_sample_rate": 22050
        },
        "high": {
            "demucs_model": "htdemucs_ft",
            "whisper_model": "large",
            "output_format": "wav",
            "output_bitrate": "320k", 
            "target_sample_rate": 44100
        },
        "audiophile": {
            "demucs_model": "mdx_extra_q",
            "whisper_model": "large",
            "output_format": "wav",
            "output_bitrate": "320k",
            "target_sample_rate": 48000
        }
    }
    
    if quality_preset not in presets:
        typer.echo(f"⚠️  Unknown quality preset '{quality_preset}', using 'balanced'")
        quality_preset = "balanced"
    
    selected = presets[quality_preset]
    typer.echo(f"🎵 Quality preset: {quality_preset.title()}")
    typer.echo(f"   • Demucs model: {selected['demucs_model']}")
    typer.echo(f"   • Whisper model: {selected['whisper_model']}")
    typer.echo(f"   • Output format: {selected['output_format']}")
    
    return selected


def get_lexicon_path() -> Path:
    """
    Find the profanity lexicon file.
    
    Returns:
        Path to lexicon file
    """
    possible_paths = [
        Path("lexicons/profanity_en.txt"),
        Path("../lexicons/profanity_en.txt"),
        Path.cwd() / "lexicons" / "profanity_en.txt"
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    raise FileNotFoundError(
        "Profanity lexicon not found. Expected at lexicons/profanity_en.txt"
    )


@app.command()
def clean(
    input_file: Path = typer.Argument(..., help="Input audio file"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
    device: str = typer.Option("auto", "--device", "-d", help="Device (auto/cpu/cuda)"),
    model: str = typer.Option("large", "--model", help="Whisper model size"),  # Remove -m to avoid conflict
    quality: str = typer.Option("balanced", "--quality", "-q", help="Quality preset"),
    method: str = typer.Option("mute", "--method", help="Censoring method (mute/bleep/reverse)"),
    analyze_quality: bool = typer.Option(False, "--analyze-quality", help="Run quality analysis"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path")
):
    """
    Clean profanity from an audio file.
    
    This command processes an audio file to detect and censor profane language:
    1. Separates vocals from instrumentals using Demucs
    2. Transcribes speech using Whisper
    3. Detects profane words using lexicon matching
    4. Censors profanity in the vocal track
    5. Remixes clean vocals with instrumental
    6. Generates detailed report
    
    Example:
        explicitly clean song.mp3 --device cuda --method reverse
    """
    try:
        # Load configuration
        config = load_config(config_path)
        
        # Apply quality preset settings
        quality_config = get_quality_config(quality)
        config.update(quality_config)
        
        # Override with command line options
        if model != "large":  # Only update if user specified different model
            config["whisper_model"] = model
        
        # Set up paths
        if output_dir is None:
            output_dir = Path("data/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        stems_dir = Path("data/stems")
        work_dir = Path("data/work")
        stems_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)
        
        # Get lexicon path
        lexicon_file = get_lexicon_path()
        
        # Set device with compatibility check
        if device is None:
            device = "auto"
        device = check_device_compatibility(device)
        
        # Generate output filenames
        base_name = input_file.stem
        clean_audio_path = output_dir / f"{base_name}.clean.{config['output_format']}"
        report_path = output_dir / f"{base_name}.report.json"
        
        typer.echo(f"Processing: {input_file}")
        typer.echo(f"Output directory: {output_dir}")
        typer.echo(f"Device: {device}")
        
        # Start comprehensive word logging
        start_logging_session(str(input_file))
        
        # Step 1: Separate stems
        typer.echo("\n[1/6] Separating audio stems...")
        stem_paths = separate_audio(
            input_file,
            stems_dir,
            model_name=config.get("demucs_model", "htdemucs"),
            device=device
        )
        
        if "vocals" not in stem_paths:
            raise RuntimeError("Failed to separate vocals from audio")
        
        vocals_path = stem_paths["vocals"]
        instrumental_path = stem_paths.get("instrumental", stem_paths.get("other"))
        
        typer.echo(f"  Vocals: {vocals_path}")
        typer.echo(f"  Instrumental: {instrumental_path}")
        
        # Step 2: Transcribe vocals
        typer.echo("\n[2/6] Transcribing speech...")
        word_segments = transcribe_audio(
            vocals_path,
            model=config.get("whisper_model", "base.en"),
            device=device,
            target_sr=config.get("target_sample_rate", 16000)
        )
        
        typer.echo(f"  Found {len(word_segments)} words")
        
        # Log all transcribed words with timestamps
        log_words(word_segments, "whisper_transcription")
        
        # Step 3: Detect profanity
        typer.echo("\n[3/6] Detecting profanity...")
        profane_segments = detect_profanity(
            word_segments,
            lexicon_file,
            normalize_text=config.get("normalize_text", True),
            case_sensitive=config.get("case_sensitive", False),
            confidence_threshold=config.get("profanity_threshold", 0.8)
        )
        
        typer.echo(f"  Detected {len(profane_segments)} profane words")
        
        # Log profanity detection results to word logger
        if profane_segments:
            # Convert WordSegment objects to dictionaries for word logger
            profane_dicts = []
            for segment in profane_segments:
                profane_dicts.append({
                    "word": segment.word,
                    "start": segment.start,
                    "end": segment.end,
                    "confidence": segment.confidence
                })
            
            # Update word logger with profanity detection results
            word_logger = get_word_logger()
            word_logger.log_profanity_detection(profane_dicts)
        
        # Log profanity detection results to convenience logger
        log_profanity(profane_segments)
        
        if len(profane_segments) == 0:
            typer.echo("✅ No profanity detected! Audio is clean.")
            # Copy original file to output
            import shutil
            shutil.copy2(input_file, clean_audio_path)
        else:
            # Show detected profanity
            typer.echo("  Profane words detected:")
            for seg in profane_segments[:10]:  # Show first 10
                typer.echo(f"    '{seg.word}' at {seg.start:.2f}s - {seg.end:.2f}s")
            if len(profane_segments) > 10:
                typer.echo(f"    ... and {len(profane_segments) - 10} more")
            
            # Step 4: Censor vocals
            typer.echo("\n[4/7] Censoring profanity...")
            censored_vocals_path = work_dir / f"{base_name}_vocals_clean.wav"
            
            censor = AudioCensor(
                fade_ms=config.get("fade_ms", 50),
                pre_margin_ms=config.get("pre_margin_ms", 100),
                post_margin_ms=config.get("post_margin_ms", 100),
                censor_method=method
            )
            
            censor_stats = censor.censor_audio(
                vocals_path,
                profane_segments,
                censored_vocals_path,
                instrumental_path=instrumental_path
            )
            
            # Step 5: Remix audio
            typer.echo("\n[5/7] Remixing clean audio...")
            remix_stats = remix_audio(
                censored_vocals_path,
                instrumental_path,
                clean_audio_path,
                output_format=config.get("output_format", "mp3"),
                output_bitrate=config.get("output_bitrate", "320k")
            )
            
            # Step 6: Generate report
            typer.echo("\n[6/7] Generating report...")
            censor.generate_report(
                input_file,
                clean_audio_path,
                profane_segments,
                censor_stats,
                report_path
            )
        
        # Clean up intermediate files (optional - can be removed if you want to keep stems)
        # Uncomment the following lines if you want to automatically clean up temp files:
        # for stem_path in stem_paths.values():
        #     Path(stem_path).unlink(missing_ok=True)
        # for work_file in work_dir.glob(f"{base_name}*"):
        #     work_file.unlink(missing_ok=True)
        
        # Save comprehensive word timeline logs
        typer.echo("\n[7/8] Generating comprehensive logs...")
        log_files = save_logs(include_summary=True)
        
        # Optional quality analysis
        if analyze_quality and len(profane_segments) > 0:
            typer.echo("\n[8/8] Analyzing processing quality...")
            try:
                from .quality_analyzer import analyze_processing_quality
                
                # Set up paths for analysis
                processed_vocals_path = work_dir / f"{base_name}_vocals_clean.wav"
                quality_report_path = output_dir / f"{base_name}.quality_analysis.json"
                
                # Run quality analysis
                quality_results = analyze_processing_quality(
                    input_file,
                    stems_dir,
                    processed_vocals_path,
                    clean_audio_path,
                    quality_report_path
                )
                
                typer.echo(f"Quality analysis report saved: {quality_report_path}")
                
            except Exception as e:
                typer.echo(f"⚠️ Quality analysis failed: {str(e)}")
        
        # Final output
        typer.echo("\n✅ Processing complete!")
        if len(profane_segments) > 0:
            typer.echo(f"  Clean audio: {clean_audio_path}")
            typer.echo(f"  Report: {report_path}")
            
            # Show summary stats
            original_duration = get_audio_duration(input_file)
            censored_duration = sum(seg.end - seg.start for seg in profane_segments)
            censorship_percent = (censored_duration / original_duration) * 100
            
            typer.echo(f"  Censored {censored_duration:.1f}s ({censorship_percent:.1f}%) of audio")
        else:
            typer.echo(f"  Clean audio: {clean_audio_path} (copy of original)")
        
        # Show log file locations
        typer.echo("\n📝 Word timeline logs:")
        for log_type, log_path in log_files.items():
            typer.echo(f"  {log_type.capitalize()}: {log_path}")
        
    except KeyboardInterrupt:
        typer.echo("\n❌ Processing cancelled by user.")
        sys.exit(1)
    except Exception as e:
        typer.echo(f"\n❌ Error: {str(e)}", err=True)
        sys.exit(1)


@app.command()
def analyze(
    input_file: Path = typer.Argument(
        ...,
        help="Input audio file to analyze",
        exists=True,
        file_okay=True,
        dir_okay=False
    ),
    device: Optional[str] = typer.Option(
        "auto",
        "--device", "-d",
        help="Device to use (cpu, cuda, auto)"
    ),
    config_path: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Configuration file path"
    )
):
    """
    Analyze audio file for profanity without creating cleaned version.
    
    This performs transcription and profanity detection but doesn't
    create any output files - useful for quick analysis.
    """
    # Reuse the clean command with dry_run=True
    clean(
        input_file=input_file,
        device=device,
        config_file=config_path,
        dry_run=True
    )


@app.command()
def version():
    """
    Show version information.
    """
    typer.echo(f"Explicitly v{__version__}")


@app.command()
def web(
    port: int = typer.Option(5000, "--port", "-p", help="Port to run the web server on"),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind the web server to")
):
    """
    Start the web interface for easy file processing.
    
    This launches a Flask web server where you can upload audio files,
    select processing models, and download cleaned versions through a
    user-friendly browser interface.
    
    Example:
        explicitly web --port 8080
    """
    try:
        from .web import app as flask_app
        import torch
        
        # Check CUDA availability
        if torch.cuda.is_available():
            typer.echo(f"✅ GPU detected: {torch.cuda.get_device_name(0)}")
        else:
            typer.echo("ℹ️  No GPU detected, using CPU processing")
        
        typer.echo(f"\n🎵 Starting Explicitly Web Interface...")
        typer.echo(f"📍 Open your browser to: http://localhost:{port}")
        typer.echo("Press Ctrl+C to stop the server\n")
        
        flask_app.run(host=host, port=port, debug=False)
        
    except ImportError as e:
        typer.echo("❌ Flask not installed. Install web dependencies:", err=True)
        typer.echo("   pip install flask werkzeug", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error starting web server: {e}", err=True)
        raise typer.Exit(1)


def main():
    """
    Main entry point for the CLI.
    """
    app()


if __name__ == "__main__":
    main()
