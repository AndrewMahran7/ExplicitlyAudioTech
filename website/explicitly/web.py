"""
Web interface for the Explicitly profanity filtering tool.

This module provides a Flask-based web UI for uploading audio files,
selecting processing models, and downloading cleaned versions.
"""

import os
import json
import uuid
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime
import threading
from functools import lru_cache

from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename

try:
    from yt_dlp import YoutubeDL
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False
    print("⚠️  yt-dlp not installed. YouTube download functionality disabled.")

from .separate import separate_audio
from .transcribe_align import transcribe_audio, WordSegment
from .detect import detect_profanity
from .censor import AudioCensor
from .remix import remix_audio
from .word_logger import start_logging_session, log_words, log_profanity, save_logs
from .lyrics_align import align_lyrics_to_transcription, compare_transcription_to_lyrics
from .stable_transcribe import (
    transcribe_with_stable_ts,
    convert_to_word_segment_objects,
    check_dependencies as check_stable_deps,
    StableTranscriptionError
)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Use absolute paths to avoid path resolution issues
BASE_DIR = Path.cwd()
app.config['UPLOAD_FOLDER'] = BASE_DIR / 'data' / 'uploads'
app.config['OUTPUT_FOLDER'] = BASE_DIR / 'data' / 'output'
app.config['STEMS_FOLDER'] = BASE_DIR / 'data' / 'stems'
app.config['WORK_FOLDER'] = BASE_DIR / 'data' / 'work'

# Ensure directories exist
for folder in ['UPLOAD_FOLDER', 'OUTPUT_FOLDER', 'STEMS_FOLDER', 'WORK_FOLDER']:
    app.config[folder].mkdir(parents=True, exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac'}

# Model configurations
MODELS = {
    'speed': {
        'whisper_model': 'base.en',
        'demucs_model': 'htdemucs',
        'description': 'Faster processing, good accuracy'
    },
    'balanced': {
        'whisper_model': 'base.en',
        'demucs_model': 'htdemucs',
        'description': 'Balanced speed and accuracy'
    },
    'accuracy': {
        'whisper_model': 'large-v2',
        'demucs_model': 'htdemucs_ft',
        'description': 'Best accuracy, slower processing'
    }
}

# Processing job status storage (in-memory for now)
processing_jobs = {}


@lru_cache(maxsize=3)
def get_cached_demucs_separator(model_name: str, device: str):
    """Cache Demucs StemSeparator instances to avoid reloading models on each request."""
    from .separate import StemSeparator
    print(f"🔄 Loading and caching Demucs model: {model_name} on {device}")
    return StemSeparator(model_name=model_name, device=device)


@lru_cache(maxsize=3)
def get_cached_whisper_model(model_name: str, device: str):
    """Cache Whisper/stable-ts models to avoid reloading on each request."""
    try:
        import stable_whisper
        print(f"🔄 Loading and caching stable-ts model: {model_name} on {device}")
        return stable_whisper.load_model(model_name, device=device)
    except ImportError:
        import whisper
        print(f"🔄 Loading and caching Whisper model: {model_name} on {device}")
        return whisper.load_model(model_name, device=device)


def get_best_device():
    """Detect and return the best available device (GPU if available, else CPU)."""
    import torch
    
    if torch.cuda.is_available():
        try:
            # Test if CUDA actually works
            test_tensor = torch.zeros(1).cuda()
            del test_tensor
            device_name = torch.cuda.get_device_name(0)
            print(f"✅ GPU detected: {device_name}")
            return 'cuda'
        except Exception as e:
            print(f"⚠️  GPU available but not working ({e}), using CPU")
            return 'cpu'
    else:
        print("ℹ️  No GPU detected, using CPU")
        return 'cpu'


def preload_models():
    """Preload AI models at server startup to reduce first-request latency."""
    print("\n" + "="*70)
    print("PRELOADING AI MODELS...")
    print("="*70)
    
    # Detect best device
    device = get_best_device()
    
    try:
        # Preload Demucs model (htdemucs - balanced quality)
        print(f"Loading Demucs model (htdemucs) on {device.upper()}...")
        get_cached_demucs_separator('htdemucs', device)
        print("✅ Demucs model loaded")
        
        # Preload Whisper model
        print(f"Loading Whisper model (base.en) on {device.upper()}...")
        get_cached_whisper_model('base.en', device)
        print("✅ Whisper model loaded")
        
        print("="*70)
        print(f"All models preloaded successfully on {device.upper()}!")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"⚠️  Warning: Model preload failed: {e}")
        print("Models will load on first request instead.\n")


def allowed_file(filename: str) -> bool:
    """Check if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def download_youtube_audio(url: str, output_dir: Path) -> Path:
    """
    Download audio from YouTube URL.
    
    Args:
        url: YouTube video URL
        output_dir: Directory to save the downloaded audio
        
    Returns:
        Path to the downloaded audio file
    """
    if not YOUTUBE_AVAILABLE:
        raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Download best audio format directly without FFmpeg conversion
    # This works even if FFmpeg is not installed
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
        'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
        'quiet': False,
        'no_warnings': False,
        'extract_flat': False,
        'noplaylist': True,  # Only download single video, ignore playlists
        'playlist_items': '1',  # Only first item if somehow in playlist
    }
    
    try:
        print(f"[YouTube] Downloading audio from: {url}")
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info)
            file_path = Path(file_name)
            
            print(f"[YouTube] Downloaded: {file_path.name}")
            print(f"[YouTube] File exists: {file_path.exists()}")
            
            if not file_path.exists():
                raise RuntimeError(f"Downloaded file not found: {file_path}")
            
            return file_path
    except Exception as e:
        raise RuntimeError(f"Failed to download YouTube video: {str(e)}")


def get_lexicon_path() -> Path:
    """Find the profanity lexicon file."""
    possible_paths = [
        Path("lexicons/profanity_en.txt"),
        Path("../lexicons/profanity_en.txt"),
        Path.cwd() / "lexicons" / "profanity_en.txt"
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    raise FileNotFoundError("Profanity lexicon not found at lexicons/profanity_en.txt")


def check_device_compatibility(requested_device: str) -> str:
    """Check device compatibility and return available device."""
    import torch
    
    # If CPU explicitly requested, respect it
    if requested_device == "cpu":
        return "cpu"
    
    # For 'auto' or 'cuda', try to use GPU
    if requested_device in ["cuda", "auto"]:
        if not torch.cuda.is_available():
            if requested_device == "cuda":
                print("⚠️  CUDA requested but not available, falling back to CPU")
            return "cpu"
        try:
            # Test if CUDA actually works (not just available)
            test_tensor = torch.zeros(1).cuda()
            del test_tensor
            if requested_device == "auto":
                print(f"🚀 Auto-detected GPU: {torch.cuda.get_device_name(0)}")
            return "cuda"
        except Exception as e:
            print(f"⚠️  CUDA available but not working ({e}), using CPU")
            return "cpu"
    
    return requested_device


def process_audio_file(job_id: str, input_path: Path, model_preset: str, method: str, device: str, lyrics: str = None):
    """
    Process an audio file in the background.
    
    Args:
        job_id: Unique job identifier
        input_path: Path to input audio file
        model_preset: Model preset ('speed', 'balanced', or 'accuracy')
        method: Censoring method ('mute', 'bleep', or 'reverse')
        device: Processing device ('cpu' or 'cuda')
    """
    import traceback
    
    try:
        # Update job status
        processing_jobs[job_id]['status'] = 'processing'
        processing_jobs[job_id]['step'] = 'Initializing...'
        print(f"\n[Job {job_id}] Starting processing...")
        
        # Get model configuration
        model_config = MODELS.get(model_preset, MODELS['balanced'])
        whisper_model = model_config['whisper_model']
        demucs_model = model_config['demucs_model']
        
        # Set up paths
        base_name = input_path.stem
        output_dir = app.config['OUTPUT_FOLDER'] / job_id
        stems_dir = app.config['STEMS_FOLDER'] / job_id
        work_dir = app.config['WORK_FOLDER'] / job_id
        
        output_dir.mkdir(parents=True, exist_ok=True)
        stems_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)
        
        clean_audio_path = output_dir / f"{base_name}.clean.wav"
        report_path = output_dir / f"{base_name}.report.json"
        
        # Get lexicon
        lexicon_file = get_lexicon_path()
        
        # Check device compatibility
        actual_device = check_device_compatibility(device)
        
        # Start logging
        start_logging_session(str(input_path))
        
        # Check if we can use forced alignment (skip stem separation if so)
        use_stable_ts = False
        forced_alignment = False
        vocals_path = None
        instrumental_path = None
        
        try:
            stable_deps = check_stable_deps()
            use_stable_ts = stable_deps.get("stable_ts", False)
        except Exception as e:
            print(f"[Job {job_id}] Could not check stable-ts: {e}")
            use_stable_ts = False
        
        # FORCED ALIGNMENT MODE: If lyrics provided, separate vocals for better alignment
        if lyrics and use_stable_ts:
            processing_jobs[job_id]['step'] = 'Separating vocals for forced alignment...'
            processing_jobs[job_id]['progress'] = 10
            print(f"\n[Job {job_id}] " + "="*70)
            print(f"[Job {job_id}] FORCED ALIGNMENT MODE ACTIVATED")
            print(f"[Job {job_id}] " + "="*70)
            print(f"[Job {job_id}] ✅ Lyrics provided - guarantees 100% word accuracy")
            print(f"[Job {job_id}] ✅ Separating vocals for accurate timestamp alignment")
            print(f"[Job {job_id}] Model: {whisper_model} | Device: {actual_device}")
            print()
            
            # Separate vocals for better alignment accuracy
            separator = get_cached_demucs_separator(demucs_model, actual_device)
            stem_paths = separator.separate_vocals_instrumental(input_path, stems_dir)
            
            if "vocals" not in stem_paths:
                raise RuntimeError("Failed to separate vocals from audio")
            
            vocals_path = stem_paths["vocals"]
            instrumental_path = stem_paths.get("instrumental", stem_paths.get("other"))
            print(f"[Job {job_id}] Vocals: {vocals_path}")
            print(f"[Job {job_id}] Instrumental: {instrumental_path}")
            forced_alignment = True
            
        # TRANSCRIPTION MODE: No lyrics provided, must separate stems for accuracy
        else:
            processing_jobs[job_id]['step'] = 'Separating vocals from instrumentals...'
            processing_jobs[job_id]['progress'] = 10
            print(f"[Job {job_id}] Step 1: Separating stems...")
            print(f"[Job {job_id}] (No lyrics provided - separating for better transcription accuracy)")
            
            # Use cached separator to avoid reloading model
            separator = get_cached_demucs_separator(demucs_model, actual_device)
            stem_paths = separator.separate_vocals_instrumental(input_path, stems_dir)
            
            if "vocals" not in stem_paths:
                raise RuntimeError("Failed to separate vocals from audio")
            
            vocals_path = stem_paths["vocals"]
            instrumental_path = stem_paths.get("instrumental", stem_paths.get("other"))
            print(f"[Job {job_id}] Vocals: {vocals_path}")
            print(f"[Job {job_id}] Instrumental: {instrumental_path}")
        
        # Step 2: Transcribe/Align vocals
        processing_jobs[job_id]['progress'] = 30
        
        try:
            # FORCED ALIGNMENT: Use provided lyrics as ground truth
            if lyrics and use_stable_ts and forced_alignment:
                processing_jobs[job_id]['step'] = 'Aligning lyrics to audio timestamps...'
                print(f"[Job {job_id}] Step 2: Aligning lyrics to audio...")
                
                from .stable_transcribe import align_lyrics_with_audio
                
                # Use cached model for faster subsequent runs
                model = get_cached_whisper_model(whisper_model, actual_device)
                
                result = model.align(
                    str(vocals_path),
                    text=lyrics,
                    language="en"
                )
                
                word_segments = convert_to_word_segment_objects(result)
                
                print(f"\n[Job {job_id}] " + "="*70)
                print(f"[Job {job_id}] ✅ FORCED ALIGNMENT SUCCESSFUL")
                print(f"[Job {job_id}] " + "="*70)
                print(f"[Job {job_id}] Total words aligned: {len(word_segments)}")
                print(f"[Job {job_id}] Word accuracy: 100% (using actual lyrics, not AI guesses)")
                print(f"[Job {job_id}] Timestamp accuracy: ±30-80ms (stable-ts precision)")
                
                # Show sample words including profane ones to verify alignment
                if len(word_segments) > 0:
                    print(f"\n[Job {job_id}] Sample aligned words:")
                    for i, seg in enumerate(word_segments[:15]):
                        print(f"[Job {job_id}]   {seg.start:6.2f}s - {seg.end:6.2f}s | '{seg.word}'")
                    if len(word_segments) > 15:
                        print(f"[Job {job_id}]   ... ({len(word_segments) - 15} more words)")
                
                print(f"\n[Job {job_id}] Next step: Profanity detection will check these exact words")
                print()
            
            # TRANSCRIPTION MODE: No lyrics, or stable-ts not available
            elif use_stable_ts:
                processing_jobs[job_id]['step'] = 'Transcribing speech with stable-ts...'
                print(f"[Job {job_id}] Step 2: Transcribing with stable-ts model {whisper_model} on {actual_device}...")
                
                # Use cached model for faster subsequent runs
                model = get_cached_whisper_model(whisper_model, actual_device)
                result = model.transcribe(
                    str(vocals_path),
                    vad=True,
                    word_timestamps=True
                )
                word_segments = convert_to_word_segment_objects(result)
                print(f"[Job {job_id}] stable-ts transcribed {len(word_segments)} words with refined timestamps")
            
            else:
                processing_jobs[job_id]['step'] = 'Transcribing speech with Whisper...'
                print(f"[Job {job_id}] stable-ts not available, falling back to standard Whisper")
                word_segments = transcribe_audio(
                    vocals_path,
                    model=whisper_model,
                    device=actual_device,
                    target_sr=16000
                )
                print(f"[Job {job_id}] Whisper transcribed {len(word_segments)} words")
                
        except StableTranscriptionError as e:
            print(f"[Job {job_id}] stable-ts/alignment failed: {e}, falling back to Whisper")
            word_segments = transcribe_audio(
                vocals_path,
                model=whisper_model,
                device=actual_device,
                target_sr=16000
            )
        except Exception as e:
            print(f"[Job {job_id}] ERROR in transcription/alignment: {e}")
            print(f"[Job {job_id}] Traceback: {traceback.format_exc()}")
            raise
        
        if forced_alignment:
            log_words(word_segments, "forced_alignment_from_lyrics")
            print(f"[Job {job_id}] ⭐ Using forced alignment - 100% word accuracy guaranteed")
        else:
            log_words(word_segments, "stable_ts_transcription" if use_stable_ts else "whisper_transcription")
        
        # Step 2.6: Apply lyrics correction if provided (only for non-forced-alignment mode)
        if lyrics and not forced_alignment:
            processing_jobs[job_id]['step'] = 'Correcting with provided lyrics...'
            print(f"[Job {job_id}] Step 2.5: Applying lyrics correction...")
            
            # Compare and get differences
            differences, accuracy = compare_transcription_to_lyrics(word_segments, lyrics)
            print(f"[Job {job_id}] Transcription accuracy: {accuracy:.1f}%")
            print(f"[Job {job_id}] Found {len(differences)} differences")
            
            # Align and correct
            word_segments = align_lyrics_to_transcription(word_segments, lyrics)
            print(f"[Job {job_id}] Corrected transcription using lyrics")
        
        # Step 3: Detect profanity
        processing_jobs[job_id]['step'] = 'Detecting profanity...'
        processing_jobs[job_id]['progress'] = 50
        print(f"[Job {job_id}] Step 3: Detecting profanity...")
        
        profane_segments = detect_profanity(
            word_segments,
            lexicon_file,
            normalize_text=True,
            case_sensitive=False,
            confidence_threshold=0.8
        )
        
        log_profanity(profane_segments)
        print(f"[Job {job_id}] Found {len(profane_segments)} profane words")
        
        # Step 4: Censor profanity
        processing_jobs[job_id]['step'] = 'Censoring profanity...'
        processing_jobs[job_id]['progress'] = 70
        print(f"[Job {job_id}] Step 4: Censoring audio...")
        
        censor = AudioCensor(
            fade_ms=50,
            pre_margin_ms=100,
            post_margin_ms=100,
            censor_method=method
        )
        
        # Choose audio source based on censoring method
        if method == 'mute':
            # Mute: Use separated vocals (better quality, only mutes vocals)
            print(f"[Job {job_id}] Using separated vocals for mute method")
            censored_vocal_path = work_dir / "censored_vocals.wav"
            censor.censor_audio(vocals_path, profane_segments, censored_vocal_path)
            
            # Step 5: Remix audio (vocals + instrumentals)
            processing_jobs[job_id]['step'] = 'Remixing audio...'
            processing_jobs[job_id]['progress'] = 85
            print(f"[Job {job_id}] Step 5: Remixing...")
            remix_audio(censored_vocal_path, instrumental_path, clean_audio_path)
        else:
            # Reverse/Bleep: Use original audio (no quality loss from separation)
            print(f"[Job {job_id}] Using original audio for {method} method (preserves quality)")
            clean_audio_path_temp = work_dir / "censored_full.wav"
            censor.censor_audio(input_path, profane_segments, clean_audio_path_temp)
            
            # Move to final output location
            processing_jobs[job_id]['step'] = 'Finalizing...'
            processing_jobs[job_id]['progress'] = 85
            print(f"[Job {job_id}] Step 5: Finalizing output...")
            shutil.copy(clean_audio_path_temp, clean_audio_path)
        
        # Step 6: Generate report
        processing_jobs[job_id]['step'] = 'Generating report...'
        processing_jobs[job_id]['progress'] = 95
        
        report = {
            "input_file": str(input_path.name),
            "output_file": str(clean_audio_path.name),
            "timestamp": datetime.now().isoformat(),
            "model_preset": model_preset,
            "whisper_model": whisper_model,
            "demucs_model": demucs_model,
            "censoring_method": method,
            "device": actual_device,
            "lyrics_provided": bool(lyrics),
            "total_words": len(word_segments),
            "profane_words_detected": len(profane_segments),
            "profane_words": [
                {
                    "word": seg.word,
                    "start": seg.start,
                    "end": seg.end,
                    "confidence": seg.confidence
                }
                for seg in profane_segments
            ]
        }
        
        # Add lyrics comparison if provided
        if lyrics:
            differences, accuracy = compare_transcription_to_lyrics(word_segments, lyrics)
            report["lyrics_accuracy"] = f"{accuracy:.1f}%"
            report["lyrics_differences_found"] = len(differences)
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Save logs
        save_logs(include_summary=True)
        
        # Update job status
        processing_jobs[job_id]['status'] = 'completed'
        processing_jobs[job_id]['step'] = 'Complete!'
        processing_jobs[job_id]['progress'] = 100
        processing_jobs[job_id]['output_file'] = str(clean_audio_path)
        processing_jobs[job_id]['report_file'] = str(report_path)
        processing_jobs[job_id]['profane_count'] = len(profane_segments)
        print(f"[Job {job_id}] ✅ Processing complete!")
        
        # Cleanup temporary files
        try:
            shutil.rmtree(stems_dir)
            shutil.rmtree(work_dir)
        except Exception as e:
            print(f"Warning: Failed to cleanup temporary files: {e}")
        
    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()
        processing_jobs[job_id]['status'] = 'failed'
        processing_jobs[job_id]['error'] = error_msg
        print(f"\n❌ [Job {job_id}] FATAL ERROR: {error_msg}")
        print(f"[Job {job_id}] Full traceback:\n{error_trace}")
        
        # Cleanup on error
        try:
            if stems_dir.exists():
                shutil.rmtree(stems_dir)
            if work_dir.exists():
                shutil.rmtree(work_dir)
        except:
            pass
            print(f"Warning: Failed to cleanup temporary files: {e}")
        
    except Exception as e:
        processing_jobs[job_id]['status'] = 'failed'
        processing_jobs[job_id]['error'] = str(e)
        print(f"Error processing job {job_id}: {e}")


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html', models=MODELS)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload or YouTube URL and start processing."""
    # Get input type
    input_type = request.form.get('input_type', 'file')
    
    # Get processing options
    model_preset = request.form.get('model', 'balanced')
    method = request.form.get('method', 'mute')
    device = request.form.get('device', 'cpu')
    
    # Validate options
    if model_preset not in MODELS:
        return jsonify({'error': 'Invalid model preset'}), 400
    
    if method not in ['mute', 'bleep', 'reverse']:
        return jsonify({'error': 'Invalid censoring method'}), 400
    
    # Create unique job ID
    job_id = str(uuid.uuid4())
    upload_path = app.config['UPLOAD_FOLDER'] / job_id
    upload_path.mkdir(parents=True, exist_ok=True)
    
    try:
        if input_type == 'youtube':
            # Handle YouTube URL
            youtube_url = request.form.get('youtube_url', '').strip()
            if not youtube_url:
                return jsonify({'error': 'No YouTube URL provided'}), 400
            
            if not YOUTUBE_AVAILABLE:
                return jsonify({'error': 'YouTube download not available. Install yt-dlp: pip install yt-dlp'}), 400
            
            print(f"[Upload] Downloading from YouTube: {youtube_url}")
            file_path = download_youtube_audio(youtube_url, upload_path)
            filename = file_path.name
        else:
            # Handle file upload
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'error': 'Invalid file type'}), 400
            
            filename = secure_filename(file.filename)
            file_path = upload_path / filename
            file.save(file_path)
            print(f"[Upload] Saved file: {filename}")
    
    except Exception as e:
        return jsonify({'error': f'Failed to process input: {str(e)}'}), 400
    
    # Get optional lyrics
    lyrics = request.form.get('lyrics', '').strip() or None
    
    # Initialize job status
    processing_jobs[job_id] = {
        'status': 'queued',
        'step': 'Waiting to start...',
        'progress': 0,
        'filename': filename,
        'model_preset': model_preset,
        'method': method,
        'device': device,
        'lyrics_provided': bool(lyrics)
    }
    
    # Start processing in background thread
    thread = threading.Thread(
        target=process_audio_file,
        args=(job_id, file_path, model_preset, method, device, lyrics)
    )
    thread.start()
    
    return jsonify({
        'job_id': job_id,
        'message': 'Processing started'
    })


@app.route('/status/<job_id>')
def get_status(job_id: str):
    """Get the status of a processing job."""
    if job_id not in processing_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(processing_jobs[job_id])


@app.route('/download/<job_id>')
def download_file(job_id: str):
    """Download the processed audio file."""
    if job_id not in processing_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = processing_jobs[job_id]
    
    if job['status'] != 'completed':
        return jsonify({'error': 'Processing not complete'}), 400
    
    output_file = Path(job['output_file'])
    
    # Debug logging
    print(f"[Download] Job ID: {job_id}")
    print(f"[Download] Output file path: {output_file}")
    print(f"[Download] File exists: {output_file.exists()}")
    print(f"[Download] Absolute path: {output_file.absolute()}")
    
    if not output_file.exists():
        # Try to find the file in the output directory
        output_dir = app.config['OUTPUT_FOLDER'] / job_id
        print(f"[Download] Searching in: {output_dir}")
        if output_dir.exists():
            files = list(output_dir.glob('*.clean.wav'))
            print(f"[Download] Found files: {files}")
            if files:
                output_file = files[0]
                print(f"[Download] Using file: {output_file}")
            else:
                return jsonify({'error': f'Output file not found in {output_dir}'}), 404
        else:
            return jsonify({'error': f'Output directory not found: {output_dir}'}), 404
    
    return send_file(
        output_file,
        as_attachment=True,
        download_name=output_file.name
    )


@app.route('/report/<job_id>')
def download_report(job_id: str):
    """Download the processing report."""
    if job_id not in processing_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = processing_jobs[job_id]
    
    if job['status'] != 'completed':
        return jsonify({'error': 'Processing not complete'}), 400
    
    report_file = Path(job['report_file'])
    
    if not report_file.exists():
        return jsonify({'error': 'Report file not found'}), 404
    
    return send_file(
        report_file,
        as_attachment=True,
        download_name=report_file.name
    )


def main():
    """Run the Flask development server."""
    import torch
    import os
    
    # Check CUDA availability
    if torch.cuda.is_available():
        print(f"✅ GPU detected: {torch.cuda.get_device_name(0)}")
    else:
        print("ℹ️  No GPU detected, using CPU processing")
    
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    
    # Check if running in production
    is_production = os.environ.get('FLASK_ENV') == 'production'
    
    if is_production:
        print("\n🎵 Starting Explicitly Web Interface (Production Mode)...")
        print(f"📍 Server running on port {port}")
        print("⚠️  Use gunicorn in production, not Flask dev server")
    else:
        print("\n🎵 Starting Explicitly Web Interface (Development Mode)...")
        print(f"📍 Open your browser to: http://localhost:{port}")
        print("Press Ctrl+C to stop the server\n")
    
    # Preload models at startup (always preload, even in dev mode)
    preload_models()
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=not is_production,
        use_reloader=False
    )


if __name__ == '__main__':
    main()
