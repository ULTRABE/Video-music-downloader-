# wired but optional – reply /mp3 to bot video
import subprocess
import os
from pathlib import Path

def convert_to_mp3(input_file: Path, output_file: Path) -> bool:
    """Convert video to MP3 using ffmpeg"""
    try:
        cmd = [
            "ffmpeg",
            "-i", str(input_file),
            "-vn",  # No video
            "-acodec", "libmp3lame",
            "-ab", "192k",
            "-ar", "44100",
            "-y",  # Overwrite
            str(output_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        return result.returncode == 0
    except Exception:
        return False

def get_audio_size_mb(file_path: Path) -> float:
    """Get file size in MB"""
    if not file_path.exists():
        return 0
    return file_path.stat().st_size / (1024 * 1024)
