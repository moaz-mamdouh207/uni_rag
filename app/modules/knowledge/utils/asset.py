from __future__ import annotations
from pathlib import Path
import hashlib
from typing import BinaryIO, TYPE_CHECKING
import aiofiles
import asyncio
import uuid
import json

from core.config import settings
from modules.knowledge.utils.string_utils import get_safe_name
from modules.knowledge.utils.manifest import check_duplicate
from modules.knowledge.exceptions import FileDuplicateError

if TYPE_CHECKING:
    from db.relational.models.course import Course

ROOT_DIR = Path.cwd()
ASSETS_DIR = ROOT_DIR / "assets"
ASSETS_DIR.mkdir(exist_ok=True)
TEMP_DIR = ROOT_DIR / "assets" / "temp"
TEMP_DIR.mkdir(exist_ok=True)
REGISTRY_JSON_PATH = TEMP_DIR / "temp_file_registry.json"

def get_file_path(course: Course, stored_file_name: str) -> Path:
    course_dir = get_or_create_course_dir(course=course)
    return course_dir / stored_file_name


def get_or_create_course_dir(course: Course) -> Path:
    course_dir = ASSETS_DIR / Path(str(course.user_id)) / get_safe_name(course.name)
    course_dir.mkdir(parents=True, exist_ok=True)
    return course_dir
       

def compute_file_hash(file: BinaryIO, buffer_size: int = 8192) -> str:
    hasher = hashlib.sha256()

    file.seek(0)
    while chunk := file.read(buffer_size):
        hasher.update(chunk)
    file.seek(0)

    return hasher.hexdigest()


def get_stored_file_name(original_file_name: str) -> str:
        name, _, ext = original_file_name.rpartition(".")
        clean_file_name = get_safe_name(name)
        return f"{clean_file_name}.{ext}"


def unsave_file_from_disk(course_dir: Path, stored_file_name: str) -> None:
    file_path = course_dir / stored_file_name
    file_path.unlink(missing_ok=True)


async def save_file_to_disk(
    course: Course,
    original_file_name: str,
    file: BinaryIO, 
) -> tuple[Path, Path, str, str]:
    """
    Validate, deduplicate, and persist an uploaded file for a given course.
 
    Returns:
        file_path:      Full path to the written file.
        course_dir:    Directory the file was written into.
        file_hash:      SHA-256 (or equivalent) hash of the file contents.
        stored_file_name: Sanitised version of the original file name.
 
    Raises:
        FileDuplicateError: If a file with the same hash already exists in the course directory.
    """
    buffer_size = settings.document.buffer_size_in_mbs * 1024 * 1024

    course_dir = get_or_create_course_dir(course=course)
 
    file_hash = compute_file_hash(file, buffer_size)
 
    existing_name = check_duplicate(course_dir, file_hash)
    if existing_name:
        raise FileDuplicateError(file_name=existing_name)
 
    stored_file_name = get_stored_file_name(original_file_name=original_file_name)
    file_path = get_file_path(
        course=course,
        stored_file_name=stored_file_name
    )
 
    await _write_file_to_disk(file, file_path, buffer_size)
 
    return course_dir, file_path, stored_file_name, file_hash 


async def _write_file_to_disk(file: BinaryIO, file_path: Path, buffer_size: int) -> None:
    """
    Write a binary file to disk asynchronously.
 
    Offloads the blocking seek/read calls to a thread via run_in_executor
    so the event loop is not blocked during I/O.
    """
    loop = asyncio.get_event_loop()
 
    await loop.run_in_executor(None, file.seek, 0)
 
    async with aiofiles.open(file_path, "wb") as out_file:
        while True:
            chunk = await loop.run_in_executor(None, file.read, buffer_size)
            if not chunk:
                break
            await out_file.write(chunk)



async def save_temp_file_to_disk(
    name: str,
    file: BinaryIO, 
) -> uuid.UUID:
    buffer_size = settings.document.buffer_size_in_mbs * 1024 * 1024
    file_id = uuid.uuid4().hex
    _, _, ext = name.rpartition(".")
    stored_file_name = f"temp-{file_id}.{ext}"
    file_path = TEMP_DIR / stored_file_name
    file_path.parent.mkdir(parents=True, exist_ok=True)
 
    await _write_file_to_disk(file, file_path, buffer_size)

    await register_file_path(uuid.UUID(file_id), file_path)

    return uuid.UUID(file_id)

async def unsave_temp_file_from_disk(file_id: uuid.UUID) -> None:
    """Removes the file from the JSON registry and deletes the actual file from disk."""
    # 1. Remove from JSON registry
    file_path = await deregister_file_path(file_id)
    
    # 2. Delete the physical file if it exists
    if file_path and file_path.exists():
        file_path.unlink()

async def get_temp_file_path(file_id: uuid.UUID) -> Path | None:
    """
    Looks up a file_id in the disk registry and returns its Path.
    Returns None if the file_id is not found.
    """
    registry = _load_registry()
    file_id_str = str(file_id)
    
    if file_id_str in registry:
        stored_path_str = registry[file_id_str]
        return Path(stored_path_str)
        
    return None


def _load_registry() -> dict[str, str]:
    """Helper to read the JSON file from disk."""
    if not REGISTRY_JSON_PATH.exists():
        return {}
    try:
        with open(REGISTRY_JSON_PATH, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Handle case where file exists but is corrupted/empty
        return {}

def _save_registry(registry: dict[str, str]) -> None:
    """Helper to write the dictionary back to disk."""
    REGISTRY_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_JSON_PATH, "w") as f:
        json.dump(registry, f, indent=4)

# --- Core Public Functions ---

async def register_file_path(file_id: uuid.UUID, file_path: Path) -> None:
    """Appends or updates a file ID mapping on disk."""
    registry = _load_registry()
    
    # JSON keys must be strings, so convert the UUID and Path
    registry[str(file_id)] = str(file_path)
    
    _save_registry(registry)

async def deregister_file_path(file_id: uuid.UUID) -> Path | None:
    """Deletes a file ID from the registry disk and returns the path if it existed."""
    registry = _load_registry()
    file_id_str = str(file_id)
    
    if file_id_str in registry:
        stored_path_str = registry.pop(file_id_str)
        _save_registry(registry)
        return Path(stored_path_str)
    
    return None