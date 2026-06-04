"""
Tool I/O schemas for the engineering RAG agent.

Each ToolInput schema maps directly to a tool the LLM can call.
Each ToolOutput schema is what gets injected back into the message history.

Keeping these separate from the rest of chat/schemas.py means the agent
internals are self-contained and easy to test independently.
"""
from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tool inputs  (what the LLM sends)
# ---------------------------------------------------------------------------

class ExtractFileInput(BaseModel):
    file_id: UUID = Field(
        ...,
        description="UUID of the temp file to extract. Call once per attached file.",
    )


class RetrieveInput(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description=(
            "The search query. Should be a specific concept, formula name, or "
            "problem statement — not a generic topic."
        ),
    )
    context_hint: str | None = Field(
        default=None,
        description=(
            "Optional short topic label prepended to the query to narrow the "
            "embedding search. E.g. 'fluid mechanics', 'beam bending', 'thermodynamics'."
        ),
    )


class RetrieveQuery(BaseModel):
    """Single query inside a retrieve_multi call."""
    query:        str      = Field(..., min_length=1)
    context_hint: str | None = Field(default=None)


class RetrieveMultiInput(BaseModel):
    queries: list[RetrieveQuery] = Field(
        ...,
        min_length=1,
        description=(
            "List of independent search queries to run in parallel. "
            "Use when you need context for several questions at once."
        ),
    )


class CalculateInput(BaseModel):
    expression: str = Field(
        ...,
        min_length=1,
        description=(
            "A mathematical expression to evaluate. "
            "Supports arithmetic, algebra, trig, log, sqrt, and solve(). "
            "Examples: '(15 * 6**2) / 8', 'sqrt(144)', 'sin(pi/4)', "
            "'solve(x**2 - 4, x)'. "
            "Always use ** for exponentiation, not ^."
        ),
    )


class ClarifyQuestionInput(BaseModel):
    original_text:  str = Field(
        ...,
        description="The ambiguous or dependent question text, verbatim.",
    )
    interpretation: str = Field(
        ...,
        description=(
            "Your interpretation of what the question is asking, including "
            "any assumptions about dependencies on earlier parts."
        ),
    )


class FinishInput(BaseModel):
    answer: str = Field(
        ...,
        min_length=1,
        description=(
            "The complete final answer to return to the user. "
            "Format clearly: number answers to match question numbering, "
            "show working for calculations, state units explicitly."
        ),
    )


# ---------------------------------------------------------------------------
# Tool outputs  (what gets injected back into agent history)
# ---------------------------------------------------------------------------

class ExtractFileOutput(BaseModel):
    file_id:          UUID
    file_type:        str
    markdown_content: str   # structured extraction or NO_ITEMS_FOUND
    item_count:       int   # number of ## Item blocks found


class RetrieveOutput(BaseModel):
    query:   str
    results: list[RetrieveResultItem]
    total:   int


class RetrieveResultItem(BaseModel):
    index:       int
    content:     str
    score:       float
    document_id: str


class RetrieveMultiOutput(BaseModel):
    queries_run: int
    results:     list[RetrieveResultItem]
    total:       int


class CalculateOutput(BaseModel):
    expression: str
    result:     str    # string so it handles symbolic results cleanly
    success:    bool
    error:      str | None = None


class ClarifyQuestionOutput(BaseModel):
    recorded:       bool = True
    original_text:  str
    interpretation: str


class FinishOutput(BaseModel):
    answer: str
