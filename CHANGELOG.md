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

2026-01-31T04:15:00Z - Frontend: smooth scrolling and UX polish
- frontend: added a smooth-scroll behavior for the chat pane so new messages animate into view instead of jumping. The scroll now applies a small offset (approx. 40–48px) so the newest QA pair is visually pinned above the bottom input/controls rather than hugging the edge.
- frontend: scrolling uses a short deferred scroll (60ms) to allow layout to settle (fonts/images), and falls back to manual setting if smooth scroll isn't supported.
- frontend: improved message ordering and rendering to better support QA grouping and timestamping.

2026-01-31T05:00:00Z - Frontend: UI improvements (ChatBot title, attachment preview, fixed input, centered responses)
- frontend: changed app title from "CV Chat PoC" to "ChatBot" and centered it at the top of the screen.
- frontend: PDF attachments now appear immediately as a message when uploaded (with 📎 icon and filename), instead of only showing after processing.
- frontend: fixed the input box to the bottom of the viewport with the chat area now scrollable above it.
- frontend: centered assistant response messages for better readability and visual balance.
- frontend: improved overall layout with proper scroll containment and viewport-height-based flex layout.

2026-01-31T06:00:00Z - Environment configuration system
- project: added comprehensive `.env` files for both backend and frontend with all connection configurations.
- backend: created `backend/.env` and `backend/.env.example` with settings for database (PostgreSQL/SQLite), MongoDB (GridFS), Ollama LLM, file processing, embeddings, CORS, logging, and security.
- frontend: created `frontend/.env` and `frontend/.env.example` with settings for API endpoints, UI configuration, feature flags, polling, and analytics.
- docs: added `ENV_SETUP_GUIDE.md` - comprehensive guide covering configuration reference, common scenarios, security best practices, troubleshooting, and advanced usage.
- project: all sensitive configuration now managed through environment variables instead of hard-coded values.

2026-01-31T07:00:00Z - UX improvements: input clearing, pronoun resolution, visual spacing
- frontend: input box now clears immediately when user hits Enter/Send button for better UX flow.
- frontend: added 80px bottom padding to chat area to prevent messages from hiding under the fixed input box.
- frontend: visual gap between input box and message container for cleaner layout.
- backend: enhanced LLM prompt with pronoun resolution instructions - when user refers to candidate using pronouns (he/she/they/his/her/their), the LLM now understands these refer to the resume candidate.
- backend: improved context instruction for more natural conversation about candidate resumes.

2026-01-31T08:00:00Z - Critical fix: Environment variables now loading correctly
- backend: added `load_dotenv()` call in `app/main.py` to load .env file at startup.
- backend: added `load_dotenv()` call in `app/config.py` for configuration module.
- fix: Database connections now use PostgreSQL and MongoDB as configured in .env instead of SQLite fallback.
- backend: created `diagnose_databases.py` script to test database connections and help troubleshoot storage issues.
- docs: Environment variables were configured but not being loaded - now fixed and verified working.

2026-01-31T05:00:00Z - Frontend redesign to match modern UI + backend diagnostics
- frontend: Complete UI overhaul to match modern design aesthetic:
  - Replaced file input with + icon button (hidden file input triggered by label)
  - Redesigned Send button with rounded corners, black background, and elevation shadow
  - Changed input placeholder from "Ask about the CV..." to "Ask anything"
  - Removed helper text about automatic upload
  - Enhanced chat input container with pill-shaped design, white background, and subtle shadow
  - Improved overall spacing, typography, and visual hierarchy
- frontend: Updated styles.css with modern CSS including hover states, transitions, and shadow effects
- backend: Added check_db_connection.py diagnostic script to verify:
  - Database connectivity (SQLAlchemy connection test)
  - Table existence and schema validation
  - CRUD operations (create/read/update/delete test)
  - Storage backend health (GridFS or filesystem)
  - LLM adapter connectivity (Ollama HTTP or CLI)
- docs: PROJECT_GUIDE.md now includes comprehensive architecture documentation:
  - System architecture diagram showing all components and their relationships
  - Data flow diagram: Frontend ↔ Backend ↔ Database communication
  - Complete user journey from CV upload through CRUD operations
  - File-by-file breakdown of responsibilities
  - Visual representation of how RAG, embeddings, and LLM extraction work together

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
