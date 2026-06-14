from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING


from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict


from modules.chat.schemas import CitedSource


if TYPE_CHECKING:
    pass
from modules.chat.schemas import CitationMetaData
from modules.chat.utils.temp import AgentState

logger = logging.getLogger(__name__)


class FinishInput(BaseModel):
    answer: str = Field(..., description="The final answer with [sN] inline markers.")
    citation_refs: list[CitationRef] = Field(..., description="List of cited chunk IDs in order of appearance.")


class CitationRef(BaseModel):
    id: str = Field(
        ...,
        description="The chunk ID as it appears inline e.g. s1, s2."
    )
    reason: str = Field(
        ...,
        description=(
            "A single sentence explaining what this chunk contributed to the answer. "
            "Written for the end user, not the system. "
            "E.g. 'Defines the formula for calculating beam deflection under uniform load.'"
        )
    )


class FinishOutput(BaseModel):
    answer: str
    citations: list[CitationMetaData]


class FinishTool(BaseTool):
    """Emit the final answer + citation to the user."""

    name: str = "finish"
    description: str = (
        "Emit the final answer to the user. "
        "Use [sN] inline markers to cite retrieved chunks. "
        "In citations, list every chunk referenced in the answer with a reason "
        "explaining what it contributed, written for the end user."
    )
    args_schema: type[BaseModel] = FinishInput


    state: AgentState

    model_config = ConfigDict(arbitrary_types_allowed=True)


    async def _arun(self, answer: str, citation_refs: list[CitationRef]):

        short_id_to_display: dict[str, str] = {}  # s2 -> [1], s5 -> [2] etc
        citations: list[CitedSource] = []
        counter = 1

        for ref in citation_refs:
            if ref.id in short_id_to_display:
                continue

            meta = self.state.chunk_cache.get(ref.id)
            
            if meta is None:
                logger.warning("parse_answer_and_citations: id %r not in chunk_cache", ref.id)
                continue

            display = f"[{counter}]"
            short_id_to_display[ref.id] = display
            counter += 1

            citations.append(CitedSource(
                index=display,
                reason=ref.reason,
                document_id=meta.document_id,
                starting_page=meta.starting_page,
                end_page=meta.end_page,
            ))

        def replace_marker(match: re.Match) -> str:
            short_id = match.group(1)  # e.g. s2
            return short_id_to_display.get(short_id, match.group(0))  # type: ignore # fallback to original if not found

        clean_answer = re.sub(r"\[([sS]\d+)\]", replace_marker, answer)

        return clean_answer, citations
    

    def _run(self, **kwargs):
        "Required by langchain"
        raise NotImplementedError("The agent is designed to be used async only")
