<div align="center">

<img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/FastAPI-0.128-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
<img src="https://img.shields.io/badge/Celery-5.5-37814A?style=for-the-badge&logo=celery&logoColor=white" />
<img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
<img src="https://img.shields.io/badge/Qdrant-Vector%20DB-DC244C?style=for-the-badge&logo=qdrant&logoColor=white" />
<img src="https://img.shields.io/badge/Redis-8.0-FF4438?style=for-the-badge&logo=redis&logoColor=white" />

<br /><br />

```
██╗   ██╗███╗   ██╗██╗    ██████╗  █████╗  ██████╗
██║   ██║████╗  ██║██║    ██╔══██╗██╔══██╗██╔════╝
██║   ██║██╔██╗ ██║██║    ██████╔╝███████║██║  ███╗
██║   ██║██║╚██╗██║██║    ██╔══██╗██╔══██║██║   ██║
╚██████╔╝██║ ╚████║██║    ██║  ██║██║  ██║╚██████╔╝
 ╚═════╝ ╚═╝  ╚═══╝╚═╝    ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝
```

### A production-grade Retrieval-Augmented Generation backend
**Upload course documents → Ask questions → Get grounded answers**

[Features](#-features) · [Architecture](#-architecture) · [Quick Start](#-quick-start) · [API Reference](#-api-reference) · [Configuration](#-configuration) · [Testing](#-testing)

</div>

---

## 📖 Overview

**UniRAG** is a modular-monolith RAG (Retrieval-Augmented Generation) backend built for academic use cases. Students and educators can upload course materials (PDFs, text files), then have natural conversations grounded exclusively in that content — no hallucinations, no made-up facts.

The system handles the full pipeline autonomously:

```
Upload PDF/TXT  →  Extract text  →  Chunk  →  Embed  →  Store in Qdrant
                                                              ↓
Ask a question  →  Embed query  →  Vector search  →  Rerank  →  LLM  →  Answer
```

---

## ✨ Features

| Feature | Details |
|---|---|
| 📁 **Document Management** | Upload PDFs and text files per course with duplicate detection via SHA-256 hashing |
| ⚡ **Async Ingestion Pipeline** | Celery-powered background processing: extract → chunk → embed → index |
| 🔍 **Semantic Retrieval** | Vector similarity search via Qdrant with optional reranking |
| 💬 **Grounded Chat** | Conversation history with context-window trimming, answers sourced only from uploaded content |
| 🔐 **JWT Authentication** | Access + refresh token rotation, bcrypt passwords, per-user data isolation |
| 📊 **Task Status Polling** | Real-time ingestion progress via task ID |
| 🔌 **Pluggable Providers** | Swap embedding (OpenAI / Google) or vector DB (Qdrant / pgvector) via config |
| 🧪 **Test Suite** | Repository-layer tests with per-test in-memory SQLite databases |

---

## 🏗️ Architecture

UniRAG follows a **modular monolith** pattern — all modules live in one deployable unit but are cleanly separated by domain, with explicit dependency boundaries.

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI App                          │
│                                                             │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  │
│  │   auth   │  │ knowledge │  │   chat   │  │ingestion │  │
│  │  module  │  │  module   │  │  module  │  │  module  │  │
│  └──────────┘  └───────────┘  └──────────┘  └──────────┘  │
│                      │               │                      │
│              ┌────────────────────────────┐                 │
│              │      retrieval module      │                 │
│              └────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
         │                  │                    │
   ┌─────▼─────┐    ┌───────▼──────┐    ┌───────▼──────┐
   │ PostgreSQL │    │    Qdrant    │    │    Redis     │
   │ (SQLAlch) │    │  Vector DB   │    │  (Celery)    │
   └───────────┘    └──────────────┘    └──────────────┘
```

### Module Responsibilities

```
modules/
├── auth/          JWT auth, token rotation, user management
├── knowledge/     Course + document CRUD, file validation, disk storage
├── chat/          Conversation management, RAG orchestration, LLM calls
├── retrieval/     Query embedding, vector search, reranking
└── ingestion/     Celery tasks: extract → chunk → embed → index
```

### Ingestion Pipeline (Async)

```
HTTP POST /documents
        │
        ▼
┌───────────────┐      ┌──────────────────────────────────────────────┐
│  Validate &   │      │              Celery Workers                  │
│  Save to disk ├─────►│                                              │
│  Queue task   │      │  process_task          index_task            │
└───────────────┘      │  ┌────────────┐        ┌─────────────────┐  │
        │              │  │ Load file  │        │ Embed chunks    │  │
        │              │  │ Chunk text │──chain►│ Upsert Qdrant   │  │
        ▼              │  │ Save chunks│        │ Set INDEXED     │  │
  Return task_id       │  └────────────┘        └─────────────────┘  │
                       └──────────────────────────────────────────────┘
```

### RAG Chat Flow

```
User message
     │
     ▼
Embed query ──► Vector search (Qdrant) ──► [Optional rerank]
                                                   │
                                                   ▼
                              Trim history + Build prompt
                                                   │
                                                   ▼
                                            LLM (Gemini)
                                                   │
                                                   ▼
                                     Persist messages + Return answer
```

---

## 🗂️ Project Structure

```
uni_rag/
├── app/
│   ├── main.py                  # FastAPI app, middleware, exception handlers
│   ├── celery_app.py            # Celery instance
│   ├── celery_config.py         # Broker, backend, serialization settings
│   │
│   ├── modules/
│   │   ├── auth/                # JWT, bcrypt, token rotation
│   │   ├── knowledge/           # Courses, documents, file I/O
│   │   ├── chat/                # Conversations, prompt builder, history
│   │   ├── retrieval/           # Embedder, vector search, reranker
│   │   └── ingestion/           # Celery tasks, loaders, chunker
│   │
│   ├── db/
│   │   ├── relational/          # SQLAlchemy models, repositories, sessions
│   │   └── vector/              # Qdrant & pgvector providers, factory
│   │
│   ├── shared/
│   │   ├── embedder.py          # LangChain embedding wrapper (OpenAI / Google)
│   │   └── llm/                 # LangChain LLM wrapper (Gemini)
│   │
│   ├── core/
│   │   └── config.py            # Pydantic Settings, nested config
│   │
│   └── tests/
│       └── db/relational/       # Repository-layer tests (SQLite in-memory)
│
└── docker/
    └── docker-compose.yml       # PostgreSQL, Qdrant, Redis
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- A Google Gemini API key (or OpenAI key for alternative providers)

### 1. Clone & Install

```bash
git clone https://github.com/your-username/uni_rag.git
cd uni_rag/app
pip install -r requirements.txt
```

### 2. Start Infrastructure

```bash
cd ../docker
docker-compose up -d
```

This starts:
- **PostgreSQL** on `localhost:5432`
- **Qdrant** on `localhost:6333`
- **Redis** on `localhost:6379`

### 3. Configure Environment

Copy `.env` and fill in your keys:

```bash
cp app/.env app/.env.local
```

Required values to set:

```env
# Your Gemini API key
EMBEDDING__API_KEY=your_google_api_key_here
LLM__API_KEY=your_google_api_key_here

# Database (matches docker-compose defaults)
RELATIONAL_DB__SYNC_URL=postgresql://appuser:apppassword@localhost:5432/appdb
RELATIONAL_DB__ASYNC_URL=postgresql+asyncpg://appuser:apppassword@localhost:5432/appdb

# JWT — change this to a strong random secret
AUTH__JWT_SECRET_KEY=your-strong-secret-here
```

### 4. Run Migrations

```bash
cd app
alembic upgrade head
```

### 5. Start the API

```bash
uvicorn main:app --reload
```

### 6. Start Celery Worker

In a separate terminal:

```bash
cd app
celery -A celery_app worker --loglevel=info
```

The API is now available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

## 📡 API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Create a new account |
| `POST` | `/api/v1/auth/login` | Login, receive token pair |
| `POST` | `/api/v1/auth/refresh` | Exchange refresh token for new access token |
| `POST` | `/api/v1/auth/logout` | Revoke current refresh token |
| `POST` | `/api/v1/auth/logout/all` | Revoke all sessions |
| `GET`  | `/api/v1/auth/me` | Get current user info |
| `POST` | `/api/v1/auth/change-password` | Change password |

### Knowledge (Courses & Documents)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/knowledge/courses` | Create a course |
| `GET`  | `/api/v1/knowledge/courses` | List your courses |
| `PATCH`| `/api/v1/knowledge/courses/{course_id}` | Rename a course |
| `DELETE`| `/api/v1/knowledge/courses/{course_id}` | Delete course + all documents |
| `POST` | `/api/v1/knowledge/courses/{course_id}/documents` | Upload documents (multipart) |
| `GET`  | `/api/v1/knowledge/courses/{course_id}/documents` | List documents |
| `PATCH`| `/api/v1/knowledge/courses/{course_id}/documents/{document_id}` | Update document metadata |
| `DELETE`| `/api/v1/knowledge/courses/{course_id}/documents/{document_id}` | Delete document |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/chat/conversations` | Create a conversation (linked to a course) |
| `GET`  | `/api/v1/chat/conversations` | List your conversations |
| `PATCH`| `/api/v1/chat/conversations/{conversation_id}` | Rename conversation |
| `DELETE`| `/api/v1/chat/conversations/{conversation_id}` | Delete conversation |
| `POST` | `/api/v1/chat/conversations/{conversation_id}/messages` | Send a message, get RAG answer |
| `GET`  | `/api/v1/chat/conversations/{conversation_id}/history` | Fetch full message history |

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/v1/tasks/{task_id}` | Poll ingestion task status |

#### Task Status Values

```
PENDING  → Task queued, not yet started
STARTED  → Worker picked it up
SUCCESS  → Document fully indexed, ready to query
FAILURE  → Something went wrong (check error field)
RETRY    → Transient error, retrying automatically
```

---

## 🔄 Typical Usage Flow

```
1.  Register           POST /auth/register
2.  Login              POST /auth/login          → save access_token + refresh_token
3.  Create course      POST /knowledge/courses   → save course_id
4.  Upload documents   POST /knowledge/courses/{course_id}/documents
                                                  → save task_id per file
5.  Poll until ready   GET  /tasks/{task_id}     → wait for status == "SUCCESS"
6.  Start a chat       POST /chat/conversations   → save conversation_id
                            body: { name: "...", meta: { course_id: "..." } }
7.  Ask a question     POST /chat/conversations/{conversation_id}/messages
                            body: { query: "What is X?" }
8.  Read history       GET  /chat/conversations/{conversation_id}/history
```

---

## ⚙️ Configuration

All configuration is driven by environment variables with `__` as the nested delimiter. Pydantic Settings validates everything at startup.

### Full Reference

```env
# ── Broker / Queue ────────────────────────────────────────
BROKER_URL=redis://localhost:6379/0
RESULT_BACKEND=redis://localhost:6379/1

# ── Auth ─────────────────────────────────────────────────
AUTH__JWT_SECRET_KEY=change-me
AUTH__JWT_ALGORITHM=HS256
AUTH__JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
AUTH__JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ── Document limits ───────────────────────────────────────
DOCUMENT__MAX_FILE_SIZE_IN_MBS=10
DOCUMENT__BUFFER_SIZE_IN_MBS=5

# ── Embedding ─────────────────────────────────────────────
EMBEDDING__PROVIDER=google           # google | openai
EMBEDDING__MODEL=gemini-embedding-001
EMBEDDING__API_KEY=your_key
EMBEDDING__DIMENSION=3072
EMBEDDING__BASE_URL=                 # OpenAI only

# ── LLM ──────────────────────────────────────────────────
LLM__MODEL=gemini-2.5-flash
LLM__TEMPERATURE=0.2
LLM__MAX_OUTPUT_TOKENS=1024
LLM__API_KEY=your_key

# ── Relational DB ─────────────────────────────────────────
RELATIONAL_DB__SYNC_URL=postgresql://user:pass@localhost:5432/db
RELATIONAL_DB__ASYNC_URL=postgresql+asyncpg://user:pass@localhost:5432/db
RELATIONAL_DB__ECHO=false
RELATIONAL_DB__POOL_SIZE=10
RELATIONAL_DB__MAX_OVERFLOW=20

# ── Vector DB ─────────────────────────────────────────────
VECTOR_DB__PROVIDER=qdrant           # qdrant | pgvector

# Qdrant
VECTOR_DB_QDRANT__URL=http://localhost:6333
VECTOR_DB_QDRANT__API_KEY=
VECTOR_DB_QDRANT__COLLECTION_NAME=uni_rag
VECTOR_DB_QDRANT__PREFER_GRPC=false
VECTOR_DB_QDRANT__TIMEOUT=10

# ── Chat ──────────────────────────────────────────────────
CHAT__CONTEXT_WINDOW_LIMIT=2000
```

### Switching Embedding Provider to OpenAI

```env
EMBEDDING__PROVIDER=openai
EMBEDDING__MODEL=text-embedding-3-large
EMBEDDING__API_KEY=sk-...
EMBEDDING__DIMENSION=3072
EMBEDDING__BASE_URL=                 # leave empty for official OpenAI
```

---

## 🧪 Testing

Tests use in-memory SQLite so no running database is required.

```bash
cd app
pytest
```

### Test Coverage

| Area | What's tested |
|------|--------------|
| `AsyncUserRepository` | CRUD, defaults, timestamps, not-found |
| `AsyncCourseRepository` | CRUD, user isolation, not-found |
| `AsyncDocumentRepository` | CRUD, bulk add, status updates, sync variant |
| `SyncChunkRepository` | add, bulk_add, document assignment |
| `AsyncConversationRepository` | CRUD, metadata round-trip, user isolation |
| `AsyncMessageRepository` | add, ordering, conversation isolation |
| Model defaults & cascades | Timestamps, UUID PKs, cascade deletes |
| Exception classes | Message format, inheritance hierarchy |
| RefreshToken properties | `is_expired`, `is_valid` logic |

```bash
# Run a specific test file
pytest tests/db/relational/test_user_repository.py -v

# Run with output
pytest -s
```

---

## 🔌 Extending the System

### Add a New Embedding Provider

1. Add a new value to `EmbeddingProvider` in `shared/embedder.py`
2. Add a branch in `Embedder._build_client()`
3. Set `EMBEDDING__PROVIDER=your_provider` in `.env`

### Add a New Vector DB Provider

1. Create `db/vector/providers/your_provider.py` implementing both `SyncVectorDBRepository` and `AsyncVectorDBRepository`
2. Add a case to the `match` block in `db/vector/vector_repo_factory.py`
3. Add settings to `db/vector/config.py`
4. Set `VECTOR_DB__PROVIDER=your_provider` in `.env`

### Add a New Document Type

1. Add a new value to `shared/enums.FileType`
2. Create a loader class in `modules/ingestion/loaders.py` extending `BaseLoader`
3. Register it in `LoaderFactory._registry`

---

## 🗄️ Database Schema

### Relational (PostgreSQL)

```
user
├── id (UUID PK)
├── email (unique)
├── hashed_password
├── full_name
├── role
├── is_active
└── is_verified

course
├── id (UUID PK)
├── user_id (FK → user, CASCADE)
└── name

document
├── id (UUID PK)
├── course_id (FK → course, CASCADE)
├── original_name / stored_name / file_path
├── type (PDF | TEXT)
├── status (UPLOADED → EXTRACTING → CHUNKED → INDEXED | FAILED)
└── chunks_count / indexed_at

chunk
├── id (UUID PK)
├── document_id (FK → document, CASCADE)
├── chunk_index / content
└── starting_page / end_page / token_count

conversation
├── id (UUID PK)
├── user_id (FK → user, CASCADE)
├── name
└── meta (JSON: { course_id, documents_ids? })

message
├── id (UUID PK)
├── conversation_id (FK → conversation, CASCADE)
├── role (system | user | assistant)
├── content
└── token_count

refresh_token
├── id (UUID PK)
├── user_id (FK → user, CASCADE)
├── token_hash (SHA-256)
├── expires_at
└── revoked
```

### Vector (Qdrant)

Each point stored in Qdrant:

```json
{
  "id": "<chunk_uuid>",
  "vector": [0.1, 0.2, ...],
  "payload": {
    "user_id": "...",
    "course_id": "...",
    "document_id": "...",
    "content": "chunk text..."
  }
}
```

Payload indexes on `user_id` and `course_id` enforce per-user isolation at the vector search level.

---

## 🐳 Docker

The `docker-compose.yml` provides all three infrastructure services:

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop everything
docker-compose down

# Stop and remove volumes (wipe all data)
docker-compose down -v
```

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL | 5432 | Relational data |
| Qdrant | 6333 (HTTP), 6334 (gRPC) | Vector search |
| Redis | 6379 | Celery broker + result backend |

---

## 🛡️ Security Notes

- Passwords are hashed with **bcrypt** via `passlib`
- Refresh tokens are stored as **SHA-256 hashes** — raw tokens never touch the database
- Token rotation on every refresh — old token is revoked immediately
- Vector search always scopes to `user_id` — users cannot access each other's data
- File type validation uses **magic bytes** (not file extension) to prevent spoofing
- Duplicate files detected by content hash before disk write

---

## 📋 Requirements

```
Python         3.11+
FastAPI        0.128
SQLAlchemy     2.0
Celery         5.5
Redis          (broker)
PostgreSQL     16
Qdrant         latest
LangChain      1.2 + community + google-genai
```

Full list in `app/requirements.txt`.

---

## 📄 License

MIT

---

<div align="center">

Built with FastAPI · SQLAlchemy · Celery · Qdrant · LangChain · Gemini

</div>
