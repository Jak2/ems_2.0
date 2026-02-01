# Employee Management System (EMS) 2.0

An AI-powered Employee Management System that accepts CV/resume uploads, extracts structured data using a local LLM (Ollama), stores information in dual databases (MongoDB + PostgreSQL), and provides a conversational interface for CRUD operations.

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm start

# Ollama (required)
ollama serve
ollama pull qwen2.5:7b-instruct
```

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Pydantic
- **Frontend**: React, Vite
- **LLM**: Ollama (qwen2.5:7b-instruct)
- **Databases**: PostgreSQL, MongoDB (GridFS)
- **PDF Processing**: pdfplumber, pytesseract (OCR)

## Project Structure

```
ems_2.0/
├── backend/           # FastAPI backend
│   └── app/
│       ├── main.py    # API endpoints
│       ├── db/        # Database models
│       └── services/  # Business logic
├── frontend/          # React frontend
│   └── src/
│       ├── App.jsx
│       └── Upload.jsx
├── data/              # Runtime data
│   ├── jobs/          # Job status files
│   ├── extracted/     # Extracted JSON
│   └── faiss/         # Vector store
└── markdown/          # Documentation
```

---

## Complete Project Flow

### 1. CV Upload Flow
Complete diagram and step-by-step explanation with code references


```
User selects PDF → Frontend Upload.jsx → POST /api/upload-cv → Backend main.py
                                                ↓
                        ┌───────────────────────┴───────────────────────┐
                        ↓                                               ↓
                MongoDB GridFS                                   Background Thread
                (stores raw PDF)                                        ↓
                                                              pdfplumber extracts text
                                                                        ↓
                                                              Ollama LLM processes text
                                                                        ↓
                                                              Pydantic validates output
                                                                        ↓
                                                              PostgreSQL stores employee
                                                                        ↓
                                                              FAISS indexes for RAG
                                                                        ↓
                                                              Job status → "done"
                        ↓                                               ↓
                Frontend polls GET /api/job/{id} ←──────────────────────┘
                        ↓
                Shows employee_id to user
```

**Step-by-step:**

1. **Frontend (Upload.jsx:132-230)**: User selects PDF, clicks Send
2. **Upload Request**: `POST /api/upload-cv` with FormData
3. **Backend (main.py:186-234)**:
   - Generates `job_id` (UUID)
   - Stores PDF in MongoDB GridFS
   - Spawns background thread `process_cv()`
   - Returns `job_id` immediately
4. **Background Processing (main.py:237-400)**:
   - `pdfplumber` extracts text from PDF
   - Falls back to `pytesseract` OCR if needed
   - Sends text to Ollama LLM with extraction prompt
   - Parses JSON response into Pydantic model
   - Creates `Employee` record in PostgreSQL
   - Indexes employee data in FAISS vector store
   - Updates job status file to "done"
5. **Frontend Polling (Upload.jsx:66-100)**: Polls `/api/job/{id}` every second until done

---

### 2. Chat/Query Flow
How user questions are processed and answered
```
User types question → Frontend Upload.jsx → POST /api/chat → Backend main.py
                                                   ↓
                                    ┌──────────────┴──────────────┐
                                    ↓                             ↓
                            employee_id provided?          No employee_id?
                                    ↓                             ↓
                            Query PostgreSQL              Search by name in prompt
                            for that employee             or use RAG/FAISS
                                    ↓                             ↓
                                    └──────────────┬──────────────┘
                                                   ↓
                                    Build context from employee data
                                                   ↓
                                    Send prompt + context to Ollama
                                                   ↓
                                    Return LLM response to frontend
```

**Step-by-step:**

1. **Frontend (Upload.jsx:163-219)**: User types question, clicks Send
2. **Chat Request**: `POST /api/chat` with `{prompt, employee_id, session_id}`
3. **Backend (main.py:403-586)**:
   - If `employee_id` provided: fetches employee from PostgreSQL
   - If no `employee_id`: searches by name in prompt or uses FAISS similarity search
   - Builds context string from employee data
   - Sends `system_prompt + context + user_prompt` to Ollama
   - Returns `{reply, session_id, employee_id}`
4. **Frontend**: Displays assistant response in chat

---

### 3. CRUD Operations Flow
Table showing Create, Read, Update, Delete triggers and actions
| Operation | Trigger | Backend Action |
|-----------|---------|----------------|
| **Create** | Upload CV | `db.add(Employee(...))` after LLM extraction |
| **Read** | Chat query | `db.query(Employee).filter_by(employee_id=...)` |
| **Update** | Chat "update X to Y" | LLM parses intent → `setattr(employee, field, value)` |
| **Delete** | Chat "delete employee" | `db.delete(employee)` + remove from FAISS |

---

### 4. Service Communication Map
Visual diagram of Frontend → Backend → Databases/LLM
```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                  │
│  Upload.jsx ←→ App.jsx (state management)                          │
│       ↓                                                             │
│  fetch() calls to backend                                          │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ HTTP
┌─────────────────────────────────────────────────────────────────────┐
│                           BACKEND (FastAPI)                         │
│  main.py                                                            │
│    ├── /api/upload-cv  → MongoDB + Thread(process_cv)              │
│    ├── /api/job/{id}   → Read job status file                      │
│    ├── /api/chat       → PostgreSQL + Ollama                       │
│    └── /api/employees  → PostgreSQL CRUD                           │
└─────────────────────────────────────────────────────────────────────┘
         ↓                    ↓                    ↓
┌────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│   MongoDB      │  │   PostgreSQL    │  │      Ollama         │
│   (GridFS)     │  │   (SQLAlchemy)  │  │   (Local LLM)       │
│                │  │                 │  │                     │
│ - Raw PDFs     │  │ - employees     │  │ - qwen2.5:7b        │
│ - File chunks  │  │ - structured    │  │ - Text extraction   │
│                │  │   employee data │  │ - Chat responses    │
└────────────────┘  └─────────────────┘  └─────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │     FAISS       │
                    │  (Vector Store) │
                    │                 │
                    │ - Embeddings    │
                    │ - RAG search    │
                    └─────────────────┘
```

---

### 5. Data Flow Summary
Table showing each processing stage from upload to query
| Stage | Input | Processing | Output | Storage |
|-------|-------|------------|--------|---------|
| Upload | PDF file | GridFS chunking | file_id | MongoDB |
| Extract | PDF bytes | pdfplumber/OCR | Raw text | Memory |
| Parse | Raw text | Ollama LLM | JSON structure | Memory |
| Validate | JSON | Pydantic model | Employee object | Memory |
| Store | Employee | SQLAlchemy ORM | DB record | PostgreSQL |
| Index | Employee text | Sentence embeddings | Vectors | FAISS |
| Query | User prompt | Context + LLM | Response | Memory |

---

### 6. Where Does LLM Get Information?
Explains the 4 sources (PostgreSQL, FAISS, Session Memory, LLM Knowledge)
The LLM gets information from **multiple sources** depending on the query:

1. **PostgreSQL Database** (Primary Source)
   - All structured employee data is fetched via SQLAlchemy
   - Fields: name, email, phone, skills, education, experience, etc.

2. **FAISS Vector Store** (RAG Search)
   - When no specific employee is identified, semantic search finds relevant employees
   - Uses sentence-transformers for embedding similarity

3. **Conversation Memory** (Session Context)
   - `session_id` tracks conversation history
   - Previous Q&A pairs are included in the prompt for context

4. **LLM's Own Knowledge** (General Responses)
   - For questions not about specific employees
   - General HR/resume advice, formatting help, etc.

---


### 3. Project Requirements Coverage Analysis

Based on the `PROJECT_GUIDE.md`, here's the status of all **POC A** requirements:

#### FULLY IMPLEMENTED (Done)

| Feature | Status | Details |
| --- | --- | --- |
| **PDF Upload Endpoint** | Done | `POST /api/upload-cv` accepts PDF, returns `job_id` |
| **PDF Storage** | Done | GridFS (MongoDB) + local filesystem fallback |
| **PDF Text Extraction** | Done | `pdfplumber` with `pytesseract` OCR fallback |
| **LLM Adapter** | Done | Ollama HTTP API + CLI fallback |
| **LLM Structured Extraction** | Done | Pydantic validation for name, email, skills, etc. |
| **SQLAlchemy Models** | Done | Employee model with PostgreSQL/SQLite |
| **Background Processing** | Done | Threading for CV processing (`BackgroundTasks`) |
| **Job Polling** | Done | `GET /api/job/{id}` with status files |
| **Chat Endpoint** | Done | `POST /api/chat` with employee context |
| **RAG/FAISS** | Done | Vector indexing and retrieval implemented |
| **Embeddings** | Done | `sentence-transformers` for chunk embeddings |
| **Frontend Upload+Chat** | Done | React components with merged flow |
| **Session Memory** | Done | `session_id` for conversation continuity |
| **NL CRUD** | Done | Natural language command parsing |
| **Prompt Logging** | Done | Logs under `data/jobs/` and `data/prompts/` |
| **Diagnostic Endpoints** | Done | `/api/storage-status`, `/api/db-status` |

---

#### PARTIALLY IMPLEMENTED

| Feature | Status | Missing |
| --- | --- | --- |
| **OCR Fallback** | Partial | Works but requires Tesseract binary installed |
| **NL CRUD UI** | Partial | Basic UI exists, needs polish |
| **Tailwind Migration** | Partial | Core styles done, some legacy CSS remains |
| **Multiple Resume Upload** | Done (Fixed) | Was blocking, now works |

---

### Summary

| Category | Done | Partial | Pending |
| --- | --- | --- | --- |
| **Core Features** | 16 | 2 | 0 |
| **Production Hardening** | 0 | 0 | 5 |
| **Testing** | 0 | 0 | 2 |
| **DevOps** | 0 | 0 | 1 |
| **Total** | **16** | **2** | **8** |

---



*Last updated: February 1, 2026*
