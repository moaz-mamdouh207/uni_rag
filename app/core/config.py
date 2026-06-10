from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from modules.auth.config import AuthSettings
from modules.knowledge.config import DocumentSettings
from modules.chat.config import ChatSettings
from shared.embedder import EmbeddingSettings
from shared.tracing import LangfuseSettings
from db.vector.config import VectorDBSettings
from db.relational.config import RelationalDBSettings
from shared.llm.config import LLMSettings
 

class Settings(BaseSettings):
    GOOGLE_API_KEY: str = ""
    # ── Global ───────────────────────────────────────────────────────────────
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/1"

    # ── Modular ──────────────────────────────────────────────────────────────
    auth: AuthSettings                  =   Field(default_factory=AuthSettings)         # type: ignore[arg-type]
    document: DocumentSettings          =   Field(default_factory=DocumentSettings)
    chat: ChatSettings                  =   Field(default_factory=ChatSettings)
    llm: LLMSettings                    =   Field(default_factory=LLMSettings)          # type: ignore[arg-type]
    embedding: EmbeddingSettings        =   Field(default_factory=EmbeddingSettings)    # type: ignore[arg-type]
    relational_db: RelationalDBSettings =   Field(default_factory=RelationalDBSettings) # type: ignore[arg-type]
    vector_db: VectorDBSettings         =   Field(default_factory=VectorDBSettings)
    langfuse: LangfuseSettings          =   Field(default_factory=LangfuseSettings)     # type: ignore[arg-type]


    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
    )


settings = Settings()