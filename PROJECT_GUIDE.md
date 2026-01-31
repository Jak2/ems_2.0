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
