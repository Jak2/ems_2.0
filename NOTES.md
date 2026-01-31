CV Chat PoC — Setup & Notes
===========================

This document explains how to set up, configure, and run the CV Chat PoC locally (Windows).
It also documents key design decisions, environment variables, and how to debug storage/DB/LLM issues.

1) Requirements
---------------
- Python 3.10+ (3.11 tested in development)
- Node.js 16+ and npm (for the frontend)
- Tesseract OCR (optional but recommended for scanned PDFs) — install from releases: https://github.com/tesseract-ocr/tesseract/releases
- Ollama (or other local LLM). This project expects either the Ollama CLI on PATH or OLLAMA_API_URL pointing to Ollama's HTTP API.

2) Backend setup
----------------
- Create and activate a Python virtualenv in `backend/` and install dependencies:

  ```powershell
  cd backend
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```

- Important environment variables (set before running uvicorn):
  - `DATABASE_URL` (optional). If not set, the app uses `sqlite:///./backend_dev.db` by default. To use Postgres, set `DATABASE_URL` e.g. `postgresql://user:pass@localhost:5432/dbname`.
  - `MONGO_URI` (optional). If set and `pymongo`/`gridfs` are available, uploaded files will be stored in MongoDB GridFS. Example: `mongodb://localhost:27017`.
  - `OLLAMA_API_URL` (optional). If set, the Ollama HTTP API is used instead of the CLI. Example: `http://localhost:11434/api/generate`.

- If you installed Tesseract, ensure `tesseract.exe` is in your PATH.

3) Running backend
------------------
- Start the backend with uvicorn:

  ```powershell
  uvicorn app.main:app --reload --port 8000
  ```

- Endpoints of interest:
  - `POST /api/upload-cv` — upload a PDF file (multipart form `file`). Returns `{job_id}`.
  - `GET /api/job/{job_id}` — poll job status (returns `employee_id` when done).
  - `POST /api/chat` — {prompt, employee_id?} returns `{reply}`. If `employee_id` is supplied, RAG retrieval is performed and relevant chunks are prepended to the prompt.
  - `GET /api/employee/{id}/raw` — debug endpoint to see `raw_len` and a short excerpt of the extracted resume text.
  - `GET /api/storage-status` — reports whether GridFS is configured and runs a small save/read roundtrip.
  - `GET /api/db-status` — reports `DATABASE_URL` in use and whether a test query runs.
  - `POST /api/nl-command` — submit an NL CRUD command to parse into a JSON proposal (pending).
  - `GET /api/nl/{pending_id}` and `POST /api/nl/{pending_id}/confirm` — view and confirm proposals.

4) Frontend setup
-----------------
- From the `frontend/` folder:
  ```powershell
  npm install
  npm run dev
  ```
- The UI allows uploading CVs, chatting, and a "Natural Language CRUD" box for asking the app to update/create/read/delete employee records using NL commands. The NL flow provides a "Parse" step that creates a pending proposal and a Confirm button to apply the change.

5) LLM configuration
--------------------
- Ollama CLI: ensure `ollama` is on PATH. The adapter will prefer `OLLAMA_API_URL` if set. The typical CLI invocation is:
  ```powershell
  ollama run qwen2.5:7b-instruct "Hello from CLI"
  ```
- HTTP API: set `OLLAMA_API_URL` to the HTTP endpoint (e.g., `http://localhost:11434/api/generate`) if you prefer HTTP.

6) Troubleshooting storage/DB
-----------------------------
- If uploaded resumes do not appear in MongoDB/GridFS:
  - Verify `MONGO_URI` is set in the environment before starting uvicorn.
  - Call `GET /api/storage-status` to see if GridFS is active and a roundtrip succeeded.
  - If GridFS is not active, files are saved locally under `backend/data/files/`.

- If employee records are not in Postgres:
  - Check `DATABASE_URL` is set and reachable. If not set, the app uses SQLite (`backend_dev.db`) in the `backend/` folder.
  - Call `GET /api/db-status` to run a quick DB probe and see which URL is in use.

7) Where files and logs are stored
---------------------------------
- Job files and debug artifacts: `data/jobs/` (job json, extracted text, prompts, meta)
- FAISS index and metadata: `data/faiss/`
- Chat prompt logs: `data/prompts/`
- Local uploaded files (fallback): `backend/data/files/`

8) Security & production notes
------------------------------
- This PoC is not production hardened. Key next steps for production:
  - Add authentication & authorization for API endpoints.
  - Move background tasks to a robust queue (Celery + Redis) for long-running tasks.
  - Use a managed vector DB or sharded FAISS for scale.
  - Add validation and confirmation workflows for DB updates (the NL flow here includes a confirmation step but should be audited).

9) Support & next steps
-----------------------
- To improve accuracy: add more careful prompt engineering for extraction, add email/phone normalization, and show the user the parsed fields for manual correction before confirm.
- To support scanned PDFs: ensure Tesseract installed and consider tuning pytesseract options (PSM, language models).

*** End of NOTES.md
