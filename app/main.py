from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from modules.auth.router import auth_router
from modules.knowledge.router import knowledge_router
from modules.ingestion.router import ingestion_router
from modules.chat.router import chat_router

from db.vector.factory import get_async_vector_repo

@asynccontextmanager
async def lifespan(app: FastAPI):

    vector_repo = get_async_vector_repo()
    await vector_repo.ensure_collection()

    yield
    # Executed before shutown
    #moaz: close connections
    

app = FastAPI(lifespan=lifespan)
app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
)


app.include_router(auth_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")

# register_ingestion_exception_handlers(app)