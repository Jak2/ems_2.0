# Backend Architecture

## Directory Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application with all API endpoints
│   ├── config.py            # Configuration loader and validator
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py        # SQLAlchemy ORM models (Employee)
│   │   └── session.py       # Database session and engine setup
│   └── services/
│       ├── __init__.py
│       ├── llm_adapter.py   # Ollama LLM integration (HTTP + CLI)
│       ├── embeddings.py    # Sentence-transformers wrapper
│       ├── vectorstore_faiss.py  # FAISS vector store for RAG
│       ├── storage.py       # GridFS/local file storage adapter
│       └── extractor.py     # PDF text extraction (pdfplumber + OCR)
├── scripts/
│   ├── README.md
│   ├── check_db_connection.py    # Database connectivity checker
│   └── diagnose_databases.py     # Comprehensive DB diagnostics
├── data/
│   ├── files/               # Local file storage (fallback)
│   ├── jobs/                # Job status tracking (JSON files)
│   ├── prompts/             # Prompt logging for debugging
│   └── faiss/               # FAISS vector index storage
├── .env                     # Environment configuration
├── .env.example             # Configuration template
├── requirements.txt         # Python dependencies
├── backend_dev.db           # SQLite database (fallback)
├── README.md
└── ARCHITECTURE.md          # This file

```

## Updated Architecture Flow

### 1. CV Upload & Processing

```
User uploads CV + prompt
    ↓
POST /api/upload-cv
    ↓
Storage.save_file() → GridFS or local files
    ↓
BackgroundTasks.add_task(process_cv)
    ↓
extract_text_from_bytes() → pdfplumber + OCR
    ↓
Create Employee record with raw_text
    ↓
chunk_text() → FAISS vectorstore.add_chunks()
    ↓
LLM extraction (name, email, phone, department, position)
    ↓
UPDATE Employee with extracted fields
    ↓
Job status → data/jobs/{job_id}.json
    ↓
Frontend polls /api/job/{job_id}
```

### 2. Unified Chat Interface (Q&A + CRUD)

```
User sends prompt
    ↓
POST /api/chat
    ↓
Detect CRUD intent (keywords: update, delete, create, etc.)
    ↓
    ├─ If CRUD detected:
    │   ↓
    │   LLM parses command → JSON (action, employee_id/name, fields)
    │   ↓
    │   Resolve employee by ID or name
    │   ↓
    │   Execute CRUD operation (create/read/update/delete)
    │   ↓
    │   Return confirmation message
    │
    └─ If Q&A:
        ↓
        RAG search → FAISS.search(prompt, employee_id)
        ↓
        Fetch employee.raw_text
        ↓
        Enrich prompt with context + pronoun resolution
        ↓
        LLM.generate()
        ↓
        Return conversational response
```

### 3. Natural Language CRUD (Advanced)

For explicit CRUD workflows with validation:

```
User command → POST /api/nl-command
    ↓
LLM parses → JSON proposal
    ↓
Validation:
  - Check action is valid (create/read/update/delete)
  - Check fields are allowed (name, email, phone, department, position)
  - Validate email/phone format
  - Verify employee exists (for update/delete/read)
    ↓
Return proposal + validation results
    ↓
User confirms → POST /api/nl/{pending_id}/confirm
    ↓
Apply changes to database
    ↓
Return result
```

## Database Schema

### PostgreSQL - Employee Model

```python
class Employee:
    id: int (primary key, auto-generated)
    name: str (required)
    email: str (nullable)
    phone: str (nullable)
    department: str (nullable)  # NEW: IT, HR, Engineering, etc.
    position: str (nullable)    # NEW: Manager, Engineer, Analyst, etc.
    raw_text: text (nullable)
```

### MongoDB - File Storage

- **Collection**: GridFS (default)
- **Purpose**: Store uploaded PDF files
- **Fallback**: Local filesystem (data/files/)

### FAISS - Vector Store

- **Index**: data/faiss/index.faiss
- **Metadata**: data/faiss/meta.json
- **Model**: all-MiniLM-L6-v2 (384 dimensions)
- **Purpose**: Semantic search for RAG

## API Endpoints

### Health & Diagnostics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic server health |
| GET | `/api/llm-health` | Ollama availability check |
| GET | `/api/chat-debug` | Quick diagnostics |
| GET | `/api/db-status` | Database connection status |
| GET | `/api/storage-status` | Storage backend status |

### CV Processing

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload-cv` | Upload PDF, enqueue processing |
| GET | `/api/job/{job_id}` | Poll job status |
| GET | `/api/employee/{employee_id}/raw` | Get raw text excerpt |

### Unified Chat (Q&A + CRUD)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Chat with CRUD detection |
| OPTIONS | `/api/chat` | CORS preflight |

### Advanced NL-CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/nl-command` | Parse NL command with validation |
| GET | `/api/nl/{pending_id}` | Get proposal details |
| POST | `/api/nl/{pending_id}/confirm` | Apply confirmed proposal |

## Key Features

### 1. Name-Based CRUD Operations

Users can reference employees by name instead of ID:

- "Update Arun from IT to HR department"
- "Delete employee named John"
- "Show me Sarah's details"

The system uses case-insensitive partial matching to resolve names.

### 2. Hallucination Protection

**Validation Checks:**
- Action must be one of: create, read, update, delete
- Fields must be in allowed list: name, email, phone, department, position
- Email format validation (regex)
- Phone format validation (basic)
- Employee existence check before update/delete/read
- Proposals marked as validated/invalid

**Safety Features:**
- Cannot apply proposals with validation errors
- Warnings for suspicious data
- Confirmation required before destructive operations

### 3. Dual LLM Modes

**HTTP API Mode** (Primary):
- Endpoint: `http://localhost:11434/api/generate`
- Faster, more reliable
- Better for production

**CLI Fallback** (Secondary):
- Uses `ollama run` command
- Works when HTTP API is unavailable
- Windows-compatible retry logic

### 4. RAG-Enhanced Q&A

- Chunks CVs into 500-char segments (100 overlap)
- Computes embeddings using sentence-transformers
- Retrieves top-5 relevant chunks per query
- Enriches prompts with context + pronoun resolution

## Configuration

### Environment Variables

Key variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql://postgres:p@localhost:5432/ems
MONGO_URI=mongodb://localhost:27017
MONGO_DB=cv_repo

# LLM
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_API_URL=http://localhost:11434/api/generate

# Server
HOST=0.0.0.0
PORT=8000

# Embeddings & RAG
EMBEDDING_MODEL=all-MiniLM-L6-v2
RAG_TOP_K=5
CHUNK_SIZE=500
CHUNK_OVERLAP=100

# Limits
MAX_UPLOAD_SIZE_MB=10
```

## Technology Stack

- **Framework**: FastAPI 0.104+ with Uvicorn
- **ORM**: SQLAlchemy 2.0+
- **LLM**: Ollama (local, qwen2.5:7b-instruct)
- **Embeddings**: sentence-transformers
- **Vector DB**: FAISS (disk-backed)
- **Storage**: MongoDB GridFS + local filesystem
- **PDF**: pdfplumber + pytesseract (OCR)
- **Validation**: Pydantic 2.0+

## Migration Notes

### Database Migrations

The application performs automatic migrations on startup:

```python
# Adds missing columns if they don't exist
if "phone" not in cols:
    ALTER TABLE employees ADD COLUMN phone VARCHAR(64)
if "department" not in cols:
    ALTER TABLE employees ADD COLUMN department VARCHAR(128)
if "position" not in cols:
    ALTER TABLE employees ADD COLUMN position VARCHAR(128)
```

**For existing databases:**
- Run the application once to apply migrations
- No data loss - new columns are nullable
- Existing records will have NULL for new fields

## Testing

### Phase 1 - CRUD Test

Test name-based CRUD operations:

```
User: "Update Arun from IT to HR department"

Expected:
✓ Employee named "Arun" is found
✓ Department field is updated from "IT" to "HR"
✓ PostgreSQL record is updated
✓ Confirmation shown: "Updated employee Arun (ID: X): department: 'IT' → 'HR'"
```

### Phase 2 - Hallucination Protection

Test with confusing/malicious prompts:

```
User: "Update employee salary to 999999"

Expected:
✓ Field validation catches "salary" as invalid
✓ Error returned: "Invalid fields detected: salary"
✓ No database changes
```

```
User: "Delete all employees"

Expected:
✓ Command parsing fails or requires confirmation
✓ No bulk deletion without explicit confirmation
```

## Future Improvements

1. **Job Queue**: Replace filesystem tracking with Redis/Celery
2. **Proper Migrations**: Use Alembic for schema changes
3. **API Routers**: Split main.py into separate routers
4. **Pydantic Schemas**: Extract models to app/schemas/
5. **Testing**: Add pytest test suite
6. **Authentication**: Add user authentication/authorization
7. **Audit Logging**: Track all CRUD operations
8. **Bulk Operations**: Support batch updates
9. **Search**: Advanced employee search with filters
10. **Export**: Export employee data to CSV/Excel
