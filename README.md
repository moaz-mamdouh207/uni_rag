<div align="center">

<pre>
██╗   ██╗███╗   ██╗██╗██████╗  █████╗  ██████╗
██║   ██║████╗  ██║██║██╔══██╗██╔══██╗██╔════╝
██║   ██║██╔██╗ ██║██║██████╔╝███████║██║  ███╗
██║   ██║██║╚██╗██║██║██╔══██╗██╔══██║██║   ██║
╚██████╔╝██║ ╚████║██║██║  ██║██║  ██║╚██████╔╝
 ╚═════╝ ╚═╝  ╚═══╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝
</pre>

**Your AI study buddy that actually read your lecture slides**

*Upload your course materials. Ask anything. Get answers straight from your notes — with proof.*

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## What is UniRAG?

UniRAG is an AI-powered study assistant built specifically for university students. Upload your lecture slides and PDFs, then ask questions — the assistant finds the exact relevant passages from **your own documents**, shows you where it found them, solves math problems with a built-in calculator for precise answers, and explains things the way your professor does.

Unlike ChatGPT, UniRAG never makes things up from thin air. Every answer comes with a citation pointing back to the exact page in your notes.

---

## How it works

<div align="center">
  <img src="images/illustration.png" alt="UniRAG — how it works" width="1000"/>
</div>

You type a question on your laptop → it travels to the API building → the Security Guard checks your identity → the Filing Room pulls your documents → the Brain reads them, uses the calculator, and writes a cited answer → the answer flies back to you.

---

## What can it do?

| | Feature | What it means for you |
|---|---|---|
| 📚 | **Answers from your own notes** | Upload your PDFs and it only answers from those — no random internet knowledge mixed in |
| 🔍 | **Shows you where it found the answer** | Every response includes the exact source so you can verify and read more |
| 🔢 | **Gets the math right, every time** | Has a built-in calculator — so it never guesses a number |
| 🎓 | **Explains like your professor** | Adapts its style to match how your course teaches the material |
| 📁 | **Organize by course** | Separate knowledge bases per course — no cross-contamination between subjects |
| 💬 | **Full conversation memory** | Ask follow-up questions naturally, it remembers the whole conversation |

---

## Tech Stack

### Backend
| | Technology | Role |
|---|---|---|
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/fastapi/fastapi-original.svg" width="20"/> | **FastAPI** | API framework |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg" width="20"/> | **Celery + Redis** | Async document processing |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/postgresql/postgresql-original.svg" width="20"/> | **PostgreSQL** | Users, courses, conversations |
| 🧠 | **Google Gemini / OpenAI** | LLM + embeddings (configurable) |
| 🔷 | **Qdrant / pgvector** | Vector search (switchable) |

### Frontend
| | Technology | Role |
|---|---|---|
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nextjs/nextjs-original.svg" width="20"/> | **Next.js 16 + React 19** | UI framework |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/tailwindcss/tailwindcss-original.svg" width="20"/> | **Tailwind CSS v4** | Styling |
| 📐 | **KaTeX** | Math equation rendering |

---

## Project Structure

```
.
├── app/                    # FastAPI backend
│   ├── modules/
│   │   ├── auth/           # JWT authentication
│   │   ├── chat/           # Conversation management + agent loop
│   │   │   └── agent/      # Tool definitions, loop logic, prompts
│   │   ├── ingestion/      # Document parsing, chunking, Celery tasks
│   │   ├── retrieval/      # Vector search + reranking
│   │   └── knowledge/      # Course and document management
│   ├── db/
│   │   ├── relational/     # PostgreSQL models + repositories
│   │   └── vector/         # Qdrant + pgvector providers (factory)
│   ├── shared/             # Embedder, LLM client, enums, tracing
│   └── eval/               # RAGAS evaluation suite
│
├── GUI/                    # Next.js frontend
│   ├── app/                # App router pages
│   ├── components/         # Sidebar, ChatArea, modals
│   └── lib/                # API client, auth context, theme
│
└── docker/                 # Docker Compose stack
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker + Docker Compose
- Git

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/uni-rag.git
cd uni-rag
```

### 2. Set up the backend

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

cd app
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys and DB credentials
```

### 3. Set up the frontend

```bash
cd GUI
npm install
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### 4. Start infrastructure

```bash
cd docker
docker compose up -d
```

### 5. Run database migrations

```bash
cd app
alembic upgrade head
```

### 6. Start the services

```bash
# Terminal 1 — API
cd app && uvicorn main:app --reload --port 8000

# Terminal 2 — Background worker
cd app && celery -A celery_app worker --loglevel=info

# Terminal 3 — Frontend
cd GUI && npm run dev
```

---
Visit **http://localhost:3000**

---

<div align="center">

Built with ❤️ for students who deserve better study tools.

*Backend deep-dive → [`app/README.md`](app/README.md)*

</div>