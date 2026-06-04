from pydantic import BaseModel

class LLMSettings(BaseModel):
    api_key: str
    llm: str
    vlm: str
    temperature: float = 0.2
    max_output_tokens: int = 1024
