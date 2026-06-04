from dataclasses import dataclass


@dataclass
class UsageInfo:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class LLMResult:
    content: str
    usage: UsageInfo
