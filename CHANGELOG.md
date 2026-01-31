# Changelog

All notable changes to this project are recorded here with timestamps (UTC).

2026-01-31T00:00:00Z - Added structured extraction and prompt logging
- backend: `process_cv` now runs an LLM-driven extractor to parse name/email/phone from resumes and upserts them into the `employees` table.
- backend: added a small DB migration to add the `phone` column if missing.
- backend: write prompt logs for extraction under `data/jobs/{job_id}.prompt.txt` and save extracted excerpt under `data/jobs/{job_id}.extracted.txt`.
- backend: added chat prompt logging under `data/prompts/` (timestamped files).
- backend: added `GET /api/employee/{id}/raw` to fetch raw_text excerpt and length for debugging.
- frontend: show user's prompt above assistant replies and use structured message types (user/assistant/info/error).
- frontend: poll job status after upload and include `employee_id` in chat requests.
- frontend: display separators between user/assistant exchanges.

2026-01-31T01:00:00Z - OCR fallback, prompt logging, and extraction validation
- backend: `extract_text_from_bytes` now attempts OCR fallback using `pytesseract` and `pdfplumber.Page.to_image()` when initial extraction yields no text.
- backend: added pydantic-based validation for extractor JSON and a single stricter re-prompt if `name` is missing.
- backend: chat prompts are logged to `data/prompts/` as timestamped JSON files for each chat request.
- backend: job metadata updated to include extraction error when extraction fails.

2026-01-31T02:00:00Z - RAG: embeddings + FAISS
- backend: added `app/services/embeddings.py` using sentence-transformers to produce normalized embeddings.
- backend: added `app/services/vectorstore_faiss.py` which persists a FAISS index and metadata under `data/faiss/`.
- backend: `process_cv` now chunks extracted text and indexes chunks into FAISS under the employee id; job metadata records chunk counts.
- backend: `POST /api/chat` now performs retrieval-augmented generation (RAG): it fetches top-k relevant chunks for the requested `employee_id` and prepends them to the LLM prompt.

2026-01-31T03:00:00Z - CRUD-by-NL workflow and confirmation UI
- backend: added `POST /api/nl-command` to parse natural-language CRUD commands into a JSON proposal (saved as pending). The parser uses the LLM.
- backend: added `GET /api/nl/{pending_id}` and `POST /api/nl/{pending_id}/confirm` to view and apply pending proposals with confirmation.
- frontend: added `frontend/src/NLCrud.jsx` and integrated into the main app to allow parsing and confirming NL CRUD commands.
- backend: added diagnostic endpoints `GET /api/storage-status` and `GET /api/db-status` to help debug MongoDB/Postgres connectivity and storage health.

- backend: added `app/services/embeddings.py` using sentence-transformers to produce normalized embeddings.
- backend: added `app/services/vectorstore_faiss.py` which persists a FAISS index and metadata under `data/faiss/`.
- backend: `process_cv` now chunks extracted text and indexes chunks into FAISS under the employee id; job metadata records chunk counts.
- backend: `POST /api/chat` now performs retrieval-augmented generation (RAG): it fetches top-k relevant chunks for the requested `employee_id` and prepends them to the LLM prompt.



2026-01-30T23:00:00Z - Stability and adapter fixes
- backend: improved `llm_adapter` subprocess decoding to avoid UnicodeDecodeError on Windows.
- backend: added `/api/chat-debug` and `GET /api/chat` friendly handler to avoid 405 noise.
- frontend: improved error surfacing for server errors and job polling UI.

2026-01-30T22:00:00Z - Initial project scaffold
- Created FastAPI backend, LLM/storage/extractor adapters, SQLAlchemy models (Employee), and React frontend (Vite).

--
Note: timestamps are approximate and refer to local development session times. Continue appending entries for further edits.
