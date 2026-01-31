# CV Chat PoC — Project Guide

Overview
--------
This is a lightweight local PoC demonstrating a conversational résumé assistant:
- FastAPI backend (ingestion, background processing, chat)
- React frontend (upload + chat UI)
- Local Ollama LLM adapter (CLI or HTTP)
- Storage adapter (GridFS or local fallback)
- SQLAlchemy for employee records (SQLite fallback)

Run (development)
-----------------
1. Backend (from `backend` folder):

   - Create a virtualenv and install requirements (example):

     ```powershell
     cd backend
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     pip install -r requirements.txt
     uvicorn app.main:app --reload --port 8000
     ```

   - Ensure Ollama is installed and either available on PATH or set `OLLAMA_API_URL` to the local HTTP endpoint.

2. Frontend (from `frontend` folder):

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

Key Endpoints
-------------
- POST /api/upload-cv -> accepts PDF, returns job_id.
- GET /api/job/{job_id} -> poll background processing result (returns employee_id when done).
- POST /api/chat -> { prompt, employee_id? } -> returns { reply } (if employee_id set, prompt is enriched with resume text).
- GET /api/employee/{id}/raw -> debugging excerpt and raw_len.
- GET /api/chat-debug -> quick LLM + DB + storage health probe.

Current Implemented Features
----------------------------
- Resume upload + background ingestion (BackgroundTasks).
- PDF text extraction (pdfplumber) with local storage fallback.
- LLM-driven structured extraction (name/email/phone) that attempts to parse and save fields into `employees`.
- Frontend upload flow that polls job status and includes `employee_id` in chat requests.
- Prompt logging for both extraction and chat (under `data/prompts/` and `data/jobs/`).
- Basic chat endpoint that enriches prompts with `Employee.raw_text`.

Pending / Suggested Next Work
----------------------------
- OCR fallback (Tesseract/pytesseract) for scanned-image PDFs — recommended if resumes are scanned.
- OCR fallback (Tesseract/pytesseract) for scanned-image PDFs — implemented as a fallback. Note: you must install the Tesseract binary on the host (Windows: install from https://github.com/tesseract-ocr/tesseract/releases) and ensure it's on PATH. The backend uses `pytesseract` + `Pillow` and pdfplumber's `page.to_image()` so no additional poppler dependency is required for the common case.
- Embeddings + FAISS vector store for RAG retrieval to improve chat relevance.
- CRUD-by-NL and confirmation workflows for safe DB updates.
- Production hardening (auth, TLS, rate limits, background worker like Celery + Redis).

POC A Status Summary
--------------------
POC A planned a modular pipeline (FastAPI + BackgroundTasks, local Ollama, PDF extraction, vector store, RAG). Current implementation status:

- Implemented: FastAPI backend, BackgroundTasks ingestion, storage adapter, PDF extractor, SQLAlchemy Employee model, Ollama adapter, React frontend, job polling, LLM-driven extraction for structured fields, prompt logging.
- Partially implemented: Chat enrichment via Employee.raw_text (works when employee_id is provided). Frontend shows prompts and replies.
- Pending: Embeddings & FAISS (RAG), OCR fallback, robust CRUD-by-NL behavior, tests, and deployment hardening.

Full POC A feature checklist (requested/targeted features)
------------------------------------------------------
Below is a detailed list of features and functionality that were scoped for "POC A" along with the current status (Done / Partial / Pending). Use this as a single-source checklist for what's implemented and what remains.

- Ingest & storage
   - Accept PDF resumes via HTTP upload endpoint (POST /api/upload-cv). — Done
   - Store raw PDF (GridFS when MONGO_URI available, local filesystem fallback). — Done (storage adapter implemented; verify configured MONGO_URI to use GridFS)
   - Job artifacts: write prompts, extracted text, metadata under `data/jobs/{job_id}.*`. — Done

- PDF processing & extraction
   - Extract candidate text using `pdfplumber`. — Done
   - OCR fallback via `pytesseract` + `Pillow` when initial extraction yields no text. — Partially Done (fallback implemented; requires host Tesseract binary to be installed)
   - Chunking of resume text for embeddings/indexing. — Done (chunking present in pipeline)

- LLM extraction & adapters
   - Ollama adapter (HTTP endpoint or CLI fallback). — Done
   - LLM-driven structured extraction (JSON with pydantic validation for name/email/phone/etc.). — Done
   - Prompt logging for both extraction and chat (timestamped under `data/prompts/`). — Done

- Embeddings, indexing & RAG
   - Embeddings via `sentence-transformers` (normalized vectors). — Done (service wrapper present)
   - FAISS vectorstore for chunk retrieval and persistence on disk. — Done (FAISS index and metadata persisted under `data/faiss/`)
   - RAG retrieval in chat endpoint to prepend top-k chunks for a given employee_id. — Done (chat performs retrieval when employee_id provided)

- Chat & UI
   - Chat endpoint (POST /api/chat) that accepts { prompt, employee_id? } and returns { reply }. — Done
   - Frontend single-step flow: pick a PDF, press Enter/Send — file uploads, is processed, and subsequent chat requests are enriched by the employee_id. — Done (frontend has merged upload+send flow)
   - UI niceties: '+' file picker, Enter to send, spinner while LLM thinking, message types (user/assistant/info/error), QA grouping, timestamps, dark-mode toggle. — Partial/Done (core pieces implemented; some styling still pending full Tailwind migration)
   - Smooth scrolling + offset so newest QA doesn't hug the bottom edge. — Done (smooth scroll implemented in `frontend/src/App.jsx`)

- CRUD-by-NL
   - Endpoint to parse natural-language CRUD commands into a pending JSON proposal (`POST /api/nl-command`). — Done
   - Endpoints to view pending proposals and confirm (`GET /api/nl/{pending_id}`, `POST /api/nl/{pending_id}/confirm`). — Done
   - Frontend component to issue NL commands and confirm proposed DB updates. — Done (basic UI exists; more UX polish possible)

- Background processing & scaling
   - BackgroundTasks-based PoC processing pipeline for ingestion (FastAPI BackgroundTasks). — Done
   - Plan/adapter to swap to Celery + Redis for production. — Pending (design notes present; not wired)

- DB & migrations
   - SQLAlchemy models for `employees` with SQLite fallback. — Done
   - Option to use Postgres via DATABASE_URL env var. — Done (supported by session config)
   - Alembic migrations (recommended next step). — Pending

- Diagnostics & ops
   - Diagnostic endpoints for storage/db health (`GET /api/storage-status`, `GET /api/db-status`). — Done
   - Chat debug endpoint to exercise LLM + RAG quickly (`/api/chat-debug`). — Done
   - Logging of prompts and job metadata to help reproduce/explain LLM output. — Done

- Tests, docs, CI
   - Unit tests for extractor, llm adapter, and vectorstore. — Pending
   - End-to-end smoke test for upload→ingest→chat flow. — Pending
   - Project docs and a readable changelog (this file + `CHANGELOG.md`). — Done (basic docs updated here)

- Security & production hardening
   - Authentication/authorization for APIs. — Pending
   - TLS, rate limiting, input validation hardening. — Pending
   - Secrets management for LLM endpoints and DB credentials. — Pending

If you'd like, I can start turning any of the Pending items into concrete PR-sized tasks. Suggested next high-impact work: (1) wire Celery + Redis for robust background jobs, (2) add Alembic migrations and a simple test suite, or (3) finish the frontend Tailwind migration and convert legacy styles to utility classes.

Approximate feature count:
- Total POC A target features: ~10 major items (ingest, extractor, storage, LLM adapter, embeddings/indexing, RAG, CRUD-by-NL, UI, background queue, logging/ops).
- Implemented: ~5-6 (ingest, extractor, storage, LLM adapter, UI, structured extraction, logging).
- Pending: ~4-5 (embeddings/indexing, RAG retrieval, OCR fallback, CRUD-by-NL, Celery/production queueing).

Where to look in the repo
-------------------------
- `backend/app/main.py` — API, ingestion, extraction orchestration, chat.
- `backend/app/services/llm_adapter.py` — Ollama CLI/HTTP adapter.
- `backend/app/services/extractor.py` — pdfplumber extraction.
- `backend/app/services/storage.py` — GridFS / local fallback.
- `frontend/src` — React UI.

Contact / Notes
---------------
If you want, I can now add OCR fallback, implement FAISS-based RAG, or wire Celery for production background jobs. State which feature you'd like next.
