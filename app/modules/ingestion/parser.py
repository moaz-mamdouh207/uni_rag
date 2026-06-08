from __future__ import annotations
import io
import re
from typing import List, Dict
from pathlib import Path
import subprocess
import tempfile

import fitz
from PIL import Image as PILImage

from db.relational.schemas import ChunkCreate
from db.relational.constants import ChunkType
from modules.ingestion.prompt import build_prompt
from shared.llm.client import LLMClient

def chunk_output(
        raw_text: str, 
        existing_chunks: List[ChunkCreate], 
        page_number: int,
        equations: Dict[str, str],
        figures: Dict[str, str],
        tables: Dict[str, str],
        index: int
    ) -> int:
    """
    Parses LLM output for a single page with support for:
    - Standard Theory chunks (<<<START>>>)
    - Cross-page continuation chunks (<<<CONTINUE>>>)
    - Solved Examples chunks (<<<SOLVED_QUESTION>>>)
    - Unsolved Exercises chunks (<<<UNSOLVED_QUESTION>>>)
    """
    if "<<<SKIP_PAGE>>>" in raw_text:
        return index

    # --- PHASE 1: DISCOVER AND MAP DATA OBJECTS ---
    eq_pattern = r"<<<EQUATION\|([^|]+)\|([^>]+)>>>"
    fig_pattern = r"<<<FIGURE\|([^|]+)\|([^>]+)>>>"
    table_pattern = r"<<<TABLE\|([^|]+)\|([^|]+)\|([^>]+)>>>"

    

    for label, latex in re.findall(eq_pattern, raw_text):
        equations[label.strip()] = latex.strip()

    for label, description in re.findall(fig_pattern, raw_text):
        figures[label.strip()] = description.strip()

    for label, caption, md_table in re.findall(table_pattern, raw_text):
        tables[label.strip()] = f"**{caption.strip()}**\n{md_table.strip()}"

    # --- PHASE 2: EXTRACT CHUNKS WITH TYPE IDENTIFICATION ---
    # MODIFIED: Captures all four valid chunk tags
    chunk_pattern = r"(<<<START>>>|<<<CONTINUE>>>|<<<SOLVED_QUESTION>>>|<<<UNSOLVED_QUESTION>>>)(.*?)(?:<<<END>>>)"
    raw_chunks = re.findall(chunk_pattern, raw_text, re.DOTALL)

    for tag, chunk_body in raw_chunks:
        chunk_content = chunk_body.strip()

        # 1. Resolve all cross-references inside this chunk text
        def replace_eq_ref(match):
            lbl = match.group(1).strip()
            eq_content = equations.get(lbl, f"[Equation {lbl}]")
            return f"({lbl} : {eq_content})"
        chunk_content = re.sub(r"<<<REF_EQ\|([^>]+)>>>", replace_eq_ref, chunk_content)

        def replace_fig_ref(match):
            lbl = match.group(1).strip()
            figure_content = figures.get(lbl, f"[Figure {lbl}]")
            return f"({lbl} : {figure_content})"
        chunk_content = re.sub(r"<<<REF_FIG\|([^>]+)>>>", replace_fig_ref, chunk_content)

        def replace_table_ref(match):
            lbl = match.group(1).strip()
            table_content = tables.get(lbl, f"[Table {lbl}]")
            return f"({lbl} : {table_content})"
        chunk_content = re.sub(r"<<<REF_TABLE\|([^>]+)>>>", replace_table_ref, chunk_content)

        # 2. Merge or Append based on the tag type
        if tag == "<<<CONTINUE>>>" and existing_chunks:
            existing_chunks[-1].content += " " + chunk_content
            existing_chunks[-1].end_page = page_number  # Update the end page to the current page

        else:
            chunk = ChunkCreate(
                index=index,
                starting_page=page_number,
                end_page=page_number,
                token_count=None,
                type=ChunkType.SOLVED_QUESTION if tag == "<<<SOLVED_QUESTION>>>" else (ChunkType.UNSOLVED_QUESTION if tag == "<<<UNSOLVED_QUESTION>>>" else ChunkType.THEORY),
                content=chunk_content
            )
            existing_chunks.append(chunk)
            index += 1

    return index


class PdfParser:
    def __init__(self, llm_client: LLMClient):
        self.vlm = llm_client


    def load(self, file_path: Path) -> list[ChunkCreate]:
        index = 1
        prev_chunk    = ""
        chunks: List[ChunkCreate] = []
        equations: Dict[str, str] = {}
        figures: Dict[str, str] = {}
        tables: Dict[str, str] = {}

        docs = fitz.open(file_path)

        for page_no, page in enumerate(docs, start=1): # type: ignore
            pix = page.get_pixmap(dpi=150)
            img = PILImage.open(io.BytesIO(pix.tobytes("png")))

            raw_text = self.vlm.call_vlm_with_prompt_and_image(build_prompt(prev_chunk), img)
            
            index = chunk_output(
                raw_text=raw_text, 
                existing_chunks=chunks, 
                page_number=page_no,
                equations=equations,
                figures=figures,
                tables=tables,
                index=index
            )

            prev_chunk = chunks[-1].content if chunks else ""

        return chunks





def _convert_to_pdf_via_libreoffice(file_path: Path, output_dir: Path) -> Path:
    """
    Converts .docx or .pptx to PDF using LibreOffice headless.
    Returns the path to the generated PDF.

    Requires LibreOffice installed:
        Ubuntu/Debian: sudo apt install libreoffice
        macOS:         brew install --cask libreoffice
    """
    subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(output_dir),
            str(file_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pdf_path = output_dir / (file_path.stem + ".pdf")
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"LibreOffice conversion failed: expected output at {pdf_path}"
        )
    return pdf_path


class DocxParser:
    """
    Parses .docx files by converting them to PDF via LibreOffice,
    then running the same VLM-based pipeline as PdfParser.
    """

    def __init__(self, llm_client: LLMClient):
        self.vlm = llm_client

    def load(self, file_path: Path) -> List[ChunkCreate]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pdf_path = _convert_to_pdf_via_libreoffice(file_path, tmp_path)
            parser = PdfParser(llm_client=self.vlm)
            return parser.load(pdf_path)


class PptxParser:
    """
    Parses .pptx files by converting them to PDF via LibreOffice,
    then running the same VLM-based pipeline as PdfParser.

    Each slide becomes one "page" in the PDF, so page_number in
    ChunkCreate naturally maps to slide number.
    """

    def __init__(self, llm_client: LLMClient):
        self.vlm = llm_client

    def load(self, file_path: Path) -> List[ChunkCreate]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pdf_path = _convert_to_pdf_via_libreoffice(file_path, tmp_path)
            parser = PdfParser(llm_client=self.vlm)
            return parser.load(pdf_path)
