from __future__ import annotations

import asyncio
import io
import logging
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import fitz
from PIL import Image as PILImage

from modules.chat.schemas import FileExtractionResult, FileType

if TYPE_CHECKING:
    from modules.chat.config import ChatSettings
    from shared.llm.client import LLMClient

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """
You are an expert engineering document digitization assistant. \
Your task is to extract every technical detail from the provided image with absolute precision. \
Do not summarize, do not omit data, and do not hallucinate details that are not explicitly visible.

USER QUERY CONTEXT:
The user is asking the following question about this document: 
<user_query>
"{USER_QUERY}"
</user_query>
Pay extreme attention to any parts of the image, circuits, \
figures, or values relevant to this query as it will be passed for another llm to answer, \
but ensure you extract all other technical contents of the page as well.

EXTRACTION INSTRUCTIONS:
Extract the contents of the image according to these strict rules:

1. CHRONOLOGICAL/SEQUENTIAL GROUPING (CRITICAL):
   - Do NOT separate all text and all figures into isolated macro-sections.
   - Instead, follow the literal reading order/structure of the document. \
    Organize the data sequentially (e.g., Problem by Problem or Section by Section).
   - If a figure belongs to a specific question (or set of questions), embed that figure's visual description, \
    topology, and component values directly inline with or immediately underneath that specific question's text.

2. TEXT & TABLES:
   - Transcribe all text verbatim within its corresponding block.
   - Reconstruct all data tables using Markdown format. Preserve exact headers, units, and numerical values.

3. FIGURES, SCHEMATICS & GEOMETRY (INLINE WITH ASSOCIATED TEXT):
   - For every engineering drawing, physical figure, or circuit, state its reference label (e.g., FIGURE P4.17).
   - Identify every component (e.g., Mass M, Spring K, Damper f_v, Resistors, Capacitors).
   - Extract their exact reference designators and specific values/units.
   - Describe the exact topology/connections and visual structure \
    (e.g., "A mass M connected to a fixed wall via a spring K and damper f_v in parallel").
   - Extract graph axes labels, units, and critical coordinate points if present.

4. CRITICAL RESTRICTIONS:
   - If a number, unit, or letter is blurry or ambiguous, do not guess. Mark it as "[UNCLEAR: potential_guess?]".
   - Do NOT assume standard values. Write exactly what is visible.
   - Avoid conversational filler. Output only the extracted engineering data.

OUTPUT FORMAT:
Structure your response cleanly using a sequential markdown hierarchy where text and visuals are coupled together:

## [Problem Number / Section Heading]
### Verbatim Text
> (Insert verbatim transcribed text here)

### Associated Figure & Component Details
* **Figure Label & Structure:** (e.g., FIGURE P4.17 - Visual breakdown and topology)
* **Inputs/Outputs:** (e.g., Applied forces, torques, currents, displacements)
* **Component Values & Labels:** (Explicit list of variables, values, and units for this specific problem)

---
(Repeat the above block for the next sequential problem/section in the document)
"""

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}


class FileProcessor:

    def __init__(self, llm_client: LLMClient, settings: ChatSettings) -> None:
        self._llm      = llm_client
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process(self, file_ids: list[UUID], user_query: str = "") -> list[FileExtractionResult]:
        """
        Process a list of temp file UUIDs.

        Returns one FileExtractionResult per successfully processed file.
        Files that fail (bad path, unsupported type, VLM error) are skipped
        with a warning — a single bad attachment must not kill the request.
        """
        results: list[FileExtractionResult] = []

        for file_id in file_ids:
            try:
                result = await self._process_single(file_id, user_query)
                results.append(result)
            except Exception:
                logger.warning(
                    "FileProcessor: skipping file %s due to error",
                    file_id,
                    exc_info=True,
                )

        return results

    async def cleanup(self, file_ids: list[UUID]) -> None:
        """
        Delete temp files from disk and deregister them from the registry.
        Should be called after the agent turn finishes — success or failure.
        Errors are logged but never raised so they don't mask the real response.
        """
        from modules.knowledge.utils.asset import unsave_temp_file_from_disk

        for file_id in file_ids:
            try:
                await unsave_temp_file_from_disk(file_id)
                logger.debug("FileProcessor: cleaned up temp file %s", file_id)
            except Exception:
                logger.warning(
                    "FileProcessor: failed to clean up file %s",
                    file_id,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Private — orchestration
    # ------------------------------------------------------------------

    async def _process_single(self, file_id: UUID, user_query: str = "") -> FileExtractionResult:
        from modules.knowledge.utils.asset import get_temp_file_path

        file_path = await get_temp_file_path(file_id)
        if file_path is None:
            raise FileNotFoundError(f"Temp file not found for id={file_id}")

        file_type = self._detect_type(str(file_path))

        # Offload all blocking work (fitz rendering + VLM calls) to a thread moaz: better change vlm to async
        markdown = await asyncio.to_thread(self._extract, str(file_path), file_type, user_query)

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
    # Private — extraction (all blocking — must be called via to_thread)
    # ------------------------------------------------------------------

    def _extract(self, file_path: str, file_type: FileType, user_query: str = "") -> str:
        if file_type == FileType.PDF:
            return self._extract_pdf(file_path, user_query)
        return self._extract_image(file_path, user_query)

    def _extract_pdf(self, file_path: str, user_query: str = "") -> str:
        """
        Render each PDF page to a PIL Image at 150 DPI and send to VLM.
        Pages where the VLM returns NO_ITEMS_FOUND are silently skipped.
        All other pages are joined with a page-separator comment.
        """
        prompt = EXTRACTION_PROMPT.format(USER_QUERY=user_query)
        doc = fitz.open(file_path)
        pages: list[str] = []

        for page_no, page in enumerate(doc, start=1):  # type: ignore[arg-type]
            pix = page.get_pixmap(dpi=150)
            img = PILImage.open(io.BytesIO(pix.tobytes("png")))

            raw = self._llm.call_vlm_with_prompt_and_image(prompt, img)

            if "NO_ITEMS_FOUND" in raw:
                logger.debug("FileProcessor: page %d — no items found, skipping", page_no)
                continue

            pages.append(f"<!-- page {page_no} -->\n{raw.strip()}")

        if not pages:
            return "NO_ITEMS_FOUND"

        return "\n\n".join(pages)

    def _extract_image(self, file_path: str, user_query: str = "") -> str:
        prompt = EXTRACTION_PROMPT.format(USER_QUERY=user_query)
        img = PILImage.open(file_path)
        raw = self._llm.call_vlm_with_prompt_and_image(prompt, img)
        return raw.strip() if raw.strip() else "NO_ITEMS_FOUND"