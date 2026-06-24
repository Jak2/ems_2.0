# EMS 2.0 — Project Report

**Project**: Employee Management System 2.0  
**Type**: Learning Project  
**Stack**: FastAPI · React · Ollama (Local LLM) · PostgreSQL · MongoDB · FAISS  
**Date**: June 2026

---

## 1. Executive Summary

EMS 2.0 is an AI-powered Employee Management System built as a personal learning project. Unlike traditional HR tools that require manual form-filling, EMS 2.0 lets users interact entirely through a chatbot interface. Users upload a PDF or image resume, and the system automatically extracts all structured employee data — name, email, phone, skills, experience, education — using a locally-running Large Language Model (LLM). Once an employee record is created, all further interactions happen through natural language: "Show me employees who know Python", "Update John's email to john@new.com", "Delete employee 000003".

The system is deliberately privacy-first: the LLM runs locally via Ollama, meaning no resume data ever leaves the machine.

---

## 2. Motivation & Why It Was Built

### The Problem

Most Employee Management Systems are built around forms and menus. Adding a new employee means filling out 20+ fields manually. Searching requires knowing the exact filter — you can't just ask "who's our most experienced Python developer?"

### The Learning Goal

This project was built to explore a cluster of modern AI/backend concepts simultaneously:

| Learning Goal | How It Was Explored |
|---------------|---------------------|
| Local LLM integration | Ollama running `qwen2.5:7b-instruct` for structured JSON extraction |
| RAG (Retrieval-Augmented Generation) | FAISS vector store with sentence-transformer embeddings for semantic employee search |
| Multi-database architecture | PostgreSQL (structured), MongoDB GridFS (files), FAISS (vectors) working together |
| Pydantic validation in AI pipelines | Enforcing schema on LLM JSON output before writing to DB |
| NLP-based UX | Replacing all forms with a chat interface and intent classification |
| Anti-hallucination patterns | Layered guards to prevent the LLM from making up employee data |
| Async/background processing | FastAPI `BackgroundTasks` + threading for non-blocking CV processing |

The project was also an exercise in AI-assisted development — the `AI_CONSULTATION_PROMPT.md` file in the repo documents a structured consultation with an AI to review the system's robustness and identify edge cases.

---

## 3. Tech Stack

| Layer | Technology | Role |
|-------|------------|------|
| **Frontend** | React + Vite | Chat UI, file upload, polling for job status |
| **Backend** | FastAPI (Python) | REST API, background processing, intent classification |
| **LLM** | Ollama (`qwen2.5:7b-instruct`) | Resume text extraction, chat responses, CRUD parsing |
| **SQL Database** | PostgreSQL (SQLite fallback) | Structured employee records (22+ fields) |
| **File Storage** | MongoDB GridFS | Raw PDF/image files, extracted JSON documents |
| **Vector Store** | FAISS | Semantic similarity search over employee text |
| **Embeddings** | `sentence-transformers` (`all-MiniLM-L6-v2`) | Chunk embeddings for FAISS indexing |
| **PDF Extraction** | `pdfplumber` | Text extraction from PDF resumes |
| **OCR** | `pytesseract` (Tesseract) | Text extraction from image-based resumes |
| **Data Validation** | Pydantic v2 | Schema enforcement on LLM output |
| **ORM** | SQLAlchemy | Database sessions, models, migrations |

### Why Local LLM?

The choice to use Ollama instead of a cloud API (OpenAI, Anthropic) was deliberate:
- **Privacy** — resume data never leaves the machine
- **No API costs** — unlimited extraction during development
- **Learning** — understanding LLM inference parameters directly (temperature, context window, seeds)

The trade-off: response times of 5–30 seconds per inference on consumer hardware.

---

## 4. System Architecture & Data Flows

### 4.1 CV Upload Flow

When a user uploads a PDF or image resume, processing happens in a background thread so the frontend gets an immediate response:

```
User selects PDF → React Upload.jsx → POST /api/upload-cv
                                              │
                        ┌─────────────────────┴─────────────────────┐
                        ▼                                           ▼
                MongoDB GridFS                            Background Thread
                (stores raw file)                                   │
                                                         pdfplumber extracts text
                                                         (pytesseract OCR fallback)
                                                                    │
                                                         Resume validation (score ≥ 40)
                                                                    │
                                                         Ollama LLM extracts JSON
                                                                    │
                                                         Pydantic validates output
                                                                    │
                                                         Duplicate detection check
                                                                    │
                                                         PostgreSQL stores employee
                                                                    │
                                                         FAISS indexes text chunks
                                                                    │
                                                         Job status → "done"
                        ▼                                           │
                Frontend polls GET /api/job/{id} ◄──────────────────┘
                        │
                Shows employee_id to user
```

**Step-by-step:**

1. Frontend sends the PDF as a `multipart/form-data` request.
2. Backend saves the raw file to MongoDB GridFS and generates a `job_id` (UUID).
3. A daemon thread runs `process_cv()` in the background.
4. The API immediately returns `{"job_id": "...", "status": "queued"}` — the frontend starts polling.
5. Background thread: extracts text with `pdfplumber`, falls back to `pytesseract` OCR for images.
6. Text is validated as a resume (scoring system — see Section 6).
7. Ollama LLM receives a structured extraction prompt and returns JSON.
8. JSON is parsed with multiple fallback strategies, then validated with Pydantic.
9. Employee record is written to PostgreSQL; text chunks are embedded and indexed in FAISS.
10. Job status file is written to `data/jobs/{job_id}.json` with `"status": "done"`.
11. Frontend's polling loop reads the done status and shows the new employee ID.

### 4.2 Chat / Query Flow

```
User types question → POST /api/chat
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
      Employee ID provided?          No employee_id?
              │                               │
      Query PostgreSQL              Name search + FAISS semantic search
              │                               │
              └───────────────┬───────────────┘
                              ▼
               Intent classification (CRUD / search / greeting / etc.)
                              │
               Anti-hallucination guard check
                              │
               Build context from employee data
                              │
               Send context + history + prompt to Ollama
                              │
               Return {reply, session_id, employee_id}
```

Every response — including greetings, search results, and error messages — routes through the LLM. There are no hardcoded bot responses. This ensures natural, contextually consistent answers.

### 4.3 CRUD Operations via Natural Language

| Operation | Example User Input | Backend Action |
|-----------|--------------------|----------------|
| **Create** | Upload CV or `create <resume text>` | LLM extraction → `db.add(Employee(...))` |
| **Read** | "Show all employees" / "What's John's email?" | Query PostgreSQL + LLM formats response |
| **Update** | "Update John's email to john@new.com" | LLM parses intent → `setattr(employee, field, value)` |
| **Delete** | "Delete employee 000003" | `db.delete(employee)` + remove from FAISS |

### 4.4 Service Communication Map

```
┌──────────────────────────────────────────────────┐
│                   FRONTEND (React)               │
│   App.jsx (state) ←→ Upload.jsx (chat + upload) │
│             fetch() calls to backend             │
└──────────────────────────┬───────────────────────┘
                           │ HTTP
┌──────────────────────────▼───────────────────────┐
│              BACKEND (FastAPI)                   │
│  /api/upload-cv  → MongoDB + Thread(process_cv)  │
│  /api/job/{id}   → Read job status file          │
│  /api/chat       → PostgreSQL + Ollama           │
│  /api/employees  → PostgreSQL CRUD               │
└───────────┬─────────────┬─────────────┬──────────┘
            ▼             ▼             ▼
  ┌──────────────┐ ┌───────────────┐ ┌─────────────┐
  │   MongoDB    │ │  PostgreSQL   │ │   Ollama    │
  │  (GridFS)   │ │ (SQLAlchemy)  │ │  (Local LLM)│
  │ Raw PDFs    │ │ Employee rows │ │ qwen2.5:7b  │
  └──────────────┘ └───────┬───────┘ └─────────────┘
                           ▼
                  ┌────────────────┐
                  │     FAISS      │
                  │ (Vector Store) │
                  │ Text embeddings│
                  └────────────────┘
```

### 4.5 Data Pipeline Summary

| Stage | Input | Processing | Output |
|-------|-------|------------|--------|
| Upload | PDF/image | GridFS chunking | `file_id` → MongoDB |
| Extract | File bytes | pdfplumber / OCR | Raw text → Memory |
| Validate | Raw text | Resume scoring | Accept/reject |
| Parse | Raw text | Ollama LLM | JSON structure |
| Enforce | JSON | Pydantic model | `Employee` object |
| Store | Employee | SQLAlchemy ORM | DB record → PostgreSQL |
| Index | Employee text | Sentence embeddings | Vectors → FAISS |
| Query | User prompt | Context + LLM | Response → Frontend |

---

## 5. Key Features

### 5.1 Resume Upload & Auto-Extraction

Users upload a PDF or image (JPG, PNG). The system:
- Detects file type and routes to the correct extractor
- Validates the document is actually a resume (not a random PDF)
- Sends extracted text to Ollama with a detailed extraction prompt
- Extracts 22+ fields: name, email, phone, LinkedIn URL, department, position, summary, work experience (array), education (array), technical skills (array), languages, hobbies, co-curricular activities
- Validates output with Pydantic, retries if the name is missing
- Optionally pasting raw resume text into chat also works: `create <resume text>`

### 5.2 Natural Language CRUD

The chatbot understands commands like:
- `"Show me all employees"` → lists all records
- `"Find employees skilled in AWS"` → semantic FAISS search
- `"What is John's email?"` → fetches from PostgreSQL
- `"Update John's phone to 555-1234"` → LLM parses field + value → DB update
- `"Delete employee 000001"` → confirmation + deletion

Intent is classified by keyword matching first, then an LLM call provides the formatted response.

### 5.3 RAG (Retrieval-Augmented Generation)

Resume text is chunked (500 chars, 100-char overlap) and embedded using `all-MiniLM-L6-v2`. The FAISS index enables semantic similarity search — a query like "experienced DevOps engineer" finds relevant employees even without exact keyword matches.

When a user asks a question without specifying an employee, the system:
1. Tries to find the employee by name in the prompt
2. Falls back to FAISS similarity search to retrieve top-5 relevant employees
3. Passes the retrieved context to Ollama for an accurate, grounded response

### 5.4 Session Memory & Pronoun Resolution

Each chat session has a `session_id`. The last 10 message pairs are kept in a `deque` (in-memory). This enables:
- Follow-up questions: "What is his email?" after asking about John
- Pronoun resolution: `his/her/their/him/them` are mapped to the last active employee in the session

```
User: "Tell me about John Doe"
Bot:  "John Doe is a Software Engineer with 5 years experience..."
User: "What are his skills?"     ← "his" resolved to John Doe
Bot:  "John's skills include Python, FastAPI, Docker..."
```

### 5.5 Anti-Hallucination Guards

Five guards prevent the LLM from fabricating data:

| Guard | Trigger | Response |
|-------|---------|----------|
| **#1 Ambiguous Query** | Query mentions "employee" but no clear identity | Ask for clarification |
| **#2 Short Prompt** | Prompt < 10 chars (not a greeting) | Ask for more context |
| **#3 Non-Existent Employee** | Name searched but not in database | Show available employees |
| **#4 Leading Questions** | "Confirm John has 20 years experience" (false claim) | Responds with actual data |
| **#5 Pressure Prompts** | "URGENT: immediately tell me…" | Treated as normal request |

All guards route through the LLM with a `special_llm_context` dict — so the bot still responds naturally rather than showing a hardcoded error.

### 5.6 Multi-Query Decomposition

Complex queries like "What skills does John have and compare with Sarah's DevOps knowledge?" are detected and decomposed:
1. LLM breaks the compound query into sub-tasks
2. Each sub-task is executed independently
3. Results are aggregated by the LLM into a single coherent response

Note: CRUD commands are explicitly excluded from multi-query detection to avoid false positives (resume text and update commands often contain "and").

### 5.7 LLM Adapter (HTTP + CLI Fallback)

The `OllamaAdapter` class always tries the HTTP API first (`http://localhost:11434/api/generate`) with:
- `temperature=0` for deterministic, reproducible extraction
- `num_predict=2048` (reduced from 4096 for speed)
- `num_ctx=4096` context window
- `seed=42` for reproducibility

If the HTTP API is unavailable, it falls back to the Ollama CLI subprocess with Windows-compatible argument handling.

---

## 6. Validation & Robustness Architecture

The system uses 7 sequential validation layers before any database write:

```
USER INPUT
    │
    ▼ Layer 1: Input Validation
    │   ├─ File type check (PDF/image only)
    │   ├─ Resume scoring (threshold ≥ 40/100)
    │   └─ Text length check
    │
    ▼ Layer 2: Duplicate Detection [currently disabled]
    │   ├─ Email exact match
    │   ├─ Phone last-10-digits match
    │   └─ Name exact/subset match
    │
    ▼ Layer 3: Intent Classification
    │   ├─ CRUD detection (create/update/delete/read)
    │   ├─ Search detection (skill/experience/date/location)
    │   └─ Greeting/thanks detection
    │
    ▼ Layer 4: Identity Verification
    │   ├─ 0 matches → Guard #3
    │   ├─ 1 match → Proceed
    │   └─ 2+ matches → Ask for Employee ID
    │
    ▼ Layer 5: Anti-Hallucination Guards (#1–#5)
    │
    ▼ Layer 6: LLM Processing
    │   ├─ JSON extraction & parsing
    │   ├─ Pydantic validation
    │   └─ Field sanitization
    │
    ▼ Layer 7: Database Operations
        ├─ PostgreSQL (structured data)
        ├─ FAISS (vector embeddings)
        └─ MongoDB GridFS (files)
```

### Resume Validation Scoring

The resume validator scores uploaded documents before any LLM processing:

| Component | Max Points | Criteria |
|-----------|-----------|---------|
| Section headers | 35 | experience, education, skills, objective, summary |
| Professional keywords | 25 | managed, developed, implemented, led, etc. |
| Contact information | 25 | Email pattern + phone pattern |
| Date patterns | 15 | Year formats (19xx/20xx), month names |
| **Threshold** | **40** | Minimum to accept as a valid resume |

Documents scoring below 40 are rejected before any LLM call is made, saving inference time and preventing garbage data.

---

## 7. Challenges & Solutions

### 7.1 Major Bugs Fixed

**BUG-001 — CRUD Operations Not Routing (Critical)**

CRUD commands like "Update John's email to x@y.com" were silently failing. Three root causes:

1. The multi-query detector was intercepting CRUD commands (resume text contains "and" which triggered compound query detection). Fix: explicitly skip multi-query detection for all CRUD starters.
2. Employee name lookup in the prompt only ran for `delete/remove`, not for `update/create/modify`. Fix: extended to all CRUD verbs.
3. `create` commands don't reference existing employees, so the employee-context check always failed for them. Fix: auto-set context for create/add commands.

**BUG-002 — Resume Validation Rejecting Valid Resumes (High)**

The email/phone regex used `^...$` anchors, which only match the full string — so they never matched patterns embedded in resume text. Fix: removed anchors, used `re.search()` instead of `re.match()`.

**BUG-003 — Image Uploads Failing Resume Validation (Medium)**

OCR output from images is messy and often lacks clear structure, so the validation score fell below 40. Fix: applied a more lenient threshold for image files (15% confidence with ≥100 chars of text is accepted).

**BUG-004 — AttributeError on `validation_result.warnings` (Medium)**

Server crash on upload due to wrong attribute name. Fix: corrected to `validation_result.validation_warnings`.

**BUG-005 — "Show All Employees" Truncated at 5 Records (Low)**

A `[:8000]` character limit cut off the employee list data before it reached the LLM. Fix: removed the limit for list queries.

### 7.2 Key Design Decisions

**All responses route through the LLM**

Initially, greetings, search results, and error messages returned hardcoded strings. This made responses feel robotic. The architecture was refactored so all user inputs are processed by the LLM via a `special_llm_context` dict, enabling natural, contextually appropriate responses for every interaction type.

**Background threads instead of `BackgroundTasks`**

FastAPI's `BackgroundTasks` was replaced with explicit `threading.Thread(daemon=True)` for CV processing. Reason: `BackgroundTasks` with blocking calls (subprocess, HTTP requests to Ollama) caused subtle issues on some setups; explicit threads are more predictable.

**Job status via flat files**

Instead of polling a database table for job status, each job writes to a JSON file at `data/jobs/{job_id}.json`. This avoids DB connection overhead during polling and is easy to debug by reading the file directly.

**6-digit zero-padded employee IDs**

Employee IDs like `000001`, `000047` are auto-generated from `MAX(employee_id) + 1` with a fallback to count-based or timestamp-based generation. Ensures human-readable IDs that sort correctly.

**GPU optimization**

The `qwen2.5:14b` model (18GB) was too large for the RTX 3060 (6GB VRAM), causing CPU fallback and 30+ second responses. Switched to `qwen2.5:7b-instruct` quantized, achieving ~100% GPU utilization and 2–5 second response times.

---

## 8. Employee Data Model

The `Employee` SQLAlchemy model stores 22+ fields:

```
id             — Internal auto-increment primary key
employee_id    — Human-readable 6-digit ID (e.g., 000001)

Basic Info:
  name, email, phone

Professional:
  department, position, linkedin_url

Career Summary:
  summary

Structured Arrays (stored as text/JSON):
  work_experience       — List of {company, role, duration, description}
  education             — List of {institution, degree, year, grade}
  technical_skills      — List of skill strings
  languages             — List of languages known
  hobbies               — List of hobbies
  cocurricular_activities — List of activities

Raw Storage:
  raw_text              — Original extracted text from PDF
  extracted_text        — Cleaned/processed text (also used for FAISS indexing)
```

---

## 9. Project Structure

```
ems_2.0/
├── backend/
│   └── app/
│       ├── main.py                 # All API endpoints + core logic (4400+ lines)
│       ├── config.py
│       ├── db/
│       │   ├── models.py           # Employee SQLAlchemy model
│       │   └── session.py          # DB connection + SessionLocal
│       └── services/
│           ├── llm_adapter.py      # Ollama HTTP + CLI wrapper
│           ├── extractor.py        # PDF/image text extraction
│           ├── extraction_utils.py # LLM prompts, JSON parsing, validation
│           ├── validators.py       # Resume scoring, Pydantic enforcement
│           ├── search_utils.py     # Skill synonyms, experience calc, FAISS helpers
│           ├── embeddings.py       # sentence-transformers wrapper
│           ├── vectorstore_faiss.py # FAISS add/search/remove
│           └── storage.py          # MongoDB GridFS + local filesystem
├── frontend/
│   └── src/
│       ├── App.jsx                 # Chat UI, message list, scroll
│       ├── Upload.jsx              # File upload + chat input + polling
│       └── NLCrud.jsx              # Natural language CRUD interface
├── data/
│   ├── jobs/                       # Job status JSON files
│   ├── prompts/                    # Logged LLM prompt/response pairs
│   └── faiss/                      # FAISS index files (index.faiss, meta.json)
├── docs/
│   ├── ARCHITECTURE_CHECKS.md      # 7-layer validation + bug changelog
│   ├── ROBUSTNESS_CHANGES.md       # Specific improvements made
│   └── AI_CONSULTATION_PROMPT.md   # AI-assisted robustness review
├── README.md                       # Quick start + full flow diagrams
├── PROJECT_SUMMARY.md              # Interview-ready summary
├── start.ps1 / start.bat           # One-click startup scripts
└── stop.ps1
```

---

## 10. Known Limitations & Future Improvements

### Current Limitations

| Limitation | Details |
|-----------|---------|
| **Duplicate detection disabled** | `check_duplicate_employee()` exists but always returns `is_duplicate: False`. Was disabled to avoid false positives during development. |
| **No authentication** | Any user can read, update, or delete any employee. JWT auth is a planned improvement. |
| **No rate limiting** | LLM calls are slow; concurrent uploads could overload Ollama. |
| **In-memory session store** | Conversation history lives in a Python `dict`. Server restart clears all sessions. Redis recommended for production. |
| **Single-node FAISS** | FAISS runs in-memory/local file. Not suitable for distributed deployment. |
| **Tesseract dependency** | OCR fallback requires Tesseract binary installed separately. |
| **No streaming** | LLM responses are buffered before sending to frontend. Users wait 5–30 seconds with no partial output. |

### Planned Improvements

1. **Re-enable duplicate detection** — tune name matching to reduce false positives
2. **JWT authentication** — role-based access (admin vs. viewer)
3. **Redis for session memory** — persist conversations across server restarts
4. **Streaming responses** — send LLM output token-by-token for better UX
5. **Skills normalization** — map "JS" → "JavaScript", "k8s" → "Kubernetes"
6. **IVF FAISS indexing** — for scale beyond ~10,000 employees
7. **Retry with exponential backoff** — for Ollama failures under load
8. **Transaction consistency** — rollback PostgreSQL if FAISS indexing fails

---

## 11. What Was Learned

This project covered a significant amount of ground for a single learning project:

- **Local LLM integration is practical** — Ollama makes it straightforward to run capable models (7B parameters) on consumer hardware, with HTTP API control over temperature and context.

- **LLM output is unreliable without guardrails** — Raw LLM JSON fails to parse in ~10–20% of cases. Multi-strategy parsing (direct JSON parse → regex extraction → regex cleanup → key-value fallback) was essential.

- **Intent classification at scale is complex** — The chat handler grew to 4400+ lines because every query type (skill search, date range, compound, temporal, null field, seniority, location...) needs its own detection and handling path.

- **Multi-database consistency is hard** — When PostgreSQL writes succeed but FAISS indexing fails (or vice versa), the system ends up in an inconsistent state. This is a genuine distributed systems problem, not a simple bug.

- **All-routes-through-LLM is a good pattern** — Once hardcoded responses were removed and all interactions funneled through Ollama with structured context, the conversational quality improved dramatically.

- **AI-assisted development accelerates iteration** — Using an AI to do robustness review (`AI_CONSULTATION_PROMPT.md`) produced a comprehensive list of edge cases (encoding issues, overlapping job dates, prompt injection, bulk operation safety) that would have taken much longer to discover organically.

---

*Report generated: June 2026*  
*Project location: `my_learning_projects/ems_2.0/`*
