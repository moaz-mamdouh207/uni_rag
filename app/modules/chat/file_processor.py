"""
FileProcessor — resolves temp file UUIDs to paths, detects file type,
and runs structured full extraction via the VLM.

Design rules:
  - Always does a FULL extraction regardless of user intent.
    The Planner decides what to keep; this module never filters.
  - Uses the same call_vlm_with_prompt_and_image() pattern as PdfParser
    so there is one single VLM integration point in the codebase.
  - PDF  → each page rendered to PIL Image via fitz → VLM per page
            → pages joined into one markdown string.
  - Image → single PIL Image → VLM once.
  - Errors on individual files are caught and logged; the caller
    (ChatService) receives an empty list for that file rather than a crash.
"""
from __future__ import annotations

import io
import logging
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import fitz                          # PyMuPDF — already used by PdfParser
from PIL import Image as PILImage

from modules.chat.schemas import FileExtractionResult, FileType

if TYPE_CHECKING:
    from modules.chat.config import ChatSettings
    from shared.llm.client import LLMClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Extraction prompt — fixed and never modified by user intent or planner.
#
# The VLM is instructed to do a complete structural extraction so the Planner
# always works against real file content, never guesses.
# ---------------------------------------------------------------------------
EXTRACTION_PROMPT = """\
Extract ALL questions, problems, and numbered items from this document page.

For EACH item output exactly this structure — do not deviate:

## Item {n}
**Type**: [question | problem | instruction | statement | other]
**Text**: <exact verbatim text, preserving all numbering and math notation>
**Sub-items**: <lettered or numbered sub-parts if any, otherwise write "none">

Rules:
- Preserve ALL original numbering exactly as it appears (e.g. "Q3", "3.", "(iii)").
- Do NOT paraphrase, summarise, merge, or reorder items.
- Do NOT add any preamble, commentary, or closing remarks.
- If this page contains no questions or problems at all, output exactly: NO_ITEMS_FOUND
"""

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}


class FileProcessor:
    """
    Resolves file UUIDs → paths, detects type, runs VLM extraction.

    Args:
        llm_client: Shared LLMClient instance. Must expose
                    call_vlm_with_prompt_and_image(prompt, PIL.Image) -> str.
        settings:   ChatSettings (reserved for future per-file config).
    """

    def __init__(self, llm_client: LLMClient, settings: ChatSettings) -> None:
        self._llm      = llm_client
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process(self, file_ids: list[UUID]) -> list[FileExtractionResult]:
        """
        Process a list of temp file UUIDs.

        Returns one FileExtractionResult per successfully processed file.
        Files that fail (bad path, unsupported type, VLM error) are skipped
        with a warning — a single bad attachment must not kill the request.
        """
        results: list[FileExtractionResult] = []

        for file_id in file_ids:
            try:
                result = await self._process_single(file_id)
                results.append(result)
            except Exception:
                logger.warning(
                    "FileProcessor: skipping file %s due to error",
                    file_id,
                    exc_info=True,
                )

        return results

    # ------------------------------------------------------------------
    # Private — orchestration
    # ------------------------------------------------------------------

    async def _process_single(self, file_id: UUID) -> FileExtractionResult:
        from modules.knowledge.utils.asset import get_temp_file_path  # mirrors service.py pattern

        file_path  = await get_temp_file_path(file_id)
        file_type  = self._detect_type(file_path) # type: ignore
        markdown   = self._extract(file_path, file_type)  # type: ignore # sync — VLM client is sync

        logger.debug(
            "FileProcessor: extracted %s (%s) — %d chars",
            file_id, file_type, len(markdown),
        )

        return FileExtractionResult(
            file_id=file_id,
            file_type=file_type,
            markdown_content=markdown,
        )

    # ------------------------------------------------------------------
    # Private — type detection
    # ------------------------------------------------------------------

    def _detect_type(self, file_path: str) -> FileType:
        """
        Determine FileType from extension, falling back to MIME sniffing.
        Raises ValueError for unsupported types so _process_single can log
        and skip cleanly.
        """
        ext = Path(file_path).suffix.lower()

        if ext == ".pdf":
            return FileType.PDF

        if ext in _IMAGE_EXTENSIONS:
            return FileType.IMAGE

        mime, _ = mimetypes.guess_type(file_path)
        if mime == "application/pdf":
            return FileType.PDF
        if mime and mime.startswith("image/"):
            return FileType.IMAGE

        raise ValueError(
            f"Unsupported file type — extension: '{ext}', MIME: '{mime}'. "
            "Only PDF and images are supported."
        )

    # ------------------------------------------------------------------
    # Private — extraction
    # ------------------------------------------------------------------

    def _extract(self, file_path: str, file_type: FileType) -> str:
        """Dispatch to the correct extractor based on file type."""
        if file_type == FileType.PDF:
            return self._extract_pdf(file_path)
        return self._extract_image(file_path)

    def _extract_pdf(self, file_path: str) -> str:
        """
        Render each PDF page to a PIL Image at 150 DPI and send to VLM.
        This mirrors PdfParser.load() exactly — same fitz → pixmap → PIL
        pipeline — but uses EXTRACTION_PROMPT instead of build_prompt().

        Pages where the VLM returns NO_ITEMS_FOUND are silently skipped.
        All other pages are joined with a page-separator comment so the
        Planner can see page boundaries if needed.
        """
        doc    = fitz.open(file_path)
        pages: list[str] = []

        for page_no, page in enumerate(doc, start=1):  # type: ignore[arg-type]
            pix = page.get_pixmap(dpi=150)
            img = PILImage.open(io.BytesIO(pix.tobytes("png")))

            raw = self._llm.call_vlm_with_prompt_and_image(EXTRACTION_PROMPT, img)

            if "NO_ITEMS_FOUND" in raw:
                logger.debug("FileProcessor: page %d — no items found, skipping", page_no)
                continue

            pages.append(f"<!-- page {page_no} -->\n{raw.strip()}")

        if not pages:
            return "NO_ITEMS_FOUND"

        return "\n\n".join(pages)

    def _extract_image(self, file_path: str) -> str:
        """
        Open the image as a PIL Image and send directly to the VLM.
        Single call — no pagination needed.
        """
        img = PILImage.open(file_path)
        raw = self._llm.call_vlm_with_prompt_and_image(EXTRACTION_PROMPT, img)
        return raw.strip() if raw.strip() else "NO_ITEMS_FOUND"
