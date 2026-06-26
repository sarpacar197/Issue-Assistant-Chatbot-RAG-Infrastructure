---
title: Issue Chatbot
emoji: 🛠️
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: "1.40.0"
app_file: chat_visualize/streamlit_app.py
pinned: false
---


# Issue Assistant — Multi-Agent Chatbot (LangGraph + RAG)

A conversational assistant that lets users perform product actions in natural
language. It routes each message to a specialized agent: opening issues
(with a form + image/vision auto-fill) or running a root-cause analysis over a
document knowledge base (RAG with a vector database).

## Features
- **Supervisor agent** — classifies the user's intent and routes the request.
- **Issue agent** — opens issues through a form; can auto-fill the form from an
  uploaded complaint-form image using a vision model.
- **Root-cause agent (RAG)** — semantic search over indexed documents in
  Weaviate, then an LLM answers based on the retrieved context.
- **Summarizer agent** — turns raw results into a clean reply.
- **Conversation memory** + multi-chat sidebar.

## Architecture
```
User (Streamlit)
      │
      ▼
[Supervisor] ── classifies intent
      ├── issue      → Issue agent → form/vision → FastAPI → SQLite
      ├── rootcause  → RAG agent → Weaviate (semantic search) → LLM
      └── other      → general chat
      │
      ▼
[Summarizer] → reply to user
```

## Tech Stack
- **LangGraph / LangChain** — agent orchestration
- **Azure OpenAI** — chat + embedding models
- **Weaviate** — vector database (semantic search)
- **FastAPI** — issue API
- **SQLite** — issue storage
- **Streamlit** — UI

## Project Structure
```
.
├── api.py                  # FastAPI - issue creation endpoint
├── requirements.txt
├── .env.example
├── chat_visualize/
│   ├── streamlit_app.py    # UI (chat + issue form + image upload)
│   ├── agent_core.py       # agents, tools, LLM/embedder
│   ├── orchestrate.py      # supervisor + routing + summarizer (graph)
│   └── .streamlit/config.toml
└── weaviate/
    └── load_data.py        # one-time: embed documents → Weaviate
```

## Prerequisites
- Python 3.11 or 3.12 (3.14 not recommended)
- Docker (for Weaviate)
- Azure OpenAI access (a chat deployment + an embedding deployment)

## 1. Install
```bash
pip install -r requirements.txt
```

## 2. Configure
Copy the example env file and fill in your values:
```bash
cp .env.example .env
```
`.env`:
```
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_CHAT_DEPLOYMENT=gpt-4o
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_API_VERSION=2025-01-01-preview
```
> The chat deployment must support tool-calling and (for image upload) vision.

## 3. Start Weaviate
```bash
docker run -d --name weaviate -p 8080:8080 -p 50051:50051 \
  -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
  -e PERSISTENCE_DATA_PATH=/var/lib/weaviate \
  -e CLUSTER_HOSTNAME=node1 \
  cr.weaviate.io/semitechnologies/weaviate:1.27.0
```

## 4. Create the SQLite table
```bash
python -c "import sqlite3; c=sqlite3.connect('resolve_core_issue.db'); c.execute('''CREATE TABLE IF NOT EXISTS resolve_core_issue (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, priority TEXT, status TEXT, source TEXT, assignee_name TEXT, assignee_email TEXT, meta TEXT, created_date TEXT, inserted_at TEXT, updated_at TEXT)'''); c.commit(); c.close()"
```

## 5. (Optional) Load documents for root-cause
Put `.docx` files in a folder and set `DOCS_PATH`, then:
```bash
python weaviate/load_data.py
```

## 6. Run
In separate terminals:
```bash
# API
uvicorn api:app --reload

# UI
cd chat_visualize
streamlit run streamlit_app.py
```
Open http://localhost:8501

## Usage
- **Open an issue:** "I want to open an issue" → fill the form (or upload a
  complaint-form image to auto-fill) → submit.
- **Root cause:** "I'm having X problem, what could be the cause?"
- **Chat:** ask anything else.

## Notes
- Conversation memory is in-memory (`MemorySaver`); use a persistent
  checkpointer (e.g. Postgres) for production.
- Embedding model used for indexing and querying must match (same dimensions).