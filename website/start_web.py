"""
Quick start script for Explicitly Web Interface

This script checks dependencies and launches the web server.
"""

import sys
import subprocess

def check_dependency(module_name, package_name=None):
    """Check if a Python module is installed."""
    if package_name is None:
        package_name = module_name
    
    try:
        __import__(module_name)
        return True
    except ImportError:
        print(f"❌ {package_name} not installed")
        return False

def main():
    print("🎵 Explicitly Web Interface - Quick Start")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher required")
        print(f"   Current version: {sys.version}")
        return 1
    
    print(f"✅ Python {sys.version.split()[0]}")
    
    # Check dependencies
    print("\n📦 Checking dependencies...")
    
    dependencies = [
        ('torch', 'PyTorch'),
        ('flask', 'Flask'),
        ('werkzeug', 'Werkzeug'),
        ('demucs', 'Demucs'),
        ('faster_whisper', 'faster-whisper'),
        ('librosa', 'librosa'),
        ('soundfile', 'soundfile'),
        ('pydub', 'pydub'),
        ('typer', 'typer'),
        ('yaml', 'PyYAML'),
    ]
    
    missing = []
    for module, package in dependencies:
        if check_dependency(module):
            print(f"✅ {package}")
        else:
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing dependencies: {', '.join(missing)}")
        print("\n📥 Install missing packages with:")
        print("   pip install -r requirements.txt")
        return 1
    
    # Check GPU availability
    print("\n🖥️  Checking GPU availability...")
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✅ GPU detected: {torch.cuda.get_device_name(0)}")
            print("   Processing will be much faster!")
        else:
            print("ℹ️  No GPU detected")
            print("   Will use CPU (slower but works)")
    except Exception as e:
        print(f"⚠️  Could not check GPU: {e}")
    
    # Check for lexicon
    print("\n📚 Checking profanity lexicon...")
    from pathlib import Path
    lexicon_paths = [
        Path("lexicons/profanity_en.txt"),
        Path("../lexicons/profanity_en.txt"),
    ]
    
    lexicon_found = False
    for path in lexicon_paths:
        if path.exists():
            print(f"✅ Lexicon found: {path}")
            lexicon_found = True
            break
    
    if not lexicon_found:
        print("⚠️  Profanity lexicon not found")
        print("   Expected at: lexicons/profanity_en.txt")
        print("   Processing may fail without it!")
    
    # All checks passed
    print("\n" + "=" * 50)
    print("✅ All checks passed! Starting web server...")
    print("\n🌐 Web interface will be available at:")
    print("   http://localhost:5000")
    print("\n💡 Press Ctrl+C to stop the server")
    print("=" * 50 + "\n")
    
    # Start the web server
    try:
        from explicitly.web import main as web_main
        web_main()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
        return 0
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
