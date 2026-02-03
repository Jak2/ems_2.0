# EMS 2.0 - Complete Project Walkthrough

A step-by-step explanation of every file, every function, and every line of code in the project.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Project Structure](#2-project-structure)
3. [Backend: Database Layer](#3-backend-database-layer)
4. [Backend: Services Layer](#4-backend-services-layer)
5. [Backend: Main Application](#5-backend-main-application)
6. [Frontend: React Application](#6-frontend-react-application)
7. [Data Flow: End-to-End](#7-data-flow-end-to-end)
8. [Configuration Files](#8-configuration-files)

---

## 1. Project Overview

### What We Built

We built an **AI-powered Employee Management System** that:

1. **Accepts PDF resumes** via a web interface
2. **Extracts text** from PDFs using pdfplumber (with OCR fallback)
3. **Processes text through an LLM** (Ollama) to extract structured data
4. **Stores data in dual databases** (PostgreSQL for structured data, MongoDB for files)
5. **Indexes content in a vector database** (FAISS) for semantic search
6. **Provides a chat interface** for natural language queries
7. **Implements anti-hallucination guards** to ensure accurate responses

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | React + Vite | User interface |
| Backend | FastAPI | REST API |
| Relational DB | PostgreSQL/SQLite | Structured employee data |
| Document DB | MongoDB + GridFS | PDF storage |
| Vector DB | FAISS | Semantic search |
| LLM | Ollama (qwen2.5:7b) | Text generation & extraction |
| Embeddings | sentence-transformers | Vector embeddings |

---

## 2. Project Structure

```
ems_2.0/
├── backend/
│   ├── app/
│   │   ├── __init__.py              # Package marker
│   │   ├── main.py                  # FastAPI application (1500+ lines)
│   │   ├── config.py                # Configuration loader
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── models.py            # SQLAlchemy ORM models
│   │   │   └── session.py           # Database connection
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── llm_adapter.py       # Ollama integration
│   │       ├── storage.py           # MongoDB/filesystem storage
│   │       ├── extractor.py         # PDF text extraction
│   │       ├── embeddings.py        # Sentence-transformers wrapper
│   │       └── vectorstore_faiss.py # FAISS vector store
│   ├── data/
│   │   ├── files/                   # Local file storage (fallback)
│   │   ├── jobs/                    # Job status JSON files
│   │   ├── extracted/               # Extracted JSON data
│   │   ├── faiss/                   # FAISS index files
│   │   └── prompts/                 # Prompt logs for debugging
│   ├── scripts/
│   │   ├── check_db_connection.py   # Database diagnostic
│   │   └── diagnose_databases.py    # Full system diagnostic
│   ├── .env                         # Environment variables
│   ├── .env.example                 # Environment template
│   └── requirements.txt             # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── main.jsx                 # React entry point
│   │   ├── App.jsx                  # Main component
│   │   ├── Upload.jsx               # File upload & chat
│   │   ├── NLCrud.jsx               # Natural language CRUD
│   │   └── styles.css               # Styling
│   ├── .env                         # Frontend environment
│   └── package.json                 # NPM dependencies
└── markdown/                        # Documentation
```

---

## 3. Backend: Database Layer

### 3.1 models.py - SQLAlchemy ORM Model

📄 **File:** `backend/app/db/models.py`

**Purpose:** Defines the Employee table structure using SQLAlchemy ORM.

```python
from sqlalchemy import Column, Integer, String, Text, Sequence
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
```

**What this does:**
- We import SQLAlchemy column types for different data types
- `declarative_base()` creates a base class that our models inherit from
- SQLAlchemy uses this base to track all models and create tables

```python
class Employee(Base):
    __tablename__ = "employees"

    # Primary key (internal, auto-increment)
    id = Column(Integer, primary_key=True, index=True)

    # Custom employee ID (format: 013449) - auto-generated
    employee_id = Column(String(6), unique=True, index=True, nullable=False)
```

**What this does:**
- `__tablename__` sets the actual database table name
- `id` is an auto-incrementing integer primary key (internal use)
- `employee_id` is a 6-digit string like "000001" (user-facing ID)
- `index=True` creates a B-tree index for fast lookups
- `unique=True` prevents duplicate employee IDs
- `nullable=False` means this field is required

```python
    # Basic Information
    name = Column(String(256), nullable=False)
    email = Column(String(256), nullable=True)
    phone = Column(String(64), nullable=True)

    # Professional Information
    department = Column(String(128), nullable=True)
    position = Column(String(128), nullable=True)
```

**What this does:**
- `String(256)` creates a VARCHAR column with max 256 characters
- `nullable=True` means the field is optional
- We separate basic info from professional info for clarity

```python
    # Arrays stored as JSON strings (PostgreSQL-compatible)
    technical_skills = Column(Text, nullable=True)     # JSON array
    soft_skills = Column(Text, nullable=True)          # JSON array
    work_experience = Column(Text, nullable=True)      # JSON array
    education = Column(Text, nullable=True)            # JSON array
```

**What this does:**
- `Text` is unlimited length (unlike VARCHAR)
- We store arrays as JSON strings: `["Python", "Java", "React"]`
- This works across SQLite and PostgreSQL without array type issues

```python
    # Original CV data
    raw_text = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
```

**What this does:**
- `raw_text` stores the full text extracted from the PDF
- `extracted_text` stores the cleaned/processed version
- This enables RAG (retrieval) without re-reading the PDF

---

### 3.2 session.py - Database Connection

📄 **File:** `backend/app/db/session.py`

**Purpose:** Creates the database engine and session factory.

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///./backend_dev.db"
```

**What this does:**
- We read `DATABASE_URL` from environment variables
- If not set, we fall back to SQLite (great for development)
- SQLite requires no server setup - just creates a file

```python
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
```

**What this does:**
- `create_engine` creates a connection pool to the database
- SQLite needs `check_same_thread=False` for FastAPI (multiple threads)
- PostgreSQL doesn't need this, so we conditionally add it

```python
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

**What this does:**
- `sessionmaker` creates a factory for database sessions
- `autocommit=False` means we control when changes are committed
- `autoflush=False` means we control when changes are sent to DB
- `bind=engine` connects sessions to our database engine

**How we use it:**
```python
db = SessionLocal()
try:
    employee = db.query(Employee).filter(Employee.id == 1).first()
    db.commit()
finally:
    db.close()  # Always close to return connection to pool
```

---

## 4. Backend: Services Layer

### 4.1 storage.py - File Storage Adapter

📄 **File:** `backend/app/services/storage.py`

**Purpose:** Handles file storage with MongoDB GridFS or local filesystem fallback.

```python
from pymongo import MongoClient
import gridfs
from bson.objectid import ObjectId

class Storage:
    """Storage adapter. Tries MongoDB GridFS, falls back to filesystem."""

    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI")
        self.local_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "files")
        os.makedirs(self.local_dir, exist_ok=True)
```

**What this does:**
- We check if `MONGO_URI` is configured
- We always set up a local directory as fallback
- `os.makedirs(..., exist_ok=True)` creates the directory if it doesn't exist

```python
        if self.mongo_uri and MongoClient:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[os.getenv("MONGO_DB", "cv_repo")]
            self.fs = gridfs.GridFS(self.db)
        else:
            self.fs = None  # Will use local filesystem
```

**What this does:**
- If MongoDB is configured, we connect and create a GridFS instance
- GridFS is MongoDB's system for storing files larger than 16MB
- If no MongoDB, `self.fs = None` triggers the fallback path

```python
    def save_file(self, data: bytes, filename: str) -> str:
        """Save binary file to GridFS or local filesystem."""
        if self.fs:
            try:
                oid = self.fs.put(data, filename=filename)
                return str(oid)  # Return MongoDB ObjectId as string
            except Exception as e:
                self.logger.exception("GridFS save failed, falling back")

        # Fallback: save to local filesystem
        path = os.path.join(self.local_dir, filename)
        with open(path, "wb") as f:
            f.write(data)
        return path  # Return file path as identifier
```

**What this does:**
- First, we try to save to GridFS using `fs.put()`
- GridFS automatically chunks large files into 255KB pieces
- If GridFS fails, we save to the local filesystem
- We return either an ObjectId string or a file path

```python
    def get_file(self, file_id: str) -> Optional[bytes]:
        """Retrieve file by ID."""
        if self.fs:
            try:
                oid = ObjectId(file_id)  # Convert string to ObjectId
                grid_out = self.fs.get(oid)
                return grid_out.read()
            except Exception:
                return None

        # Fallback: read from local path
        try:
            with open(file_id, "rb") as f:
                return f.read()
        except Exception:
            return None
```

**What this does:**
- If GridFS is available, we convert the string ID back to ObjectId
- `fs.get()` retrieves the file, `read()` gets the bytes
- For local files, the `file_id` is actually the file path

---

### 4.2 extractor.py - PDF Text Extraction

📄 **File:** `backend/app/services/extractor.py`

**Purpose:** Extracts text from PDF files using pdfplumber with OCR fallback.

```python
import pdfplumber
try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None  # OCR won't be available
```

**What this does:**
- We import pdfplumber (always required)
- We try to import pytesseract and PIL for OCR
- If OCR libraries aren't installed, we continue without them

```python
def extract_text_from_bytes(data: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
            text = "\n\n".join(pages)
```

**What this does:**
- `io.BytesIO(data)` wraps bytes as a file-like object
- `pdfplumber.open()` parses the PDF
- We extract text from each page and join with double newlines

```python
            # If no text extracted, try OCR
            if (not text or text.strip() == "") and pytesseract:
                ocr_pages = []
                for p in pdf.pages:
                    imgobj = p.to_image(resolution=150)
                    pil_img = imgobj.original
                    ocr_text = pytesseract.image_to_string(pil_img)
                    ocr_pages.append(ocr_text)
                return "\n\n".join(ocr_pages)
```

**What this does:**
- If pdfplumber returns empty (scanned PDF), we try OCR
- We convert each page to an image at 150 DPI
- pytesseract performs OCR on the image
- This handles scanned documents that have no embedded text

---

### 4.3 llm_adapter.py - Ollama Integration

📄 **File:** `backend/app/services/llm_adapter.py`

**Purpose:** Communicates with the Ollama LLM via HTTP API or CLI.

```python
class OllamaAdapter:
    """Adapter for Ollama LLM. Supports HTTP API and CLI fallback."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        self._ollama_path = shutil.which("ollama")  # Find CLI executable
```

**What this does:**
- We get the model name from parameter, env var, or use default
- `shutil.which("ollama")` finds the ollama executable in PATH
- This allows both HTTP API and CLI fallback

```python
    def generate(self, prompt: str) -> str:
        """Generate text. Tries HTTP API, falls back to CLI."""

        # Try HTTP API first (if configured)
        api_url = os.getenv("OLLAMA_API_URL")
        if api_url:
            try:
                payload = {"model": self.model, "prompt": prompt, "stream": False}
                resp = requests.post(api_url, json=payload, timeout=600)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["response"].strip()
            except requests.exceptions.RequestException as e:
                http_error = e
```

**What this does:**
- We check if `OLLAMA_API_URL` is set (e.g., `http://localhost:11434/api/generate`)
- We send a POST request with model name and prompt
- `timeout=600` gives the LLM 10 minutes (they can be slow)
- `stream=False` means we wait for the complete response

```python
        # Fallback to CLI
        if not self._ollama_path:
            raise RuntimeError("Ollama HTTP API failed and CLI not found")

        cmd = [self._ollama_path, "run", self.model, prompt]
        proc = subprocess.run(cmd, capture_output=True, text=False)
        return proc.stdout.decode("utf-8", errors="replace").strip()
```

**What this does:**
- If HTTP fails, we try the `ollama run` CLI command
- `capture_output=True` captures stdout and stderr
- `text=False` gives us bytes (we decode manually for Windows compatibility)
- `errors="replace"` handles encoding issues gracefully

---

### 4.4 embeddings.py - Text Embeddings

📄 **File:** `backend/app/services/embeddings.py`

**Purpose:** Generates vector embeddings from text using sentence-transformers.

```python
from sentence_transformers import SentenceTransformer
import numpy as np

class Embeddings:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
```

**What this does:**
- We load the `all-MiniLM-L6-v2` model (384 dimensions, fast)
- This model converts text into vectors that capture semantic meaning
- Similar texts have similar vectors (close in vector space)

```python
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Return L2-normalized embeddings."""
        emb = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

        # Normalize to unit length (for cosine similarity)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # Prevent division by zero
        emb = emb / norms

        return emb.astype("float32")
```

**What this does:**
- `model.encode()` converts text strings to vectors
- We normalize vectors to unit length (L2 normalization)
- Normalized vectors enable cosine similarity via dot product
- `float32` is efficient for FAISS

---

### 4.5 vectorstore_faiss.py - Vector Database

📄 **File:** `backend/app/services/vectorstore_faiss.py`

**Purpose:** Stores and searches vectors using FAISS.

```python
import faiss

class FaissVectorStore:
    def __init__(self, path: str):
        self.path = path
        self.index_path = os.path.join(path, "index.faiss")
        self.meta_path = os.path.join(path, "meta.json")
        self.emb = Embeddings()
        self._load()
```

**What this does:**
- We set up paths for the FAISS index and metadata
- We create an Embeddings instance for generating vectors
- `_load()` loads existing index from disk (if any)

```python
    def _load(self):
        """Load existing index from disk."""
        self.meta: List[Dict] = []
        if os.path.exists(self.meta_path):
            with open(self.meta_path, "r") as f:
                self.meta = json.load(f)
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
        else:
            self.index = None
```

**What this does:**
- We load metadata (maps vector IDs to employee IDs and text)
- We load the FAISS index from disk
- If no index exists, we start fresh

```python
    def add_chunks(self, employee_id: int, chunks: List[str]):
        """Add text chunks to the index."""
        if not chunks:
            return []

        # Generate embeddings
        vecs = self.emb.embed_texts(chunks)
        n, dim = vecs.shape

        # Create index if first time
        if self.index is None:
            self.index = faiss.IndexFlatIP(dim)  # Inner Product index
```

**What this does:**
- We convert text chunks to vectors
- `IndexFlatIP` uses inner product (equals cosine similarity for normalized vectors)
- This is exact search, suitable for our scale (thousands of vectors)

```python
        # Add vectors to index
        self.index.add(vecs)

        # Store metadata
        start_id = len(self.meta)
        for i, txt in enumerate(chunks):
            self.meta.append({
                "id": start_id + i,
                "employee_id": employee_id,
                "text": txt
            })

        # Persist to disk
        self._save_meta()
        self._save_index()
```

**What this does:**
- `index.add()` adds vectors to FAISS
- We store metadata linking vector IDs to employees and original text
- We save both to disk for persistence across restarts

```python
    def search(self, query: str, top_k: int = 5, employee_id: Optional[int] = None):
        """Search for similar chunks."""
        if self.index is None:
            return []

        # Embed the query
        qvec = self.emb.embed_texts([query])

        # Search FAISS
        D, I = self.index.search(qvec, min(top_k * 5, len(self.meta)))
```

**What this does:**
- We convert the query to a vector
- `index.search()` finds the nearest neighbors
- `D` contains similarity scores, `I` contains indices
- We search for more than needed to allow for filtering

```python
        # Build results with optional employee filter
        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            m = self.meta[idx].copy()
            m["score"] = float(score)

            if employee_id is None or m.get("employee_id") == employee_id:
                results.append(m)

            if len(results) >= top_k:
                break

        return results
```

**What this does:**
- We look up metadata for each matched vector
- We optionally filter by employee ID (for focused queries)
- We return top-k results with scores

---

## 5. Backend: Main Application

### 5.1 main.py - FastAPI Application

📄 **File:** `backend/app/main.py`

**Purpose:** The main FastAPI application with all endpoints and business logic.

#### Application Setup

```python
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CV Chat PoC")

# CORS middleware - allows frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Allow all origins (restrict in production)
    allow_credentials=True,
    allow_methods=["*"],      # Allow all HTTP methods
    allow_headers=["*"],      # Allow all headers
)
```

**What this does:**
- We create a FastAPI application
- CORS middleware allows the React frontend to call the API
- Without CORS, browsers block cross-origin requests

```python
# Initialize services
storage = Storage()                    # File storage
llm = OllamaAdapter()                  # LLM connection
vectorstore = FaissVectorStore(FAISS_DIR)  # Vector database

# Session memory (in production, use Redis)
from collections import defaultdict, deque
conversation_store = defaultdict(lambda: deque(maxlen=10))
active_employee_store = {}  # {session_id: employee_id}
```

**What this does:**
- We create instances of all our services
- `conversation_store` keeps the last 10 messages per session
- `active_employee_store` tracks which employee is being discussed

#### Upload Endpoint

```python
@app.post("/api/upload-cv")
async def upload_cv(file: UploadFile = File(...)):
    """Upload a CV/resume PDF for processing."""

    # Read file contents
    contents = await file.read()

    # Save to storage (GridFS or local)
    file_id = storage.save_file(contents, filename=file.filename)

    # Generate job ID
    job_id = str(uuid.uuid4())
```

**What this does:**
- `async def` makes this an async endpoint (handles concurrent requests)
- `UploadFile` is FastAPI's file upload type
- We read the file bytes and save to storage
- We generate a unique job ID for tracking

```python
    # Start background processing
    import threading

    def run_process_cv():
        process_cv(file_id, file.filename, job_id)

    thread = threading.Thread(target=run_process_cv, daemon=True)
    thread.start()

    return {"job_id": job_id, "status": "queued"}
```

**What this does:**
- We use a thread for background processing (not async - LLM calls block)
- `daemon=True` means the thread dies when the main process exits
- We return immediately with the job ID (non-blocking upload)

#### CV Processing Function

```python
def process_cv(file_id: str, filename: str, job_id: str):
    """Process CV in background thread."""

    # Write initial status
    with open(os.path.join(JOB_DIR, f"{job_id}.json"), "w") as jf:
        jf.write('{"status":"processing"}')
```

**What this does:**
- We write a status file so the frontend can poll progress
- The status starts as "processing"

```python
    # Fetch file from storage
    data = storage.get_file(file_id)

    # Extract text from PDF
    pdf_text = extract_text_from_bytes(data)
```

**What this does:**
- We retrieve the PDF bytes from storage
- We extract text using pdfplumber (with OCR fallback)

```python
    # Generate employee ID
    from sqlalchemy import text as sql_text
    result = db.execute(sql_text(
        "SELECT COALESCE(MAX(CAST(employee_id AS INTEGER)), 0) + 1 FROM employees"
    )).scalar()
    employee_id = str(result).zfill(6)  # Format: 000001
```

**What this does:**
- We query the max existing employee_id
- We add 1 and zero-pad to 6 digits
- This ensures unique, sequential IDs

```python
    # Create employee record
    emp = models.Employee(
        employee_id=employee_id,
        name=filename,  # Placeholder, updated by LLM
        raw_text=pdf_text,
    )
    db.add(emp)
    db.commit()
```

**What this does:**
- We create an Employee record with the raw text
- The name is initially the filename (updated after LLM extraction)
- `db.commit()` saves to the database

```python
    # Chunk text and index in FAISS
    def chunk_text(s: str, chunk_size: int = 500, overlap: int = 100):
        chunks = []
        i = 0
        while i < len(s):
            chunks.append(s[i:i + chunk_size])
            i += chunk_size - overlap
        return chunks

    chunks = chunk_text(pdf_text)
    vectorstore.add_chunks(emp.id, chunks)
```

**What this does:**
- We split text into 500-character chunks with 100-character overlap
- Overlap ensures information at boundaries isn't lost
- We index chunks in FAISS for semantic search

```python
    # LLM extraction prompt
    extraction_prompt = (
        "You are a professional resume parser. Extract ALL information into JSON.\n\n"
        "CRITICAL RULES:\n"
        "1. Return ONLY valid JSON - no explanations\n"
        "2. Use null for missing fields\n"
        "3. Do NOT guess - only extract what's explicitly stated\n\n"
        f"Resume text:\n\n{pdf_text[:8000]}\n\nJSON output:"
    )

    extraction_resp = llm.generate(extraction_prompt)
```

**What this does:**
- We craft a prompt that instructs the LLM to extract structured data
- We limit to 8000 characters to fit the context window
- We call the LLM and get the response

```python
    # Parse JSON from response
    try:
        parsed = json.loads(extraction_resp)
    except:
        # Fallback: find JSON in the response
        import re
        m = re.search(r"\{.*\}", extraction_resp, re.S)
        if m:
            parsed = json.loads(m.group(0))
```

**What this does:**
- We try to parse the response directly as JSON
- LLMs sometimes add explanatory text, so we fall back to regex extraction
- `re.S` makes `.` match newlines (for multi-line JSON)

```python
    # Validate with Pydantic
    from pydantic import BaseModel, field_validator

    class ComprehensiveExtractionModel(BaseModel):
        name: str | None = None
        email: str | None = None
        technical_skills: List[Any] | None = None

        @field_validator('technical_skills', mode='before')
        @classmethod
        def convert_dicts_to_strings(cls, v):
            if isinstance(v, list):
                return [json.dumps(x) if isinstance(x, dict) else str(x) for x in v]
            return v

    parsed_model = ComprehensiveExtractionModel(**parsed)
```

**What this does:**
- We validate and normalize the LLM output with Pydantic
- `List[Any]` accepts both strings and dicts (LLMs are unpredictable)
- The validator converts dicts to JSON strings for storage

```python
    # Update employee record with extracted data
    emp.name = parsed_model.name or filename
    emp.email = parsed_model.email
    emp.technical_skills = json.dumps(parsed_model.technical_skills)
    db.commit()

    # Write completion status
    with open(os.path.join(JOB_DIR, f"{job_id}.json"), "w") as jf:
        json.dump({"status": "done", "employee_id": emp.employee_id}, jf)
```

**What this does:**
- We update the employee record with extracted data
- Arrays are serialized as JSON strings
- We write the final status for the frontend to poll

#### Chat Endpoint

```python
@app.post("/api/chat")
def chat(req: ChatRequest):
    """Chat endpoint with CRUD detection and anti-hallucination."""

    session_id = req.session_id or str(uuid.uuid4())
    conversation_history = list(conversation_store[session_id])
```

**What this does:**
- We get or create a session ID
- We retrieve conversation history for context

```python
    # CRUD Detection
    crud_keywords = ["update", "delete", "remove", "create", "add", "change"]
    is_crud = any(kw in req.prompt.lower() for kw in crud_keywords)
```

**What this does:**
- We check if the prompt contains CRUD keywords
- This routes the request to the appropriate handler

```python
    # Employee lookup priority:
    # 1. Search for name in current prompt
    # 2. Check session memory
    # 3. Use employee_id from request

    db = SessionLocal()
    mentioned_employees = []

    # Search for employee names in prompt
    all_employees = db.query(models.Employee).all()
    for e in all_employees:
        if e.name and e.name.lower() in req.prompt.lower():
            mentioned_employees.append(e)
```

**What this does:**
- We search the prompt for any known employee names
- This enables queries like "What is John's email?"
- Names mentioned in the prompt take priority over session context

```python
    # Anti-hallucination Guard #1: Ambiguous queries
    if has_action and not mentioned_employees and not is_list_query:
        return {
            "reply": "Could you specify which employee? Available: " +
                     ", ".join([e.name for e in all_employees[:10]]),
            "session_id": session_id
        }
```

**What this does:**
- If the user asks about "the employee" without specifying which one
- We ask for clarification instead of guessing
- This prevents hallucination from ambiguous queries

```python
    # Build context for LLM
    if emp:
        structured_data = f"""
=== EMPLOYEE DATABASE RECORD ===
Employee ID: {emp.employee_id}
Name: {emp.name}
Email: {emp.email}
Technical Skills: {emp.technical_skills}
Soft Skills: {emp.soft_skills}
===
"""
        # RAG: Get relevant chunks
        results = vectorstore.search(req.prompt, top_k=5, employee_id=emp.id)
        retrieved_text = "\n".join([r["text"] for r in results])
```

**What this does:**
- We build structured context from the database record
- We retrieve relevant text chunks via semantic search
- Both are included in the LLM prompt

```python
        # Anti-hallucination prompt
        context_instruction = """
=== CRITICAL ANTI-HALLUCINATION RULES ===
1. ONLY use information from the DATABASE RECORD and RESUME TEXT
2. If information is NOT available, say: 'That information is not available'
3. NEVER guess, infer, or fabricate information
4. Preface answers with 'Based on the records...'
===
"""
        prompt = context_instruction + structured_data + retrieved_text + "\n\nQuestion: " + req.prompt
```

**What this does:**
- We include explicit anti-hallucination instructions
- The LLM is grounded in the provided data
- This prevents making up information

```python
    # Generate response
    response = llm.generate(prompt)

    # Store in conversation history
    conversation_store[session_id].append({"role": "user", "content": req.prompt})
    conversation_store[session_id].append({"role": "assistant", "content": response})

    return {
        "reply": response,
        "session_id": session_id,
        "employee_id": emp.employee_id if emp else None
    }
```

**What this does:**
- We generate the response using the LLM
- We store both user and assistant messages in history
- We return the response with session tracking info

---

## 6. Frontend: React Application

### 6.1 App.jsx - Main Component

📄 **File:** `frontend/src/App.jsx`

**Purpose:** Main application component that displays chat messages.

```jsx
import React, { useState, useRef, useEffect } from "react"
import ReactMarkdown from "react-markdown"
import Upload from "./Upload"

export default function App() {
  const [messages, setMessages] = useState([])
  const chatRef = useRef(null)
```

**What this does:**
- We track messages in state (array of message objects)
- `chatRef` references the chat container for scrolling
- `useEffect` handles side effects (scrolling)

```jsx
  // Auto-scroll when messages change
  useEffect(() => {
    const el = chatRef.current
    if (!el) return
    const t = setTimeout(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
    }, 100)
    return () => clearTimeout(t)
  }, [messages])
```

**What this does:**
- When messages change, we scroll to the bottom
- `setTimeout` waits for DOM to update before scrolling
- `behavior: "smooth"` provides a nice animation

```jsx
  return (
    <div className="container">
      <h1>ChatBot</h1>
      <div className="chat" ref={chatRef}>
        {messages.slice().reverse().map((m, i) => {
          if (m.type === "assistant") {
            return (
              <div key={i} className="message assistant-message">
                <ReactMarkdown>{m.text}</ReactMarkdown>
                {m.responseTime && <span>{m.responseTime}s</span>}
              </div>
            )
          }
          // ... handle other message types
        })}
      </div>
      <Upload onNewMessage={(m) => setMessages((s) => [m, ...s])} />
    </div>
  )
}
```

**What this does:**
- We render messages in reverse order (newest first in array, but displayed bottom-up)
- `ReactMarkdown` renders LLM responses with formatting
- `Upload` component handles input and API calls
- `onNewMessage` callback adds new messages to state

---

### 6.2 Upload.jsx - File Upload & Chat

📄 **File:** `frontend/src/Upload.jsx`

**Purpose:** Handles file selection, upload, polling, and chat input.

```jsx
export default function Upload({ onNewMessage }) {
  const [file, setFile] = useState(null)
  const [prompt, setPrompt] = useState("")
  const [isProcessing, setIsProcessing] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [employeeId, setEmployeeId] = useState(null)
  const abortControllerRef = useRef(null)
```

**What this does:**
- `file` stores the selected PDF
- `sessionId` enables conversation memory
- `employeeId` tracks the current employee context
- `abortControllerRef` allows canceling requests

```jsx
  async function uploadAndWait(fileToUpload) {
    setIsProcessing(true)
    abortControllerRef.current = new AbortController()
    const signal = abortControllerRef.current.signal

    // Upload file
    const fd = new FormData()
    fd.append("file", fileToUpload)
    const res = await fetch(`${base}/api/upload-cv`, {
      method: "POST",
      body: fd,
      signal
    })
    const { job_id } = await res.json()
```

**What this does:**
- We create a FormData object for multipart upload
- `AbortController` enables cancellation via the stop button
- We POST to the upload endpoint and get a job ID

```jsx
    // Poll for completion
    while (true) {
      if (signal.aborted) return null

      const s = await fetch(`${base}/api/job/${job_id}`, { signal })
      const j = await s.json()

      if (j.status === "done") {
        setEmployeeId(j.employee_id)
        setIsProcessing(false)
        return j.employee_id
      }
      if (j.status === "failed") {
        onNewMessage({ type: "error", text: "Processing failed" })
        setIsProcessing(false)
        return null
      }

      await new Promise(r => setTimeout(r, 1000))  // Wait 1 second
    }
  }
```

**What this does:**
- We poll the job status endpoint every second
- When status is "done", we store the employee ID
- If aborted (stop button), we exit cleanly
- No timeout - we wait as long as needed for LLM processing

```jsx
  async function handleChat(e) {
    e.preventDefault()

    // If file selected, upload first
    if (file) {
      onNewMessage({ type: "attachment", filename: file.name })
      const newEmployeeId = await uploadAndWait(file)
      setFile(null)
    }

    // Send chat message
    if (prompt) {
      onNewMessage({ type: "user", text: prompt })

      const res = await fetch(`${base}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt,
          employee_id: employeeId,
          session_id: sessionId
        })
      })

      const json = await res.json()
      setSessionId(json.session_id)
      onNewMessage({ type: "assistant", text: json.reply })
    }
  }
```

**What this does:**
- If a file is selected, we upload and process it first
- Then we send the chat prompt with session and employee context
- We update session ID from the response (for conversation continuity)
- We display the assistant's response

---

## 7. Data Flow: End-to-End

### Flow 1: PDF Upload → Database

```
1. User selects PDF in browser
   └─▶ Upload.jsx: setFile(selectedFile)

2. User clicks Send
   └─▶ Upload.jsx: handleChat() → uploadAndWait()

3. Frontend POSTs to /api/upload-cv
   └─▶ main.py: upload_cv()
       ├── Read file bytes: contents = await file.read()
       ├── Save to storage: storage.save_file(contents)
       ├── Generate job_id: uuid.uuid4()
       └── Start thread: threading.Thread(target=process_cv)

4. Background thread runs process_cv()
   └─▶ main.py: process_cv()
       ├── Fetch file: storage.get_file(file_id)
       ├── Extract text: extract_text_from_bytes(data)
       ├── Create Employee record in PostgreSQL
       ├── Chunk text and index in FAISS
       ├── Send to LLM for extraction
       ├── Parse JSON response
       ├── Validate with Pydantic
       ├── Update Employee with extracted fields
       └── Write job status: {"status": "done", "employee_id": "000001"}

5. Frontend polls /api/job/{job_id}
   └─▶ Upload.jsx: while loop checking status
       └── When done: setEmployeeId(j.employee_id)

6. Data now stored in:
   ├── PostgreSQL: Employee record with all fields
   ├── MongoDB GridFS: Original PDF binary
   ├── MongoDB Collection: extracted_resumes (JSON)
   ├── FAISS: Vector embeddings of text chunks
   └── Local files: jobs/*.json, extracted/*.json
```

### Flow 2: Chat Query → Response

```
1. User types question and clicks Send
   └─▶ Upload.jsx: handleChat()

2. Frontend POSTs to /api/chat
   └─▶ main.py: chat()
       ├── Get/create session_id
       ├── Load conversation history

3. CRUD Detection
   └─▶ Check for keywords: "update", "delete", "create"
       └── If CRUD: route to CRUD handler

4. Employee Lookup (priority order)
   └─▶ 1. Search prompt for employee names
       2. Check session memory (active_employee_store)
       3. Use employee_id from request

5. Anti-Hallucination Guards
   └─▶ Guard 1: Ambiguous query? → Ask for clarification
       Guard 2: Short prompt? → Request more context
       Guard 3: Non-existent employee? → Return "not found"
       Guard 4: Leading question? → Don't confirm blindly
       Guard 5: Pressure/urgency? → Don't bypass checks
       Guard 6: No context? → Ask which employee

6. Build LLM Context
   └─▶ ├── Structured data from PostgreSQL
       ├── Relevant chunks from FAISS (RAG)
       ├── Conversation history
       └── Anti-hallucination instructions

7. Generate Response
   └─▶ llm.generate(prompt)

8. Store in Session Memory
   └─▶ conversation_store[session_id].append(...)

9. Return to Frontend
   └─▶ {"reply": "...", "session_id": "...", "employee_id": "..."}

10. Frontend displays response
    └─▶ App.jsx: ReactMarkdown renders the reply
```

---

## 8. Configuration Files

### Backend .env

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/ems

# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DB=cv_repo

# LLM
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_API_URL=http://localhost:11434/api/generate

# Server
HOST=0.0.0.0
PORT=8000
```

### Frontend .env

```env
VITE_API_BASE_URL=http://localhost:8000
```

### requirements.txt

```
fastapi          # Web framework
uvicorn          # ASGI server
sqlalchemy       # ORM
pydantic         # Validation
pymongo          # MongoDB driver
pdfplumber       # PDF extraction
pytesseract      # OCR (optional)
sentence-transformers  # Embeddings
faiss-cpu        # Vector database
requests         # HTTP client
python-dotenv    # Env file loading
python-multipart # File uploads
```

---

## Summary

### What We Built

| Component | Technology | Lines of Code |
|-----------|------------|---------------|
| FastAPI Backend | Python | ~1,500 |
| Database Models | SQLAlchemy | ~60 |
| Storage Service | MongoDB/GridFS | ~160 |
| LLM Adapter | Ollama | ~120 |
| Vector Store | FAISS | ~110 |
| PDF Extractor | pdfplumber | ~45 |
| Embeddings | sentence-transformers | ~35 |
| React Frontend | JavaScript | ~400 |

### Key Architectural Decisions

1. **Dual Database**: PostgreSQL for structured data, MongoDB for files
2. **Background Processing**: Threading for LLM calls (non-blocking uploads)
3. **RAG Architecture**: FAISS vector search for grounded responses
4. **Anti-Hallucination**: 6-layer guard system before LLM calls
5. **Graceful Fallbacks**: Every service has a fallback (MongoDB→filesystem, HTTP→CLI)
6. **Session Memory**: Conversation context for natural dialogue

---

*Last updated: February 3, 2026*
