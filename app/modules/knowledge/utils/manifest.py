import json
from pathlib import Path


MANIFEST_FILE_NAME = ".manifest.json"

def get_manifest(course_dir_path: Path) -> dict[str, list[dict[str, str]]]:
    manifest_path = course_dir_path / MANIFEST_FILE_NAME
    if not manifest_path.exists():
        return {"files": []}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"files": []}
 
def register_manifest(
    course_dir_path: Path,
    file_hash: str,
    original_file_name: str,
    stored_file_name: str,
) -> None:
    manifest_path = course_dir_path / MANIFEST_FILE_NAME

    manifest = get_manifest(course_dir_path)

    manifest["files"].append({
        "original_name": original_file_name,
        "stored_name": stored_file_name,
        "file_hash": file_hash,
    })

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)

def check_duplicate(course_dir_path: Path, file_hash: str) -> str | None:
    """Returns the original file name if duplicate, None otherwise."""
    manifest = get_manifest(course_dir_path)
    for file in manifest["files"]:
        if file["file_hash"] == file_hash:
            return file["original_name"]
    return None
