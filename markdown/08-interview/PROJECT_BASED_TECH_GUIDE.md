# EMS 2.0 Project-Based Technology Guide

**Learn PostgreSQL, MongoDB, Python, FastAPI, and LLM Integration through actual project code.**

*Every concept is demonstrated with real code from this project.*

---

## Project Overview (30 seconds)

```
EMS 2.0 - AI-Powered Employee Management System

PDF Upload → Text Extraction → LLM Processing → Dual Database Storage → Chat Interface
     │              │                │                    │                   │
     ▼              ▼                ▼                    ▼                   ▼
  GridFS      pdfplumber         Ollama            PostgreSQL            FastAPI
 (MongoDB)    + pytesseract   qwen2.5:7b          + MongoDB             + React
```

**What it does:** Upload resumes, extract information via LLM, query via natural language chat.

---

## 1. PostgreSQL in This Project

### Where It's Used

| Purpose | File | What It Stores |
|---------|------|----------------|
| Structured employee data | `backend/app/db/models.py` | Name, email, skills, experience |
| ORM layer | `backend/app/db/session.py` | SQLAlchemy engine & session |
| CRUD operations | `backend/app/main.py` | Create, Read, Update, Delete |

### Actual Model Definition

📄 **File:** [backend/app/db/models.py](../../backend/app/db/models.py)

```python
from sqlalchemy import Column, Integer, String, Text, Sequence
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Employee(Base):
    __tablename__ = "employees"

    # Primary key (internal, auto-increment)
    id = Column(Integer, primary_key=True, index=True)  # ← ALWAYS index primary keys

    # Custom employee ID - indexed for fast lookups
    employee_id = Column(String(6), unique=True, index=True, nullable=False)

    # Basic Information
    name = Column(String(256), nullable=False)  # ← NOT NULL constraint
    email = Column(String(256), nullable=True)

    # Arrays stored as JSON strings (PostgreSQL-compatible)
    technical_skills = Column(Text, nullable=True)  # JSON array as string
    soft_skills = Column(Text, nullable=True)

    # Full text for RAG
    raw_text = Column(Text, nullable=True)  # ← TEXT for unlimited length
```

### Senior Patterns Used

| Pattern | Where | Why |
|---------|-------|-----|
| **Indexed columns** | `employee_id`, `id` | O(log n) lookups instead of O(n) |
| **NOT NULL constraints** | `name` field | Data integrity |
| **Unique constraints** | `employee_id` | Prevent duplicates |
| **TEXT vs VARCHAR** | `raw_text` vs `name` | TEXT for unlimited, VARCHAR for bounded |

### Session Management

📄 **File:** [backend/app/db/session.py](../../backend/app/db/session.py)

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Fallback to SQLite for development
DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./backend_dev.db"

engine = create_engine(
    DATABASE_URL,
    # SQLite needs this, PostgreSQL doesn't
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

### Auto-Migration Pattern

📄 **File:** [backend/app/main.py:29-94](../../backend/app/main.py)

```python
# Create tables if they don't exist
models.Base.metadata.create_all(bind=engine)

# Add missing columns (poor man's migration)
from sqlalchemy import inspect, text

inspector = inspect(engine)
cols = [c["name"] for c in inspector.get_columns("employees")]

new_columns = {
    "soft_skills": "TEXT",
    "languages": "TEXT",
}

with engine.connect() as conn:
    for col_name, col_type in new_columns.items():
        if col_name not in cols:
            conn.execute(text(f"ALTER TABLE employees ADD COLUMN {col_name} {col_type}"))
            conn.commit()
```

**Senior Note:** In production, use Alembic for proper migrations. This pattern is for rapid prototyping.

---

## 2. MongoDB in This Project

### Where It's Used

| Purpose | Collection/Storage | File |
|---------|-------------------|------|
| Raw PDF files | GridFS (`fs.files`, `fs.chunks`) | `backend/app/services/storage.py` |
| Extracted JSON | `extracted_resumes` collection | `backend/app/services/storage.py` |

### Actual Storage Implementation

📄 **File:** [backend/app/services/storage.py](../../backend/app/services/storage.py)

```python
from pymongo import MongoClient
import gridfs
from bson.objectid import ObjectId

class Storage:
    """Senior pattern: Adapter with graceful fallback."""

    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI")

        # Graceful fallback - works without MongoDB
        if self.mongo_uri and MongoClient:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[os.getenv("MONGO_DB", "cv_repo")]
            self.fs = gridfs.GridFS(self.db)  # For large files
        else:
            self.fs = None  # Fallback to filesystem

    def save_file(self, data: bytes, filename: str) -> str:
        """GridFS for binary files (PDFs)."""
        if self.fs:
            oid = self.fs.put(data, filename=filename)  # Chunks into 255KB pieces
            return str(oid)
        # Fallback to local filesystem
        path = os.path.join(self.local_dir, filename)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def get_file(self, file_id: str) -> Optional[bytes]:
        """Retrieve binary file from GridFS."""
        if self.fs:
            oid = ObjectId(file_id)  # Convert string to ObjectId
            grid_out = self.fs.get(oid)
            return grid_out.read()
        # Fallback
        with open(file_id, "rb") as f:
            return f.read()
```

### Storing Human-Readable JSON (Not Binary)

```python
def save_extracted_data(self, employee_id: str, filename: str, extracted_data: dict) -> str:
    """Store in MongoDB collection (NOT GridFS) for queryability."""

    document = {
        "employee_id": employee_id,
        "original_filename": filename,
        "extraction_timestamp": datetime.utcnow().isoformat(),
        "extracted_data": extracted_data  # Nested document
    }

    if self.db is not None:
        collection = self.db["extracted_resumes"]  # Regular collection
        result = collection.insert_one(document)
        return str(result.inserted_id)

def get_extracted_data(self, employee_id: str) -> Optional[dict]:
    """Query by employee_id - indexed for performance."""
    if self.db is not None:
        collection = self.db["extracted_resumes"]
        doc = collection.find_one({"employee_id": employee_id})
        if doc:
            doc["_id"] = str(doc["_id"])  # ObjectId → string for JSON
            return doc
    return None
```

### Senior Patterns Used

| Pattern | Implementation | Why |
|---------|---------------|-----|
| **GridFS for large files** | `fs.put(data)` | Files >16MB need chunking |
| **Collections for queryable data** | `db["extracted_resumes"]` | Human-readable, indexable |
| **ObjectId to string conversion** | `str(doc["_id"])` | JSON serialization |
| **Graceful fallback** | `if self.fs:` | Works without MongoDB |

---

## 3. Python Senior Patterns in This Project

### Pattern 1: Adapter Pattern (Dependency Inversion)

📄 **File:** [backend/app/services/llm_adapter.py](../../backend/app/services/llm_adapter.py)

```python
class OllamaAdapter:
    """Adapter pattern - swap implementations without changing callers."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        self._ollama_path = shutil.which("ollama")  # Check CLI availability

    def generate(self, prompt: str) -> str:
        """Single interface, multiple implementations."""
        # Try HTTP API first
        if api_url := os.getenv("OLLAMA_API_URL"):
            return self._generate_http(prompt)
        # Fallback to CLI
        return self._generate_cli(prompt)
```

**Why this matters:** Change from Ollama to OpenAI? Just create a new adapter with the same interface.

### Pattern 2: Graceful Degradation

📄 **File:** [backend/app/services/storage.py:46-63](../../backend/app/services/storage.py)

```python
def save_file(self, data: bytes, filename: str) -> str:
    # Try primary storage (MongoDB GridFS)
    if self.fs:
        try:
            oid = self.fs.put(data, filename=filename)
            return str(oid)
        except Exception as e:
            self.logger.exception("GridFS save failed, falling back to local file")

    # Fallback: local filesystem (always works)
    path = os.path.join(self.local_dir, filename)
    with open(path, "wb") as f:
        f.write(data)
    return path
```

**Why this matters:** System works even if MongoDB is down.

### Pattern 3: Pydantic Validation with Flexible Types

📄 **File:** [backend/app/main.py:443-470](../../backend/app/main.py)

```python
from pydantic import BaseModel, field_validator
from typing import List, Any, Optional

class ResumeExtraction(BaseModel):
    name: str
    email: Optional[str] = None
    technical_skills: List[Any] = []  # Accept any type, normalize later

    @field_validator('technical_skills', mode='before')
    @classmethod
    def stringify_items(cls, v):
        """LLM sometimes returns dicts instead of strings - handle gracefully."""
        if not v:
            return []
        result = []
        for item in v:
            if isinstance(item, dict):
                result.append(json.dumps(item))  # Dict → JSON string
            else:
                result.append(str(item))
        return result
```

**Why this matters:** LLMs are unpredictable. Validate but don't break.

### Pattern 4: Context Manager for Database Sessions

📄 **File:** [backend/app/main.py](../../backend/app/main.py) (used throughout)

```python
from sqlalchemy.orm import Session

db: Session = SessionLocal()
try:
    # Database operations
    employee = db.query(models.Employee).filter(...).first()
    db.add(new_employee)
    db.commit()
finally:
    db.close()  # ALWAYS close, even on exception
```

**Senior improvement (not in current code but recommended):**

```python
from contextlib import contextmanager

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Usage
with get_db() as db:
    employee = db.query(Employee).first()
```

---

## 4. FastAPI in This Project

### Application Setup

📄 **File:** [backend/app/main.py:1-113](../../backend/app/main.py)

```python
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="CV Chat PoC")

# CORS Middleware - Allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Restrict in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response
```

### File Upload Endpoint

📄 **File:** [backend/app/main.py:156-215](../../backend/app/main.py)

```python
@app.post("/api/upload-cv")
async def upload_cv(file: UploadFile = File(...)):
    """Upload PDF and process asynchronously."""

    # 1. Read file contents
    contents = await file.read()

    # 2. Save to storage (GridFS or local)
    file_id = storage.save_file(contents, filename=file.filename)

    # 3. Generate job ID for tracking
    job_id = str(uuid.uuid4())

    # 4. Start background processing (not blocking)
    import threading
    thread = threading.Thread(
        target=process_cv_background,
        args=(job_id, contents, file.filename)
    )
    thread.start()

    # 5. Return immediately with job ID
    return {"job_id": job_id, "status": "processing"}
```

**Senior Pattern:** Non-blocking upload with job tracking.

### Job Status Polling

📄 **File:** [backend/app/main.py](../../backend/app/main.py)

```python
@app.get("/api/job/{job_id}")
def get_job_status(job_id: str):
    """Poll for job completion."""
    job_file = os.path.join(JOB_DIR, f"{job_id}.json")

    if not os.path.exists(job_file):
        return {"status": "processing"}  # Still running

    with open(job_file) as f:
        return json.load(f)  # Returns {status, employee_id, ...}
```

### Chat Endpoint with Session Memory

📄 **File:** [backend/app/main.py](../../backend/app/main.py)

```python
class ChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    employee_id: Optional[str] = None

@app.post("/api/chat")
def chat(req: ChatRequest):
    """Chat with conversation memory."""

    # Generate session ID if not provided
    session_id = req.session_id or str(uuid.uuid4())

    # Get conversation history (last 10 messages)
    conversation_history = list(conversation_store[session_id])

    # Add current message to history
    conversation_store[session_id].append({
        "role": "user",
        "content": req.prompt
    })

    # Process and generate response...
    response = generate_response(req.prompt, conversation_history)

    # Store assistant response
    conversation_store[session_id].append({
        "role": "assistant",
        "content": response
    })

    return {
        "reply": response,
        "session_id": session_id
    }
```

### Senior Patterns Used

| Pattern | Implementation | Why |
|---------|---------------|-----|
| **Async file handling** | `await file.read()` | Non-blocking I/O |
| **Background processing** | `threading.Thread` | Don't block HTTP response |
| **Job tracking** | File-based status | Simple, works without Redis |
| **Session management** | `defaultdict(deque)` | Conversation memory |
| **Pydantic request models** | `ChatRequest` | Auto-validation |

---

## 5. LLM Integration in This Project

### LLM Adapter

📄 **File:** [backend/app/services/llm_adapter.py](../../backend/app/services/llm_adapter.py)

```python
class OllamaAdapter:
    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

    def generate(self, prompt: str) -> str:
        """Try HTTP API, fallback to CLI."""

        # HTTP API (preferred)
        api_url = os.getenv("OLLAMA_API_URL")
        if api_url:
            resp = requests.post(
                api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=600  # 10 minutes - LLMs are slow!
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["response"].strip()

        # CLI fallback
        cmd = [self._ollama_path, "run", self.model, prompt]
        proc = subprocess.run(cmd, capture_output=True, text=False)
        return proc.stdout.decode("utf-8", errors="replace").strip()
```

### Extraction Prompt Engineering

📄 **File:** [backend/app/main.py:340-380](../../backend/app/main.py)

```python
extraction_prompt = (
    "CRITICAL: Extract resume data as STRICT JSON only. NO explanations.\n\n"
    "Return JSON with these keys (use null if not found):\n"
    "name, email, phone, linkedin_url, portfolio_url, github_url, "
    "department, position, career_objective, summary, work_experience, "
    "education, technical_skills, soft_skills, languages, certifications, "
    "achievements, hobbies, cocurricular_activities, address, city, country\n\n"
    "Arrays must use JSON array format: [\"item1\", \"item2\"]\n\n"
    f"Resume:\n\n{pdf_text[:8000]}\n\nJSON:"
)
```

**Key techniques:**
1. **Explicit instruction**: "STRICT JSON only. NO explanations."
2. **Schema definition**: List all expected keys
3. **Format specification**: "Arrays must use JSON array format"
4. **Text truncation**: `pdf_text[:8000]` to fit context window

### Robust JSON Extraction

📄 **File:** [backend/app/main.py](../../backend/app/main.py)

```python
import re
import json

def extract_json_from_llm_response(response: str) -> dict:
    """LLMs don't always return clean JSON - handle gracefully."""

    # Try direct parse first
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try to find JSON in markdown code blocks
    patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
        r'\{.*\}',  # Raw JSON object
    ]

    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            try:
                json_str = match.group(1) if '```' in pattern else match.group(0)
                return json.loads(json_str)
            except:
                continue

    raise ValueError("Could not extract JSON from LLM response")
```

### Anti-Hallucination System

📄 **File:** [backend/app/main.py:1370-1390](../../backend/app/main.py)

```python
context_instruction = (
    "You are answering questions about an employee/candidate.\n\n"
    "=== CRITICAL ANTI-HALLUCINATION RULES ===\n"
    "1. ONLY use information from the DATABASE RECORD and RESUME TEXT provided below.\n"
    "2. For Employee ID, email, phone, department - use the DATABASE RECORD section.\n"
    "3. For experience, skills, projects - use the resume/CV content.\n"
    "4. If information is NOT available, say: 'That information is not available in the records.'\n"
    "5. NEVER guess, infer, assume, or fabricate information.\n"
    "6. NEVER confirm claims the user makes unless verified in the data.\n"
    "7. If the user says 'I heard they worked at X' - verify against records first.\n"
    "8. If the user asks leading questions, stick to the facts.\n"
    "9. Do NOT invent salaries, dates, companies, or skills not in the data.\n"
    "10. For short/ambiguous questions, ask for clarification.\n"
    "11. Pronouns (he/she/they/him/her/his/their) refer to this employee.\n\n"
)
```

---

## 6. Full Integration Flow

### Step-by-Step: PDF Upload to Database

```
1. User uploads PDF via React frontend
   └─▶ POST /api/upload-cv
           │
2. FastAPI receives file
   └─▶ contents = await file.read()
           │
3. Store raw PDF in MongoDB GridFS
   └─▶ file_id = storage.save_file(contents, filename)
           │
4. Start background thread
   └─▶ threading.Thread(target=process_cv_background)
           │
5. Extract text from PDF
   └─▶ pdfplumber.open() → extract text
   └─▶ Fallback: pytesseract OCR
           │
6. Send to LLM for structured extraction
   └─▶ llm.generate(extraction_prompt)
           │
7. Parse JSON response
   └─▶ Pydantic validation
   └─▶ Fallback regex extraction
           │
8. Store in PostgreSQL
   └─▶ db.add(Employee(...))
   └─▶ db.commit()
           │
9. Store extracted JSON in MongoDB
   └─▶ storage.save_extracted_data(employee_id, data)
           │
10. Index in FAISS for RAG
    └─▶ vectorstore.add_texts(chunks, employee_id)
           │
11. Update job status
    └─▶ Write JSON to data/jobs/{job_id}.json
           │
12. Frontend polls and gets completion
    └─▶ GET /api/job/{job_id}
```

### Step-by-Step: Chat Query

```
1. User sends chat message
   └─▶ POST /api/chat {prompt, session_id}
           │
2. CRUD Detection
   └─▶ Is this a create/update/delete command?
   └─▶ Route to CRUD pipeline if yes
           │
3. Employee Lookup (Priority Order)
   └─▶ Search prompt for employee names
   └─▶ Check session memory for active employee
   └─▶ Use employee_id from request
           │
4. Anti-Hallucination Guards
   └─▶ Guard 1: Ambiguous query? Ask for clarification
   └─▶ Guard 2: Short prompt? Request more context
   └─▶ Guard 3: Non-existent employee? Return "not found"
   └─▶ Guard 4: Leading question? Don't confirm blindly
   └─▶ Guard 5: Pressure/urgency? Don't bypass checks
   └─▶ Guard 6: No context? Ask which employee
           │
5. Build Context
   └─▶ Database record (structured fields)
   └─▶ RAG retrieval (relevant resume chunks)
   └─▶ Conversation history (last 5 messages)
           │
6. Generate Response
   └─▶ llm.generate(grounded_prompt)
           │
7. Store in Session Memory
   └─▶ conversation_store[session_id].append(...)
           │
8. Return Response
   └─▶ {reply, session_id, employee_id}
```

---

## 7. Key Files Reference

| What | File | Key Lines |
|------|------|-----------|
| **PostgreSQL Model** | `backend/app/db/models.py` | 10-60 |
| **DB Session** | `backend/app/db/session.py` | 1-9 |
| **MongoDB Storage** | `backend/app/services/storage.py` | 18-161 |
| **LLM Adapter** | `backend/app/services/llm_adapter.py` | 9-117 |
| **FastAPI App** | `backend/app/main.py` | 96-150 |
| **Upload Endpoint** | `backend/app/main.py` | 156-215 |
| **Chat Endpoint** | `backend/app/main.py` | 650-1520 |
| **CRUD Detection** | `backend/app/main.py` | 730-950 |
| **Anti-Hallucination** | `backend/app/main.py` | 1370-1390 |
| **Pydantic Validation** | `backend/app/main.py` | 443-470 |

---

## 8. Interview Quick Reference

### "Explain Your PostgreSQL Usage"

> "I use PostgreSQL for structured employee data—names, emails, skills. The Employee model has 25 columns with proper constraints: NOT NULL for required fields, UNIQUE for employee_id, and indexes on frequently queried columns. I store arrays like skills as JSON strings in TEXT columns for compatibility. The session management uses SQLAlchemy's sessionmaker with proper connection handling in try/finally blocks."

### "Explain Your MongoDB Usage"

> "MongoDB serves two purposes: GridFS stores raw PDF files (which can exceed 16MB), while a regular collection stores human-readable extracted JSON for queryability. I implemented a Storage adapter with graceful fallback—if MongoDB is unavailable, it falls back to filesystem storage. This ensures the system works in development without running MongoDB."

### "Explain Your LLM Integration"

> "The LLM adapter supports both HTTP API and CLI fallback for Ollama. For extraction, I use explicit prompt engineering with strict JSON instructions. Since LLMs are unpredictable, I implemented robust JSON parsing with regex fallback, Pydantic validation with flexible types, and a 6-layer anti-hallucination system that guards against fabricated responses."

### "Explain Your FastAPI Architecture"

> "The FastAPI app uses async file handling for uploads, background threads for LLM processing (which is CPU-bound), and file-based job tracking for polling. Chat endpoints maintain session memory using a defaultdict of deques, storing the last 10 messages per session. All requests go through CORS middleware and custom logging middleware."

---

## One-Page Cheat Sheet

```
┌─────────────────────────────────────────────────────────────────┐
│                    EMS 2.0 ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  POSTGRESQL (Structured Data)          MONGODB (Files + JSON)   │
│  ├── Employee model (25 columns)       ├── GridFS (PDFs)        │
│  ├── SQLAlchemy ORM                    ├── extracted_resumes    │
│  ├── Session management                └── Graceful fallback    │
│  └── Auto-migration on startup                                  │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FASTAPI (API Layer)                   LLM (AI Layer)           │
│  ├── CORS middleware                   ├── Ollama adapter       │
│  ├── Async file upload                 ├── HTTP + CLI fallback  │
│  ├── Background processing             ├── Prompt engineering   │
│  ├── Job polling mechanism             ├── JSON extraction      │
│  └── Session-based chat                └── Anti-hallucination   │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SENIOR PATTERNS USED                                           │
│  ├── Adapter pattern (LLM, Storage)                             │
│  ├── Graceful degradation (fallbacks everywhere)                │
│  ├── Pydantic validation with flexible types                    │
│  ├── Background processing (threading)                          │
│  ├── Session memory (conversation context)                      │
│  └── Defense in depth (6-layer anti-hallucination)              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

*Based on actual code from EMS 2.0 project*
*Last updated: February 3, 2026*
