# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
# Windows — activate venv, install deps, configure API key
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # then set GROQ_API_KEY in .env
```

Get a free Groq API key at https://console.groq.com (no credit card required).

## Architecture

This is a 5-milestone RAG (Retrieval Augmented Generation) pipeline:

1. **Ingestion** — scrape/load source documents into `documents/`
2. **Chunking** — split docs into overlapping text chunks
3. **Embedding + Vector Store** — embed chunks with `sentence-transformers`, persist to ChromaDB (`chroma_db/`)
4. **Retrieval** — query ChromaDB for top-k relevant chunks given a user query
5. **Generation** — pass retrieved chunks + query to Groq API and return a grounded answer

Core libraries: `sentence-transformers` (embeddings), `chromadb` (vector store), `groq` (LLM inference), `python-dotenv` (env vars).

## Key conventions

- Source documents → `documents/` (plain text or PDF)
- ChromaDB persistence → `chroma_db/` (git-ignored)
- API key → `.env` (git-ignored)
- Optional UI (Milestone 5): uncomment `gradio` or `streamlit` in `requirements.txt`
- Optional PDF support: uncomment `pdfplumber` in `requirements.txt`

## Running scripts

Scripts are created per milestone; run from the repo root with the venv active:

```bash
python ingest.py      # Milestone 1 — collect documents
python chunk.py       # Milestone 2 — chunk documents
python embed.py       # Milestone 3 — embed and store
python retrieve.py    # Milestone 4 — test retrieval
python generate.py    # Milestone 5 — end-to-end Q&A
```

Exact filenames depend on your implementation choices.
