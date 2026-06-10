from __future__ import annotations
from pathlib import Path
from typing import BinaryIO
import uuid
import asyncio
import aiofiles
import redis.asyncio as aioredis

from core.config import settings

ROOT_DIR = Path.cwd()
ATTACHMENTS_DIR = ROOT_DIR / "assets" / "attachments"
ATTACHMENTS_DIR.mkdir(exist_ok=True)

REGISTRY_KEY = "attachments_registry"


def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(
        settings.broker_url,
        encoding="utf-8",
        decode_responses=True,
    )


async def save_attachment(
    name: str,
    file: BinaryIO,
) -> uuid.UUID:
    buffer_size = settings.document.buffer_size_in_mbs * 1024 * 1024
    file_id = uuid.uuid4().hex
    _, _, ext = name.rpartition(".")
    stored_file_name = f"temp-{file_id}.{ext}"
    file_path = ATTACHMENTS_DIR / stored_file_name
    file_path.parent.mkdir(parents=True, exist_ok=True)

    await _write_file_to_disk(file, file_path, buffer_size)
    await register_attachment_path(uuid.UUID(file_id), file_path)

    return uuid.UUID(file_id)


async def unsave_attachment(file_id: uuid.UUID) -> None:
    """Removes the file from Redis registry and deletes the physical file."""
    file_path = await deregister_attachment_path(file_id)

    if file_path and file_path.exists():
        file_path.unlink()


async def get_attachment_path(file_id: uuid.UUID) -> Path | None:
    """Returns the Path for a given file_id, or None if not found."""
    async with _get_redis() as redis:
        stored_path = await redis.hget(REGISTRY_KEY, str(file_id)) # type: ignore

    return Path(stored_path) if stored_path else None


async def register_attachment_path(file_id: uuid.UUID, file_path: Path) -> None:
    async with _get_redis() as redis:
        await redis.hset(REGISTRY_KEY, str(file_id), str(file_path))  # type: ignore


async def deregister_attachment_path(file_id: uuid.UUID) -> Path | None:
    """
    Atomically removes a file_id from the registry and returns its path.
    Uses a pipeline so the GET + DEL are sent together without a round-trip race.
    """
    async with _get_redis() as redis:
        async with redis.pipeline() as pipe:
            pipe.hget(REGISTRY_KEY, str(file_id))
            pipe.hdel(REGISTRY_KEY, str(file_id))
            stored_path, _ = await pipe.execute()

    return Path(stored_path) if stored_path else None


async def _write_file_to_disk(file: BinaryIO, file_path: Path, buffer_size: int) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, file.seek, 0)

    async with aiofiles.open(file_path, "wb") as out_file:
        while True:
            chunk = await loop.run_in_executor(None, file.read, buffer_size)
            if not chunk:
                break
            await out_file.write(chunk)