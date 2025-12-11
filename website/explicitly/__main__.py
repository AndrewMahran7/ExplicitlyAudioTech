"""
Main entry point for the Explicitly package when run as a module.

This allows running the CLI using:
    python -m explicitly
"""

from .cli import main

if __name__ == "__main__":
    main()