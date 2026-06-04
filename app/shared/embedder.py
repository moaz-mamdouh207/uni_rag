from enum import Enum
from pydantic import BaseModel

from langchain_core.embeddings import Embeddings


class EmbeddingSettings(BaseModel):
    dimension: int
    provider: str
    model: str
    api_key: str
    base_url: str | None 



class EmbeddingProvider(Enum):
    OPENAI = "openai"
    GOOGLE = "google"


 
class Embedder:
    def __init__(self, settings: EmbeddingSettings):
        self.settings = settings
        self._client = self._build_client()

    def _build_client(self) -> Embeddings:
        if self.settings.provider == EmbeddingProvider.OPENAI.value:
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(
                model=self.settings.model,
                api_key=self.settings.api_key, # type: ignore
                base_url=self.settings.base_url,  # None means use default OpenAI endpoint
            )

        elif self.settings.provider == EmbeddingProvider.GOOGLE.value:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            return GoogleGenerativeAIEmbeddings(
                model=self.settings.model,
                google_api_key=self.settings.api_key, # type: ignore
            )

        else:
            raise ValueError(f"Unsupported provider: {self.settings.provider}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._client.embed_documents(texts)
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        return await self._client.aembed_query(text)