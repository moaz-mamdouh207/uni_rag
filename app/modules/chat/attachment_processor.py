from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING

import fitz
from PIL import Image as PILImage

from modules.chat.enums import AttachmentType

if TYPE_CHECKING:
    from modules.chat.config import ChatSettings
    from shared.llm.client import LLMClient
    from modules.chat.schemas import Attachment
    

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



class AttachmentProcessor:

    def __init__(self, llm_client: LLMClient, settings: ChatSettings) -> None:
        self._llm      = llm_client
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process(self, attachments: list[Attachment], query: str = "") -> list[str]:
        """
        Process a list of attachments.

        Returns one extracted content string per successfully processed file.
        Files that fail (bad path, unsupported type, VLM error) are skipped
        with a warning — a single bad attachment must not kill the request.
        """
        results: list[str] = []

        for attachment in attachments:
            try:
                result = await self._process_single(attachment, query)
                results.append(result)
            except Exception:
                logger.warning(
                    "AttachmentProcessor: skipping attachment %s due to error",
                    attachment.id,
                    exc_info=True,
                )

        return results

    async def cleanup(self, attachments: list[Attachment]) -> None:
        """
        Delete attachments from disk and deregister them from the registry.
        Should be called after the agent turn finishes — success or failure.
        Errors are logged but never raised so they don't mask the real response.
        """
        from modules.chat.utils.asset import unsave_attachment

        for attachment in attachments:
            try:
                await unsave_attachment(attachment.id)
                logger.debug("AttachmentProcessor: cleaned up attachment %s", attachment.id)
            except Exception:
                logger.warning(
                    "AttachmentProcessor: failed to clean up attachment %s",
                    attachment.id,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Private — orchestration
    # ------------------------------------------------------------------

    async def _process_single(self, attachment: Attachment, query: str = "") -> str:
        from modules.chat.utils.asset import get_attachment_path

        attachment_path = await get_attachment_path(attachment.id)
        if attachment_path is None:
            raise FileNotFoundError(f"Attachment not found for id={attachment.id}")

        # Offload all blocking work (fitz rendering + VLM calls) to a thread moaz: better change vlm to async
        content = await asyncio.to_thread(self._extract, str(attachment_path), attachment.type, query)

        logger.debug(
            "AttachmentProcessor: extracted %s (%s) — %d chars",
            attachment.id, attachment.type, len(content),
        )

        return content

    # ------------------------------------------------------------------
    # Private — extraction (all blocking — must be called via to_thread)
    # ------------------------------------------------------------------

    def _extract(self, path: str, type: AttachmentType, query: str = "") -> str:
        if type == AttachmentType.PDF:
            return self._extract_pdf(path, query)
        return self._extract_image(path, query)

    def _extract_pdf(self, path: str, query: str = "") -> str:
        """
        Render each PDF page to a PIL Image at 150 DPI and send to VLM.
        Pages where the VLM returns NO_ITEMS_FOUND are silently skipped.
        All other pages are joined with a page-separator comment.
        """
        prompt = EXTRACTION_PROMPT.format(USER_QUERY=query)
        doc = fitz.open(path)
        pages: list[str] = []

        for page_no, page in enumerate(doc, start=1):  # type: ignore[arg-type]
            pix = page.get_pixmap(dpi=150)
            img = PILImage.open(io.BytesIO(pix.tobytes("png")))

            raw = self._llm.call_vlm_with_prompt_and_image(prompt, img)

            if "NO_ITEMS_FOUND" in raw:
                logger.debug("AttachmentProcessor: page %d — no items found, skipping", page_no)
                continue

            pages.append(f"<!-- page {page_no} -->\n{raw.strip()}")

        if not pages:
            return "NO_ITEMS_FOUND"

        return "\n\n".join(pages)

    def _extract_image(self, path: str, query: str = "") -> str:
        prompt = EXTRACTION_PROMPT.format(USER_QUERY=query)
        img = PILImage.open(path)
        raw = self._llm.call_vlm_with_prompt_and_image(prompt, img)
        return raw.strip() if raw.strip() else "NO_ITEMS_FOUND"