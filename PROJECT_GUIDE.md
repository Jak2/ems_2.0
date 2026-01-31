# CV Chat PoC — Project Guide

Overview
--------
This is a lightweight local PoC demonstrating a conversational résumé assistant:
- FastAPI backend (ingestion, background processing, chat)
- React frontend (upload + chat UI)
- Local Ollama LLM adapter (CLI or HTTP)
- Storage adapter (GridFS or local fallback)
- SQLAlchemy for employee records (SQLite fallback)

Architecture
------------

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT BROWSER                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              React Frontend (Vite)                        │   │
│  │  - Upload.jsx: File picker, chat input                   │   │
│  │  - App.jsx: Message display, scroll management           │   │
│  │  - NLCrud.jsx: Natural language CRUD UI                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           │ HTTP/JSON (Port 8000)               │
│                           ▼                                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND SERVER                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     main.py (API)                         │   │
│  │  - POST /api/upload-cv                                   │   │
│  │  - POST /api/chat                                        │   │
│  │  - GET  /api/job/{job_id}                               │   │
│  │  - POST /api/nl-command                                  │   │
│  │  - GET  /api/storage-status, /api/db-status             │   │
│  └──────────────────────────────────────────────────────────┘   │
│           │              │               │           │           │
│           ▼              ▼               ▼           ▼           │
│  ┌──────────────┐ ┌──────────┐ ┌──────────────┐ ┌────────────┐ │
│  │   Storage    │ │Extractor │ │  LLM Adapter │ │ Embeddings │ │
│  │   Adapter    │ │(pdfplumb)│ │   (Ollama)   │ │(sent-trans)│ │
│  │              │ │+ Tesseract│ │ HTTP or CLI  │ │            │ │
│  └──────────────┘ └──────────┘ └──────────────┘ └────────────┘ │
│           │                            │              │          │
└───────────┼────────────────────────────┼──────────────┼──────────┘
            ▼                            ▼              ▼
┌─────────────────┐          ┌────────────────┐  ┌──────────────┐
│  File Storage   │          │ Ollama Server  │  │  FAISS Index │
│  - GridFS (opt) │          │ (Local LLM)    │  │  (Vectors)   │
│  - Filesystem   │          │ Port 11434     │  │ data/faiss/  │
│  data/files/    │          └────────────────┘  └──────────────┘
└─────────────────┘
            
┌─────────────────────────────────────────────────────────────────┐
│                   DATABASE LAYER                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            SQLAlchemy + DB Session                        │   │
│  │  models.py: Employee(id, name, email, phone, raw_text)   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │     PostgreSQL (via DATABASE_URL)                         │   │
│  │            OR                                             │   │
│  │     SQLite (backend_dev.db - fallback)                   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow: Frontend ↔ Backend ↔ Database

```
FRONTEND                    BACKEND                      DATABASE/STORAGE
────────                    ───────                      ────────────────

Upload.jsx                 main.py
   │                         │
   │ 1. User selects PDF    │
   │    via + button         │
   │                         │
   │ 2. User types prompt   │
   │    "Ask anything"       │
   │                         │
   │ 3. Click "Send"        │
   │ FormData(file, prompt) │
   ├────────────────────────>│ POST /api/upload-cv
   │                         │
   │                         ├──> storage.save_file()
   │                         │       │
   │                         │       └───> MongoDB GridFS
   │                         │              or data/files/
   │                         │
   │                         │ 4. BackgroundTasks.add_task(process_cv)
   │                         │       │
   │                         │       ├──> extractor.extract_text_from_bytes()
   │                         │       │      (pdfplumber + OCR fallback)
   │                         │       │
   │                         │       ├──> llm.generate(extraction_prompt)
   │                         │       │      (Ollama: parse name/email/phone)
   │                         │       │
   │                         │       ├──> SQLAlchemy: INSERT Employee
   │                         │       │       │
   │                         │       │       └───> PostgreSQL or SQLite
   │                         │       │              (employees table)
   │                         │       │
   │                         │       ├──> chunk_text() + vectorstore.add_chunks()
   │                         │       │       │
   │                         │       │       └───> FAISS index (data/faiss/)
   │                         │       │
   │                         │       └──> Write job status to data/jobs/{job_id}.json
   │                         │
   │<────────────────────────┤ Response: { job_id, status: "queued" }
   │                         │
   │ 5. Poll job status      │
   ├────────────────────────>│ GET /api/job/{job_id}
   │                         │
   │                         ├──> Read data/jobs/{job_id}.json
   │                         │
   │<────────────────────────┤ { status: "done", employee_id: 123 }
   │                         │
   │ 6. Send chat message    │
   ├────────────────────────>│ POST /api/chat
   │ { prompt, employee_id } │       { prompt, employee_id }
   │                         │
   │                         ├──> vectorstore.search(prompt, employee_id)
   │                         │       │
   │                         │       └───> FAISS: retrieve top-k chunks
   │                         │
   │                         ├──> SQLAlchemy: SELECT Employee WHERE id=...
   │                         │       │
   │                         │       └───> PostgreSQL/SQLite
   │                         │              (fetch raw_text)
   │                         │
   │                         ├──> Enrich prompt with RAG chunks + raw_text
   │                         │
   │                         ├──> llm.generate(enriched_prompt)
   │                         │       │
   │                         │       └───> Ollama (qwen2.5)
   │                         │
   │<────────────────────────┤ { reply: "..." }
   │                         │
App.jsx                     │
   │ 7. Display message      │
   │    in chat UI           │
   │    (smooth scroll)      │
```

### Complete User Journey: Upload CV → CRUD Operations

```
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 1: CV UPLOAD & PROCESSING                                  │
└──────────────────────────────────────────────────────────────────┘

1. User Action: Click + button in Upload.jsx
   └─> Opens file picker dialog

2. User Action: Select CV.pdf and type question
   └─> File stored in Upload.jsx state
   └─> Question stored in prompt state

3. User Action: Press "Send" button
   └─> onSubmit handler in Upload.jsx fires
   
4. Frontend: uploadAndWait() function
   Files involved: Upload.jsx
   
   a) Discover backend via findBackendBase()
      - Try http://{hostname}:8000/health
      - Try http://127.0.0.1:8000/health
      - Try http://localhost:8000/health
      
   b) FormData upload to POST /api/upload-cv
      Files involved: main.py (FastAPI endpoint)
      
   c) Backend: storage.save_file(contents, filename)
      Files involved: services/storage.py
      Database: MongoDB GridFS or data/files/ directory
      
   d) Backend: BackgroundTasks.add_task(process_cv, ...)
      Files involved: main.py → process_cv function
      
5. Background Processing (async in process_cv)
   
   a) Fetch file: storage.get_file(file_id)
      Files involved: services/storage.py
      
   b) Extract text: extract_text_from_bytes(data)
      Files involved: services/extractor.py
      Uses: pdfplumber library
      Fallback: pytesseract OCR if no text found
      
   c) LLM Extraction: llm.generate(extraction_prompt)
      Files involved: services/llm_adapter.py
      External: Ollama server (port 11434) or CLI
      Purpose: Parse name, email, phone from resume text
      
   d) Create Employee record
      Files involved: db/models.py, db/session.py
      Database: INSERT INTO employees (name, email, phone, raw_text)
      SQLAlchemy commits to PostgreSQL or SQLite
      
   e) Chunk text and index embeddings
      Files involved: services/embeddings.py, services/vectorstore_faiss.py
      Process:
        - Split text into 500-char chunks with 100-char overlap
        - Generate embeddings using sentence-transformers
        - Store in FAISS IndexFlatIP
        - Persist to data/faiss/index.faiss + metadata.json
        
   f) Write job metadata
      Files involved: main.py
      Output: data/jobs/{job_id}.json with status, employee_id
      
6. Frontend: Job Polling
   Files involved: Upload.jsx (polling loop)
   
   - Fetch GET /api/job/{job_id} every 1 second
   - Backend reads data/jobs/{job_id}.json
   - When status="done", extract employee_id
   - Store employee_id in Upload component state
   - Display success message in App.jsx message list

┌──────────────────────────────────────────────────────────────────┐
│ PHASE 2: CHAT WITH RAG                                           │
└──────────────────────────────────────────────────────────────────┘

7. User Action: Type new question and press Send
   Files involved: Upload.jsx (handleChat function)
   
   a) POST /api/chat with { prompt, employee_id }
      Files involved: main.py (chat endpoint)
      
   b) RAG Retrieval: vectorstore.search(prompt, employee_id)
      Files involved: services/vectorstore_faiss.py
      Process:
        - Generate embedding for user prompt
        - Search FAISS index for top-k similar chunks
        - Filter by employee_id metadata
        - Return relevant text excerpts
        
   c) Fetch employee record: db.query(Employee).filter_by(id=...)
      Files involved: db/session.py, db/models.py
      Database: SELECT * FROM employees WHERE id = employee_id
      
   d) Enrich prompt:
      "Relevant resume excerpts:\n{RAG chunks}\n
       Employee record:\n{raw_text[:1000]}\n
       User prompt:\n{original prompt}"
       
   e) LLM Generation: llm.generate(enriched_prompt)
      Files involved: services/llm_adapter.py
      External: Ollama server
      
   f) Log prompt: data/prompts/chat_{timestamp}.json
      
   g) Return { reply: "..." } to frontend
   
8. Frontend: Display reply
   Files involved: App.jsx
   
   - Add user message to messages state (type: "user")
   - Add assistant reply to messages state (type: "assistant")
   - Smooth scroll with offset (scrollToBottom function)
   - Messages render with QA grouping

┌──────────────────────────────────────────────────────────────────┐
│ PHASE 3: NATURAL LANGUAGE CRUD                                   │
└──────────────────────────────────────────────────────────────────┘

9. User Action: Type NL command in NLCrud.jsx
   Example: "Update employee 5's email to john@example.com"
   Files involved: NLCrud.jsx
   
   a) POST /api/nl-command with { command: "..." }
      Files involved: main.py (nl_command endpoint)
      
   b) LLM Parsing: llm.generate(parse_prompt)
      Purpose: Convert NL to JSON action spec
      Output: { action: "update", employee_id: 5, 
                fields: { email: "john@example.com" } }
      
   c) Save proposal: data/jobs/nl_{pending_id}.json
      
   d) Return { pending_id, proposal } to frontend
   
10. User Action: Review and click "Confirm" in NLCrud.jsx
    Files involved: NLCrud.jsx
    
    a) POST /api/nl/{pending_id}/confirm
       Files involved: main.py (nl_confirm endpoint)
       
    b) Read proposal: data/jobs/nl_{pending_id}.json
       
    c) Execute DB action based on proposal.action:
       - "create": db.add(Employee(...))
       - "update": emp.field = value; db.commit()
       - "delete": db.delete(emp); db.commit()
       - "read": db.query(Employee).filter_by(id=...)
       
       Files involved: db/models.py, db/session.py
       Database: UPDATE/INSERT/DELETE on employees table
       
    d) Return result to frontend
    
    e) Frontend displays success/error message

┌──────────────────────────────────────────────────────────────────┐
│ KEY FILES BY LAYER                                               │
└──────────────────────────────────────────────────────────────────┘

Frontend Layer:
  - frontend/src/Upload.jsx: File picker, chat input, job polling
  - frontend/src/App.jsx: Message display, smooth scroll
  - frontend/src/NLCrud.jsx: Natural language CRUD interface
  - frontend/src/styles.css: Custom styling (+ button, Send button)

Backend API Layer:
  - backend/app/main.py: All API endpoints and orchestration
  - backend/app/db/models.py: SQLAlchemy Employee model
  - backend/app/db/session.py: Database connection setup

Service Layer (Adapters):
  - backend/app/services/storage.py: GridFS or filesystem storage
  - backend/app/services/extractor.py: PDF text extraction + OCR
  - backend/app/services/llm_adapter.py: Ollama HTTP/CLI wrapper
  - backend/app/services/embeddings.py: sentence-transformers wrapper
  - backend/app/services/vectorstore_faiss.py: FAISS index management

Data/Artifacts:
  - data/files/: Raw PDF storage (filesystem fallback)
  - data/jobs/{job_id}.json: Background job status
  - data/prompts/chat_{ts}.json: Chat prompt logs
  - data/faiss/: FAISS vector index + metadata
  - backend_dev.db: SQLite database (default)

External Dependencies:
  - PostgreSQL: Optional (via DATABASE_URL env var)
  - MongoDB: Optional (via MONGO_URI env var for GridFS)
  - Ollama: Required (local LLM server on port 11434)
```



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
