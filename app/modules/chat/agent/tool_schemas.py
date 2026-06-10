"""
Tool I/O schemas for the engineering RAG agent.

Each ToolInput schema maps directly to a tool the LLM can call.
Each ToolOutput schema is what gets injected back into the message history.
"""
from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, Field

from db.relational.constants  import ChunkType


# ---------------------------------------------------------------------------
# Tool inputs  (what the LLM sends)
# ---------------------------------------------------------------------------

class RetrieveInput(BaseModel):
    query: str = Field(..., min_length=1)
    chunk_type: ChunkType | None = Field(
        default=None,
        description=(
            "Filter results by chunk type. "
            "Use 'theory' for conceptual background, definitions, and formulas. "
            "Use 'solved_question' for worked examples from the reference book. "
            "Omit to search across all types."
        ),
    )
    context_hint: str | None = Field(
        default=None,
        description=(
            "Short topic label prepended to the query to narrow the embedding search. "
            "E.g. 'fluid mechanics', 'beam bending', 'thermodynamics'."
        ),
    )


class RetrieveQuery(BaseModel):
    """Single query inside a retrieve_multi call."""
    query:        str            = Field(..., min_length=1)
    chunk_type:   ChunkType | None = Field(default=None)
    context_hint: str | None    = Field(default=None)


class RetrieveMultiInput(BaseModel):
    queries: list[RetrieveQuery] = Field(..., min_length=1)


class CalculateInput(BaseModel):
    expression: str = Field(
        ...,
        min_length=1,
        description=(
            "A mathematical expression to evaluate. "
            "Supports arithmetic, algebra, trig, log, sqrt, and solve(). "
            "For multi-step: 'z = 1/sqrt(2); w = z * 2; [z, w]' (semicolon-separated). "
            "Always use ** for exponentiation, not ^."
        ),
    )


class ClarifyQuestionInput(BaseModel):
    original_text:  str = Field(..., description="The ambiguous question text, verbatim.")
    interpretation: str = Field(..., description="Your interpretation including dependency assumptions.")


class FinishInput(BaseModel):
    answer: str = Field(
        ...,
        min_length=1,
        description=(
            "The complete final answer with inline [N] citation markers and a "
            "%%CITATIONS%% block at the end. See system prompt for exact format."
        ),
    )


# ---------------------------------------------------------------------------
# Tool outputs  (what gets injected back into agent history)
# ---------------------------------------------------------------------------

class RetrieveResultItem(BaseModel):
    """
    What the agent sees in the tool result JSON.
    citation_id is the value to copy verbatim into %%CITATIONS%%.
    document_id is excluded from serialisation so the agent never sees it
    and cannot accidentally use it instead of the chunk identifier.
    """
    index:         int
    content:       str
    score:         float
    citation_id:   str             # copy this value into %%CITATIONS%%
    chunk_type:    ChunkType | None = None
    starting_page: int | None = None
    end_page:      int | None = None

    # Internal only - never sent to the agent
    document_id:   str = Field(default="", exclude=True)

    @property
    def chunk_id(self) -> str:
        """Alias so tools.py can still use .chunk_id internally."""
        return self.citation_id


class RetrieveOutput(BaseModel):
    query:   str
    results: list[RetrieveResultItem]
    total:   int


class RetrieveMultiOutput(BaseModel):
    queries_run: int
    results:     list[RetrieveResultItem]
    total:       int


class CalculateOutput(BaseModel):
    expression: str
    result:     str
    success:    bool
    error:      str | None = None


class ClarifyQuestionOutput(BaseModel):
    recorded:       bool = True
    original_text:  str
    interpretation: str


class FinishOutput(BaseModel):
    answer: str