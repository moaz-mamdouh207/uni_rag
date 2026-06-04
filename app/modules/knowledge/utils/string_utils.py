import hashlib
import re
from pathlib import Path

def get_clean_file_name(filename: str) -> str:
    """
    Cleans a filename, adds a deterministic hash, and preserves the extension.
    Example: 'My Resume 2024.pdf' -> 'my-resume-2024-a1b2c3d4.pdf'
    """
    path = Path(filename)
    
    # 1. Extract the stem (name without extension) and the extension
    stem = path.stem
    extension = path.suffix.lower()

    normalized = re.sub(r'[^a-zA-Z0-9]+', '_', stem.strip().lower())
    normalized = normalized.strip('-') # Clean up trailing/leading dashes

    h = hashlib.sha256(filename.encode()).hexdigest()[8:32]

    return f"{h}_{normalized}{extension}"

def get_safe_name(name: str) -> str:
        normalized = re.sub(r'[^a-zA-Z0-9]+', '_', name.strip().lower())

        h = hashlib.sha256(name.encode()).hexdigest()[8:16]

        return f"{h}_{normalized}"