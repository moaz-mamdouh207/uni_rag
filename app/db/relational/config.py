from pydantic import BaseModel

class RelationalDBSettings(BaseModel):
    sync_url: str
    async_url: str
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20 