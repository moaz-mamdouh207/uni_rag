"""
Tool I/O schemas for the engineering RAG agent.

Each ToolInput schema maps directly to a tool the LLM can call.
Each ToolOutput schema is what gets injected back into the message history.
"""
from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tool inputs  (what the LLM sends)
# ---------------------------------------------------------------------------
class RetrieveInput(BaseModel):
    query: str = Field(..., min_length=1)
    context_hint: str | None = Field(
        default=None,
        description=(
            "Short topic label prepended to the query to narrow the embedding search. "
            "E.g. 'fluid mechanics', 'beam bending', 'thermodynamics'."
        ),
    )


class RetrieveQuery(BaseModel):
    """Single query inside a retrieve_multi call."""
    query:        str      = Field(..., min_length=1)
    context_hint: str | None = Field(default=None)


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
            "The complete final answer. Number answers to match question numbering, "
            "show working for calculations, state units explicitly, "
            "and include [Source: doc_id p.N] inline citations where relevant."
        ),
    )


# ---------------------------------------------------------------------------
# Tool outputs  (what gets injected back into agent history)
# ---------------------------------------------------------------------------

class RetrieveResultItem(BaseModel):
    index:       int
    content:     str
    score:       float
    document_id: str
    chunk_id:    str
    # Page range for citation — populated from chunk metadata when available
    starting_page: int | None = None
    end_page:      int | None = None


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