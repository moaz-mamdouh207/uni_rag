from __future__ import annotations


from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class ClarifyQuestionInput(BaseModel):
    original_text:  str = Field(..., description="The ambiguous question text, verbatim.")
    interpretation: str = Field(..., description="Your interpretation including dependency assumptions.")

    
class ClarifyQuestionTool(BaseTool):
    name: str = "clarify_question"
    description: str = (
        "Record your interpretation of an ambiguous part of the user's question "
        "before answering. Call this when you need to state an assumption."
    )
    args_schema: type[BaseModel] = ClarifyQuestionInput


    async def _arun(self, original_text: str, interpretation: str) -> str:
        return f"Recorded: interpreting '{original_text}' as '{interpretation}'"
    

    def _run(self, **kwargs):
        "Required by langchain"
        raise NotImplementedError("The agent is designed to be used async only")