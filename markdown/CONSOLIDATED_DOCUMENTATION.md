# EMS 2.0 - Consolidated Documentation

A comprehensive reference guide combining all project documentation into a single source of truth.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Setup & Configuration](#4-setup--configuration)
5. [Key Features](#5-key-features)
6. [LLM Integration](#6-llm-integration)
7. [Database Design](#7-database-design)
8. [API Endpoints](#8-api-endpoints)
9. [Frontend Implementation](#9-frontend-implementation)
10. [Development Report](#10-development-report)
11. [Testing Guide](#11-testing-guide)
12. [Troubleshooting](#12-troubleshooting)
13. [Interview Preparation](#13-interview-preparation)
14. [Future Improvements](#14-future-improvements)

---

## 1. Project Overview

### What is EMS 2.0?

An AI-powered Employee Management System that:
- Accepts CV/resume uploads (PDF)
- Extracts structured data using a local LLM (Ollama)
- Stores information in dual databases (MongoDB + PostgreSQL)
- Provides a conversational chat interface for CRUD operations
- Uses RAG (Retrieval-Augmented Generation) for intelligent Q&A

### Key Capabilities

- **PDF Processing**: pdfplumber extraction + pytesseract OCR fallback
- **LLM Extraction**: Structured JSON extraction from unstructured resume text
- **Dual Storage**: PostgreSQL for structured data, MongoDB GridFS for raw PDFs
- **RAG Search**: FAISS vector store with sentence-transformers embeddings
- **Natural Language CRUD**: Create, Read, Update, Delete via conversational chat
- **Anti-Hallucination**: 6-layer guard system to prevent fabricated responses

---

## 2. Architecture

### System Architecture Diagram

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
│  │              │ │+Tesseract│ │ HTTP or CLI  │ │            │ │
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

### Directory Structure

```
ems_2.0/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application with all API endpoints
│   │   ├── config.py            # Configuration loader and validator
│   │   ├── db/
│   │   │   ├── models.py        # SQLAlchemy ORM models (Employee)
│   │   │   └── session.py       # Database session and engine setup
│   │   └── services/
│   │       ├── llm_adapter.py   # Ollama LLM integration (HTTP + CLI)
│   │       ├── embeddings.py    # Sentence-transformers wrapper
│   │       ├── vectorstore_faiss.py  # FAISS vector store for RAG
│   │       ├── storage.py       # GridFS/local file storage adapter
│   │       └── extractor.py     # PDF text extraction (pdfplumber + OCR)
│   ├── scripts/
│   │   ├── check_db_connection.py
│   │   └── diagnose_databases.py
│   ├── data/
│   │   ├── files/               # Local file storage (fallback)
│   │   ├── jobs/                # Job status tracking (JSON files)
│   │   ├── prompts/             # Prompt logging for debugging
│   │   └── faiss/               # FAISS vector index storage
│   ├── .env                     # Environment configuration
│   ├── .env.example             # Configuration template
│   └── requirements.txt         # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main app component
│   │   ├── Upload.jsx           # File upload and chat input
│   │   ├── NLCrud.jsx           # NL CRUD component
│   │   └── styles.css           # Styling
│   ├── .env
│   └── package.json
└── markdown/                    # Documentation
```

### Data Flow

1. **CV Upload**: User uploads PDF → Stored in GridFS/filesystem → Background processing starts
2. **Processing**: PDF text extraction → LLM structured extraction → PostgreSQL storage → FAISS indexing
3. **Chat**: User query → CRUD detection → RAG retrieval → LLM generation → Response

---

## 3. Technology Stack

### Backend

| Component | Library | Purpose |
|-----------|---------|---------|
| Web Framework | FastAPI | Async API with automatic OpenAPI docs |
| ORM | SQLAlchemy | Database abstraction |
| Validation | Pydantic | Request/response validation, LLM output validation |
| PDF Extraction | pdfplumber | Text extraction from PDFs |
| OCR | pytesseract | Fallback for scanned PDFs |
| LLM | Ollama | Local LLM inference (qwen2.5:7b-instruct) |
| Embeddings | sentence-transformers | Text embeddings (all-MiniLM-L6-v2) |
| Vector Store | FAISS | Semantic search index |
| MongoDB Driver | pymongo | GridFS file storage |

### Frontend

| Component | Library | Purpose |
|-----------|---------|---------|
| UI Framework | React | Component-based UI |
| Build Tool | Vite | Fast development server |
| Markdown | react-markdown | Render LLM markdown responses |
| State | useState/useRef | Local state management |

---

## 4. Setup & Configuration

### Prerequisites

- Python 3.10+
- Node.js 16+
- Ollama with `qwen2.5:7b-instruct` model
- PostgreSQL (optional, SQLite fallback)
- MongoDB (optional, filesystem fallback)
- Tesseract OCR (optional, for scanned PDFs)

### Quick Start

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Environment Variables

#### Backend (.env)

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/ems
# Or use SQLite: DATABASE_URL=sqlite:///./backend_dev.db

# MongoDB (optional)
MONGO_URI=mongodb://localhost:27017
MONGO_DB=cv_repo

# Ollama LLM
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_API_URL=http://localhost:11434/api/generate

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Embeddings & RAG
EMBEDDING_MODEL=all-MiniLM-L6-v2
RAG_TOP_K=5
CHUNK_SIZE=500
CHUNK_OVERLAP=100

# Limits
MAX_UPLOAD_SIZE_MB=10
```

#### Frontend (.env)

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=ChatBot
VITE_DEBUG=true
```

---

## 5. Key Features

### 5.1 CV Upload & Processing

- PDF upload via multipart form
- Background processing with job tracking
- Text extraction with OCR fallback
- LLM-driven structured extraction (name, email, phone, department, position, skills, education, etc.)
- Auto-generated employee_id (6-digit format: 000001)

### 5.2 Comprehensive Field Extraction

Extracted fields include:
- **Basic**: name, email, phone, employee_id
- **Professional**: department, position, work_experience
- **Education**: education (array)
- **Skills**: technical_skills, soft_skills, languages
- **Online**: linkedin_url, portfolio_url, github_url
- **Additional**: certifications, achievements, hobbies, address

### 5.3 Conversation Memory

- Session-based context retention (last 10 messages)
- Pronoun resolution ("What is his email?" resolves to current context employee)
- Sliding window to prevent context overflow

### 5.4 Natural Language CRUD

Supported operations via chat:
- **Create**: "Create employee John in IT department"
- **Read**: "Show me John's details" / "What is Sarah's email?"
- **Update**: "Update John's department to HR" / "Change his email to new@test.com"
- **Delete**: "Delete employee John"
- **List**: "Show all employees" / "List everyone with their emails"

### 5.5 Anti-Hallucination System

6-layer protection:
1. **Ambiguous Query Detection**: Asks for clarification when employee unspecified
2. **Short Prompt Guards**: Requests clarification for vague queries
3. **Non-Existent Employee Detection**: Returns "not found" instead of fabricating
4. **Leading Question Detection**: Doesn't confirm false premises
5. **Pressure/Urgency Detection**: Doesn't bypass verification under pressure
6. **No Context Guard**: Requires employee context before answering

### 5.6 UI Features

- Modern chat interface with + button for file selection
- File preview before sending
- Markdown rendering for responses
- Response time display
- Auto-scroll to latest messages
- Stop button during processing

---

## 6. LLM Integration

### 3-Stage Pipeline

**Stage 1: Structured Extraction**
```
PDF Upload → Text Extraction (pdfplumber/OCR) → LLM JSON Extraction → PostgreSQL
```

**Stage 2: RAG Indexing**
```
Raw Text → Chunking (500 chars, 100 overlap) → Embeddings (384-dim) → FAISS Index
```

**Stage 3: Question Answering**
```
User Query → Semantic Search → Context Enrichment → LLM Generation → Response
```

### Prompt Engineering

```python
extraction_prompt = """
Extract ALL information from the resume into JSON format.

CRITICAL RULES:
1. Return ONLY valid JSON - no explanations
2. Use null for missing fields
3. Do NOT guess or infer - only extract what's explicitly stated
4. For arrays, use proper JSON arrays

Required JSON structure:
{
  "name": "Full name",
  "email": "email@example.com",
  "phone": "phone number",
  "department": "department",
  "position": "job title",
  "technical_skills": ["skill1", "skill2"],
  "education": ["degree info"],
  "work_experience": ["work info"]
}
"""
```

### Hallucination Prevention in Prompts

```python
context_instruction = """
=== CRITICAL ANTI-HALLUCINATION RULES ===
1. ONLY use information from the DATABASE RECORD and RESUME TEXT.
2. If information is NOT available, say: 'That information is not available.'
3. NEVER guess, infer, assume, or fabricate information.
4. NEVER confirm claims the user makes unless verified in the data.
5. For short/ambiguous questions, ask for clarification.
6. Preface answers with 'Based on the records...' or 'According to their resume...'
"""
```

### Alternative LLM Models

| Model | Size | Speed | JSON Accuracy | Recommended For |
|-------|------|-------|---------------|-----------------|
| qwen2.5:7b-instruct | 4.7GB | Slow | Very Good | Current default |
| mistral:7b-instruct | 4GB | Medium | Excellent | Best upgrade |
| llama3.1:8b-instruct | 5GB | Medium | Good | Complex dialogue |
| phi3:mini | 2.3GB | Fast | Good | Testing/dev |

---

## 7. Database Design

### PostgreSQL - Employee Model

```python
class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(6), unique=True)  # Format: 000001

    # Basic
    name = Column(String(256), nullable=False)
    email = Column(String(256))
    phone = Column(String(64))

    # Professional
    department = Column(String(128))
    position = Column(String(128))

    # Online
    linkedin_url = Column(String(512))
    portfolio_url = Column(String(512))
    github_url = Column(String(512))

    # Career
    career_objective = Column(Text)
    summary = Column(Text)

    # Arrays (stored as JSON strings)
    work_experience = Column(Text)
    education = Column(Text)
    technical_skills = Column(Text)
    soft_skills = Column(Text)
    languages = Column(Text)
    certifications = Column(Text)
    achievements = Column(Text)
    hobbies = Column(Text)

    # Location
    address = Column(Text)
    city = Column(String(128))
    country = Column(String(128))

    # Raw data
    raw_text = Column(Text)
    extracted_text = Column(Text)
```

### MongoDB - File Storage

- **GridFS**: Raw PDF files
- **extracted_resumes collection**: Human-readable extracted JSON

### FAISS - Vector Store

- **Index**: data/faiss/index.faiss
- **Metadata**: data/faiss/meta.json
- **Model**: all-MiniLM-L6-v2 (384 dimensions)

---

## 8. API Endpoints

### Health & Diagnostics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic server health |
| GET | `/api/llm-health` | Ollama availability |
| GET | `/api/db-status` | Database connection status |
| GET | `/api/storage-status` | Storage backend status |
| GET | `/api/chat-debug` | Quick diagnostics |

### CV Processing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload-cv` | Upload PDF, enqueue processing |
| GET | `/api/job/{job_id}` | Poll job status |
| GET | `/api/employee/{id}/raw` | Get raw text excerpt |

### Chat & CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Chat with CRUD detection |
| POST | `/api/nl-command` | Parse NL command with validation |
| GET | `/api/nl/{pending_id}` | Get proposal details |
| POST | `/api/nl/{pending_id}/confirm` | Apply confirmed proposal |

---

## 9. Frontend Implementation

### Component Structure

- **App.jsx**: Main container, message display, scroll management
- **Upload.jsx**: File picker, chat input, job polling, session management
- **NLCrud.jsx**: Explicit CRUD confirmation flow

### Key Patterns

```javascript
// Session management
const [sessionId, setSessionId] = useState(null)

// Message handling
const onNewMessage = (m) => setMessages((s) => [m, ...s])

// Auto-scroll
useEffect(() => {
  const t = setTimeout(() => scrollToBottom(), 100)
  return () => clearTimeout(t)
}, [messages])

// Response time tracking with useRef (persists across async operations)
const requestStartTimeRef = useRef(null)
```

---

## 10. Development Report

### Major Errors Encountered & Solutions

| # | Error | Root Cause | Solution |
|---|-------|------------|----------|
| 1 | Frontend 60s timeout | Hardcoded timeout | Removed timeout, infinite polling |
| 2 | LLM adapter timeout | subprocess.run timeout | Increased to 600s |
| 3 | Ollama JSON not parsed | Response wrapped in object | Extract "response" key |
| 4 | File state cleared before upload | clearFile() before async | Capture file reference first |
| 5 | MongoDB storing binary BSON | Using GridFS for JSON | Separate collection + local files |
| 6 | Windows encoding issues | Non-UTF8 console | Decode with errors="replace" |
| 7 | LLM returns explanation | Not following "only JSON" | Regex JSON extraction fallback |
| 8 | Pydantic validation failures | LLM returns dicts in arrays | List[Any] with validators |
| 9 | CORS errors | Different ports | CORS middleware allow_origins=["*"] |
| 10 | Variable shadowing | `text` variable shadows import | Rename to `pdf_text` |
| 11 | Duplicate employee_id | Wrong column in MAX query | Query employee_id column |
| 12 | Background tasks not running | async with blocking I/O | Use threading.Thread |
| 13 | Job status never created | Status written only at end | Write "processing" at start |
| 14 | Cannot upload multiple CVs | !employeeId condition | Remove condition |
| 15 | Session store causing sticky context | Session checked before prompt | Search prompt FIRST, then session |

### Key Lessons Learned

1. **Always remove hardcoded timeouts** for LLM calls
2. **Local LLMs need explicit prompt engineering** - "return ONLY JSON"
3. **Watch for variable shadowing** in Python
4. **Avoid async functions with blocking I/O** - use threading
5. **Write status early** in background tasks
6. **Make Pydantic models flexible** for LLM output
7. **Current prompt beats session memory** - search prompt first
8. **All roads lead to LLM** in conversational systems
9. **Implement anti-hallucination at architecture level**, not just prompts
10. **User experience may prefer slower natural responses** over fast data dumps

---

## 11. Testing Guide

### CRUD Test Scenarios (295+ cases)

**CREATE**: "Create employee John in IT department"
- Should create with specified fields
- Should reject invalid fields (salary)
- Should handle special characters

**READ**: "Show John's details" / "What is his email?"
- Should return correct employee
- Should resolve pronouns from context
- Should say "not found" for non-existent

**UPDATE**: "Update John's department to HR"
- Should show old → new values
- Should handle name-based lookup
- Should reject invalid fields

**DELETE**: "Delete employee John"
- Should confirm deletion
- Should say "not found" for non-existent
- Should ask which one for ambiguous names

### Hallucination Test Cases

| Scenario | Expected | Hallucination Indicator |
|----------|----------|------------------------|
| Ask about non-existent employee | "Not found" | Invents details |
| Ask about missing field (salary) | "Not available" | Fabricates value |
| Leading question ("Confirm PhD?") | Checks records | Confirms blindly |
| Pressure ("URGENT! Salary NOW!") | "Not available" | Invents under pressure |
| Ambiguous ("Show the employee") | "Which employee?" | Picks random one |

### Running Diagnostics

```powershell
cd backend
python diagnose_databases.py
python -m app.config
```

---

## 12. Troubleshooting

### Backend Issues

| Problem | Solution |
|---------|----------|
| Database connection failed | Check DATABASE_URL, start PostgreSQL |
| Ollama connection refused | Start `ollama serve`, check OLLAMA_API_URL |
| Environment variables not loading | Restart uvicorn after .env changes |
| Tables not created | Let app run once, or manually create |

### Frontend Issues

| Problem | Solution |
|---------|----------|
| Can't reach backend | Check VITE_API_BASE_URL, CORS settings |
| Variables not loading | Restart dev server, prefix with VITE_ |

### LLM Issues

| Problem | Solution |
|---------|----------|
| Malformed JSON | Retry with stricter prompt, regex extraction |
| Slow response | Use smaller model (phi3:mini) |
| Hallucination | Check anti-hallucination guards, lower temperature |

---

## 13. Interview Preparation

### Project-Specific Questions

1. **Architecture**: Why dual-database approach?
   - PostgreSQL: Structured queries, ACID compliance
   - MongoDB: Binary file storage, document flexibility

2. **LLM Choice**: Why local Ollama instead of OpenAI?
   - Privacy: Data stays on-premise
   - Cost: No API fees
   - Control: Customizable models

3. **RAG Implementation**: How does it work?
   - Chunk resume text (500 chars)
   - Generate embeddings (384-dim vectors)
   - Store in FAISS index
   - Retrieve top-k relevant chunks for each query

4. **Hallucination Prevention**: What strategies?
   - Architecture-level guards before LLM
   - Explicit "don't make up" instructions
   - Lower temperature (0.3)
   - Source grounding with RAG
   - Pydantic validation

5. **Debugging Approach**: How do you trace issues?
   - [PROCESS_CV] prefixed logs
   - Job status files (data/jobs/)
   - Prompt logs (data/prompts/)
   - Diagnostic scripts

### Technology Questions

- **FastAPI vs Flask**: Async, automatic docs, Pydantic integration
- **SQLAlchemy**: ORM benefits, session management
- **FAISS vs other vector DBs**: Fast, disk-backed, no server needed
- **Sentence-transformers**: Pre-trained embeddings, semantic similarity

---

## 14. Future Improvements

### High Priority

1. **Redis for conversation memory** (currently in-memory, lost on restart)
2. **Celery + Redis for job queue** (currently filesystem-based)
3. **Alembic migrations** (currently auto-migration)
4. **Authentication/authorization** (currently none)
5. **Test suite** (pytest)

### Medium Priority

1. **Export to CSV/Excel**
2. **Bulk CV upload**
3. **Advanced search/filter endpoint**
4. **Audit logging**
5. **Rate limiting**

### Nice to Have

1. **Multi-language CV support**
2. **CV comparison features**
3. **Job description matching**
4. **Confidence scoring in responses**
5. **Source citations in answers**

---

## Quick Reference

### Start System

```bash
# Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Ollama
ollama serve
ollama pull qwen2.5:7b-instruct
```

### Test Configuration

```bash
cd backend
python -m app.config          # Check env vars
python diagnose_databases.py  # Test connections
```

### Key Files

| File | Purpose |
|------|---------|
| backend/app/main.py | API endpoints, processing logic |
| backend/app/db/models.py | Employee model |
| backend/app/services/llm_adapter.py | Ollama integration |
| frontend/src/Upload.jsx | Chat input, file handling |
| frontend/src/App.jsx | Message display |

---

*Consolidated from 24 markdown files*
*Last updated: February 2, 2026*
