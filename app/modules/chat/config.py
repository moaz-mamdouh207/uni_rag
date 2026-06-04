from pydantic import BaseModel, Field


class ChatSettings(BaseModel):
    # --- existing fields (unchanged) ---
    context_window_limit: int   = 2000
    top_k:                int   = Field(default=5,   ge=1,   le=10)
    score_threshold:      float = Field(default=0.7, ge=0.0, le=1.0)
    rerank:               bool  = Field(default=False)

    # --- agentic pipeline ---
    max_agent_iterations: int = Field(
        default=100,
        ge=1,
        le=25,
        description=(
            "Maximum LLM->tool->LLM iterations before forcing a stop. "
            "Engineering problems rarely need more than 5-6 in practice: "
            "extract -> retrieve -> calculate -> finish."
        ),
    )
    max_file_queries: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Max ExtractedQuery items passed to retrieve_multi.",
    )
