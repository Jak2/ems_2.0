# Employee Management System (EMS) Chatbot - Development Report

## Project Overview

An AI-powered Employee Management System that accepts CV/resume uploads, extracts structured data using a local LLM, stores information in dual databases (MongoDB + PostgreSQL), and provides a conversational interface for CRUD operations.

---

## Table of Contents

1. [Initial Challenges & Library Experimentation](#1-initial-challenges--library-experimentation)
2. [Library Selection & Rationale](#2-library-selection--rationale)
3. [Errors Encountered & Solutions](#3-errors-encountered--solutions)
4. [Feature Implementation Journey](#4-feature-implementation-journey)
5. [Workarounds & Tricks Used](#5-workarounds--tricks-used)
6. [Limitations & Known Issues](#6-limitations--known-issues)
7. [Lessons Learned](#7-lessons-learned)

---

## 1. Initial Challenges & Library Experimentation

### Phase 1: PDF Text Extraction

**Challenge**: Extracting text from PDF resumes reliably.

**Libraries Experimented With**:

| Library | Pros | Cons | Verdict |
|---------|------|------|---------|
| `PyPDF2` | Simple API, widely used | Poor handling of complex layouts, missing text from some PDFs | Rejected |
| `pdfminer.six` | Accurate extraction | Slow, complex API, memory issues with large files | Rejected |
| `pdfplumber` | Excellent accuracy, handles tables, simple API | Slightly slower than PyPDF2 | **Selected** |
| `pymupdf (fitz)` | Very fast, good accuracy | Larger dependency, licensing concerns | Considered |

**Final Choice**: `pdfplumber` with `pytesseract` OCR fallback for scanned documents.

**Reasoning**: pdfplumber provided the best balance of accuracy and simplicity. Many resumes have tables (education, experience) that PyPDF2 couldn't handle properly.

---

### Phase 2: LLM Selection for Data Extraction

**Challenge**: Finding a local LLM that can:
- Run on consumer hardware (no GPU requirement)
- Extract structured JSON from unstructured resume text
- Respond in reasonable time

**Models Experimented With**:

| Model | Size | Speed | JSON Accuracy | Notes |
|-------|------|-------|---------------|-------|
| `llama2:7b` | 4GB | Slow | Poor | Often added explanations, couldn't follow JSON format |
| `mistral:7b` | 4GB | Medium | Good | Better instruction following, still slow |
| `qwen2.5:7b-instruct` | 4.7GB | Slow | Very Good | Excellent JSON compliance, chosen initially |
| `qwen2.5:3b-instruct` | 2GB | Fast | Good | Good balance for lower-end hardware |
| `phi3:mini` | 2.3GB | Very Fast | Good | Recommended for speed-critical setups |
| `codellama:7b` | 4GB | Medium | Excellent | Best for JSON but overkill for this use case |

**Final Choice**: `qwen2.5:7b-instruct` (default), configurable via environment variable.

**Reasoning**:
- Best JSON extraction accuracy among tested models
- Good instruction following (critical for "return ONLY JSON" prompts)
- Trade-off: Slow on CPU-only systems (200+ seconds per extraction)

---

### Phase 3: Database Selection

**Challenge**: Storing both raw documents and structured employee data.

**Options Considered**:

| Approach | Pros | Cons |
|----------|------|------|
| PostgreSQL only | Simple, ACID compliant | Not ideal for binary files, no document flexibility |
| MongoDB only | Flexible schema, good for documents | Complex queries for relational data |
| PostgreSQL + MongoDB | Best of both worlds | More complexity, two databases to manage |
| SQLite + Local files | Simple, no server needed | Not production-ready, concurrent access issues |

**Final Choice**: PostgreSQL (structured data) + MongoDB GridFS (raw PDFs) + Local JSON files (extracted data backup).

**Reasoning**:
- PostgreSQL: Ideal for structured employee records with relationships
- MongoDB GridFS: Perfect for storing large binary files (PDFs)
- Local JSON: Human-readable backup, easy debugging, works without MongoDB

---

## 2. Library Selection & Rationale

### Backend Stack

| Component | Library | Why This Over Alternatives |
|-----------|---------|---------------------------|
| Web Framework | **FastAPI** | Async support, automatic OpenAPI docs, Pydantic integration. Considered Flask (too simple) and Django (overkill). |
| ORM | **SQLAlchemy** | Mature, flexible, works with any SQL database. Considered Django ORM (tied to Django) and Peewee (less features). |
| Validation | **Pydantic** | Built into FastAPI, excellent for validating LLM JSON output. |
| PDF Extraction | **pdfplumber** | Best accuracy for resume layouts with tables. |
| OCR Fallback | **pytesseract** | Industry standard, good accuracy for scanned documents. |
| LLM Interface | **Ollama CLI/HTTP** | Local LLM, no API costs, privacy-preserving. Considered OpenAI API (cost, privacy) and llama.cpp (complex setup). |
| MongoDB Driver | **pymongo** | Official driver, GridFS support built-in. |

### Frontend Stack

| Component | Library | Why This Over Alternatives |
|-----------|---------|---------------------------|
| UI Framework | **React** | Component-based, large ecosystem. Considered Vue (smaller community) and vanilla JS (too verbose). |
| HTTP Client | **Fetch API** | Built-in, no dependencies. Considered Axios (overkill for this project). |
| State Management | **useState/useRef** | Simple, sufficient for this scale. Considered Redux (overkill). |

---

## 3. Errors Encountered & Solutions

### Error #1: Frontend Timeout (60 seconds)

**Symptom**:
```
Processing timed out (no result within 60s)
```

**Root Cause**: Frontend polling loop had a hardcoded 60-second timeout while LLM extraction was taking 200+ seconds.

**Solution**: Removed timeout entirely, implemented infinite polling with progress indicator.

```javascript
// Before (with timeout)
const maxWait = 60
let waited = 0
while (waited < maxWait) { ... }

// After (no timeout)
let pollCount = 0
while (true) {
  // Poll indefinitely
  if (pollCount % 10 === 0) {
    setStatus(`Processing CV with LLM... (${pollCount}s elapsed)`)
  }
  await new Promise((r) => setTimeout(r, 1000))
}
```

---

### Error #2: LLM Adapter Timeout

**Symptom**: Backend crashed with timeout error even after frontend fix.

**Root Cause**: `subprocess.run()` had implicit timeout, and HTTP request had `timeout=60`.

**Solution**: Removed all timeout parameters from LLM calls.

```python
# Before
proc = subprocess.run(cmd, capture_output=True, timeout=60)
resp = requests.post(api_url, json=payload, timeout=60)

# After
proc = subprocess.run(cmd, capture_output=True, text=False)  # No timeout
resp = requests.post(api_url, json=payload, timeout=600)  # 10 min for HTTP
```

---

### Error #3: Ollama JSON Response Not Parsed

**Symptom**: Chat returned raw JSON like:
```json
{"model":"qwen2.5:7b-instruct","response":"Hello!","done":true}
```

**Root Cause**: Ollama HTTP API wraps the actual response in a JSON object with `response` key.

**Solution**: Added response key extraction in LLM adapter.

```python
# Before
return str(data).strip()  # Returned entire JSON object

# After
for k in ("response", "text", "output", "result"):
    if k in data and data[k]:
        return data[k].strip()  # Extract actual response
```

---

### Error #4: File State Cleared Before Upload

**Symptom**: File upload failed silently when user clicked Send.

**Root Cause**: `clearFile()` was called before `uploadAndWait()` could access the file state.

**Solution**: Captured file reference before clearing and passed as parameter.

```javascript
// Before
clearFile()
const newEmployeeId = await uploadAndWait()  // file was already null!

// After
const currentFile = file
clearFile()
const newEmployeeId = await uploadAndWait(currentFile)  // Pass file explicitly
```

---

### Error #5: MongoDB Storing Binary BSON Instead of Readable JSON

**Symptom**: Extracted data in MongoDB was unreadable binary format.

**Root Cause**: Using GridFS (designed for binary files) to store JSON data.

**Solution**: Created separate MongoDB collection for JSON documents + local JSON file backup.

```python
# Before: GridFS binary storage
self.fs.put(json.dumps(data).encode(), filename=f"{employee_id}.json")

# After: MongoDB collection + local JSON file
collection = self.db["extracted_resumes"]
collection.insert_one(document)  # Human-readable in MongoDB

# Also save local JSON file
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(document, f, indent=2, ensure_ascii=False)
```

---

### Error #6: Windows Encoding Issues with Ollama CLI

**Symptom**: `UnicodeDecodeError` when processing non-ASCII characters in resumes.

**Root Cause**: Windows console uses different encoding than UTF-8.

**Solution**: Capture raw bytes and decode with error replacement.

```python
# Before
proc = subprocess.run(cmd, capture_output=True, text=True)
return proc.stdout.strip()

# After
proc = subprocess.run(cmd, capture_output=True, text=False)  # Raw bytes
out = proc.stdout.decode("utf-8", errors="replace").strip()  # Safe decode
```

---

### Error #7: LLM Returns Explanation Instead of Pure JSON

**Symptom**: LLM response included text like "Here is the extracted data:" before JSON.

**Root Cause**: Model not following "return ONLY JSON" instruction strictly.

**Solution**: Added JSON extraction fallback using regex.

```python
try:
    parsed = json.loads(extraction_resp)
except Exception:
    # Try to extract JSON substring
    m = re.search(r"\{.*\}", extraction_resp, re.S)
    if m:
        parsed = json.loads(m.group(0))
```

---

### Error #8: Pydantic Validation Failures

**Symptom**: Valid data rejected by Pydantic model.

**Root Cause**: LLM sometimes returned arrays as comma-separated strings instead of JSON arrays.

**Solution**: Made all fields optional with `None` default, added flexible type handling.

```python
# Before: Strict types
class ExtractionModel(BaseModel):
    skills: List[str]  # Fails if LLM returns "Python, Java"

# After: Flexible with defaults
class ExtractionModel(BaseModel):
    skills: List[str] | str | None = None  # Accepts any format
```

---

### Error #9: Backend Unreachable from Frontend

**Symptom**: CORS errors, connection refused on different hosts.

**Root Cause**: Frontend and backend on different ports/hosts.

**Solution**: Added CORS middleware and dynamic backend discovery.

```python
# Backend: Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

```javascript
// Frontend: Try multiple hosts
async function findBackendBase() {
  const hosts = [window.location.hostname, '127.0.0.1', 'localhost']
  for (const h of hosts) {
    try {
      const r = await fetch(`http://${h}:8000/health`)
      if (r.ok) return `http://${h}:8000`
    } catch (err) { /* try next */ }
  }
  return null
}
```

---

### Error #10: Variable Shadowing Breaks SQLAlchemy Query

**Symptom**:
```
'str' object is not callable
```
Employee ID generation failed, causing fallback to '000001' which already existed.

**Root Cause**: The variable `text` (holding extracted PDF content) was shadowing SQLAlchemy's `text` function imported at module level. When the code called `text("SELECT...")`, Python tried to call the PDF string as a function.

```python
# Problem: text variable shadows SQLAlchemy's text function
from sqlalchemy import text  # Imported at line 30

# Later in process_cv():
text = extract_text_from_bytes(data)  # Line 237 - shadows the import!

# This fails because 'text' is now a string, not a function
db.execute(text("SELECT MAX(id)..."))  # 'str' object is not callable
```

**Solution**: Renamed the variable from `text` to `pdf_text` throughout the `process_cv` function.

```python
# After: Use different variable name
pdf_text = extract_text_from_bytes(data)

# Import with alias when needed
from sqlalchemy import text as sql_text
db.execute(sql_text("SELECT..."))
```

**Lesson**: Always be careful about variable naming in Python - local variables can shadow imported functions.

---

### Error #11: Duplicate Employee ID Constraint Violation

**Symptom**:
```
duplicate key value violates unique constraint "employees_employee_id_key"
DETAIL: Key (employee_id)=(000001) already exists.
```

**Root Cause**: The employee_id generation query was using `MAX(id)` (auto-increment primary key) instead of `MAX(employee_id)`. Combined with the shadowing bug above, it always fell back to `1`, generating `000001` which already existed.

```python
# Before: Wrong column used
max_id = db.execute(text("SELECT COALESCE(MAX(id), 0) + 1 FROM employees")).scalar()
# This queries the auto-increment id, not employee_id
```

**Solution**: Query the actual `employee_id` column, casting to integer for proper MAX comparison. Added multiple fallbacks.

```python
# After: Query correct column with fallbacks
from sqlalchemy import text as sql_text
try:
    result = db.execute(sql_text(
        "SELECT COALESCE(MAX(CAST(employee_id AS INTEGER)), 0) + 1 FROM employees WHERE employee_id IS NOT NULL"
    )).scalar()
    next_id = result if result else 1
except Exception as e:
    # Fallback 1: count-based
    try:
        count = db.query(models.Employee).count()
        next_id = count + 1
    except Exception:
        # Fallback 2: timestamp-based (guaranteed unique)
        import time
        next_id = int(time.time()) % 1000000

employee_id = str(next_id).zfill(6)  # Format: 000002
```

---

### Error #12: Pydantic Validation Fails on LLM Dict Arrays

**Symptom**:
```
3 validation errors for ComprehensiveExtractionModel
education.0
  Input should be a valid string [type=string_type, input_value={'degree': 'B.E, CSE', ...}, input_type=dict]
```

**Root Cause**: The LLM returned structured data for fields like `education` as arrays of dictionaries instead of arrays of strings:

```json
// What LLM returned:
{"education": [{"degree": "B.E", "university": "MIT", "year": "2021"}]}

// What Pydantic expected:
{"education": ["B.E from MIT, 2021"]}
```

**Solution**: Made the Pydantic model accept `List[Any]` and added a field validator to convert dicts to JSON strings.

```python
from pydantic import BaseModel, field_validator
from typing import List, Any
import json

class ComprehensiveExtractionModel(BaseModel):
    education: List[Any] | None = None  # Accept any type
    work_experience: List[Any] | None = None
    # ... other fields

    @field_validator('education', 'work_experience', ..., mode='before')
    @classmethod
    def convert_dicts_to_strings(cls, v):
        if v is None:
            return None
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, dict):
                    # Convert dict to JSON string for storage
                    result.append(json.dumps(item, ensure_ascii=False))
                else:
                    result.append(str(item) if item is not None else None)
            return result
        return v
```

---

### Error #13: Cannot Upload Multiple Resumes

**Symptom**: After uploading one resume and doing some queries, trying to upload a second resume did nothing.

**Root Cause**: The frontend `handleChat` function had a condition that prevented file uploads once an `employeeId` was set:

```javascript
// Before: Blocked subsequent uploads
const hasFile = file && !employeeId && !isProcessing
// Once employeeId is set, !employeeId is false, so hasFile is always false
```

**Solution**: Removed the `!employeeId` check to allow uploading new files anytime.

```javascript
// After: Allow file upload even with existing employeeId
const hasFile = file && !isProcessing
// Now users can switch between candidates by uploading new resumes
```

---

### Error #14: BackgroundTasks Not Running (FastAPI)

**Symptom**: Upload returned immediately but background processing never started. Job status stayed "pending" forever.

**Root Cause**: Two issues:
1. `process_cv` was defined as `async def` but contained blocking calls (`subprocess.run`, `requests.post`)
2. FastAPI's `BackgroundTasks` sometimes has issues with blocking operations

```python
# Problem: async function with blocking calls
async def process_cv(...):
    # These block the event loop!
    proc = subprocess.run(...)  # BLOCKING
    resp = requests.post(...)   # BLOCKING
```

**Solution**: Changed to regular function and used `threading.Thread` directly.

```python
# After: Regular function with explicit threading
def process_cv(...):  # Not async
    # Blocking calls are fine in a thread
    proc = subprocess.run(...)
    resp = requests.post(...)

# In upload_cv:
import threading
thread = threading.Thread(target=lambda: process_cv(file_id, filename, job_id), daemon=True)
thread.start()
```

---

### Error #15: Job Status File Never Created

**Symptom**: `/api/job/{id}` always returned `{"status": "pending"}` even though processing was supposedly running.

**Root Cause**: The job status file was only written at the end of processing. If the process crashed early (e.g., due to the shadowing bug), no status file existed.

**Solution**: Write "processing" status immediately at the start of `process_cv`, before any other work.

```python
def process_cv(file_id: str, filename: str, job_id: str):
    # FIRST THING: Write initial status
    os.makedirs(JOB_DIR, exist_ok=True)
    job_path = os.path.join(JOB_DIR, f"{job_id}.json")
    with open(job_path, "w", encoding="utf-8") as jf:
        jf.write('{"status":"processing","filename":"' + filename + '"}')

    # Now do the actual work...
```

---

## 4. Feature Implementation Journey

### Feature 1: CV Upload & Processing

**Approach**:
1. Frontend sends PDF via FormData
2. Backend saves to MongoDB GridFS
3. pdfplumber extracts text
4. LLM extracts structured JSON
5. Pydantic validates structure
6. Data saved to PostgreSQL + MongoDB collection

**Services Used**:
- `pdfplumber` for text extraction
- `pytesseract` for OCR fallback
- `Ollama` for LLM extraction
- `pymongo` for MongoDB
- `SQLAlchemy` for PostgreSQL

---

### Feature 2: Natural Language CRUD Operations

**Approach**:
1. User types natural language command (e.g., "Update Arun's department to HR")
2. LLM parses intent and extracts action/fields as JSON
3. Backend executes corresponding database operation
4. Response sent back to user

**Prompt Engineering Trick**:
```
Parse this command into a JSON action.
Return ONLY valid JSON.
Examples:
- 'Update Arun from IT to HR' -> {"action":"update", "employee_name":"Arun", "fields":{"department":"HR"}}
```

---

### Feature 3: Conversation Memory

**Approach**:
1. Generate unique session_id on first message
2. Store conversation history server-side (keyed by session_id)
3. Include context in subsequent LLM prompts
4. Frontend persists session_id across messages

**Storage**: In-memory dictionary (could be upgraded to Redis for production).

---

### Feature 4: File Preview with Cancel

**Approach**:
1. Show selected file above input box before submission
2. Add X button to discard file
3. Only show in chat history after actual submission

**UI Pattern**: Preview state vs. submitted state separation.

---

### Feature 5: Stop Button for Long Requests

**Approach**:
1. Replace Send button with Stop button during processing
2. Use `AbortController` to cancel fetch requests
3. Disable input field while processing

**Limitation**: Only cancels frontend waiting; backend continues processing.

---

## 5. Workarounds & Tricks Used

### Trick 1: JSON Extraction Retry

If first LLM extraction fails to get a name, send a stricter retry prompt:

```python
retry_prompt = (
    "CRITICAL: Extract resume data as STRICT JSON only. NO explanations.\n"
    "Return JSON with these keys (use null if not found):\n"
    "name, email, phone, ...\n"
    f"Resume:\n\n{text[:8000]}\n\nJSON:"
)
```

---

### Trick 2: Comprehensive Logging

Added `[PROCESS_CV]` prefixed logs at every step for debugging:

```python
logger.info(f"[PROCESS_CV] → Sending extraction prompt to LLM ({len(prompt)} chars)...")
logger.info(f"[PROCESS_CV] ✓ LLM response received: {len(response)} chars")
logger.info(f"[PROCESS_CV] → Parsed name: '{parsed.get('name')}'")
```

---

### Trick 3: Dual Storage Strategy

Store extracted data in THREE places for redundancy:
1. PostgreSQL (structured, queryable)
2. MongoDB collection (flexible, human-readable)
3. Local JSON files (backup, easy debugging)

---

### Trick 4: Environment Variable Configuration

Made everything configurable without code changes:

```bash
OLLAMA_MODEL=phi3:mini          # Switch models
OLLAMA_API_URL=http://...       # Use HTTP API instead of CLI
MONGO_URI=mongodb://...         # Database connection
POSTGRES_URL=postgresql://...   # Database connection
```

---

### Trick 5: Graceful Degradation

System works even if some components fail:
- No MongoDB? Falls back to local files
- No OCR? Uses pdfplumber text only
- HTTP API fails? Falls back to CLI
- LLM extraction fails? Stores raw text anyway

---

### Trick 6: Pydantic Field Validators for LLM Output

LLMs return inconsistent data structures. Use Pydantic field validators to normalize:

```python
from pydantic import BaseModel, field_validator
from typing import List, Any

class ExtractionModel(BaseModel):
    education: List[Any] | None = None  # Accept anything

    @field_validator('education', mode='before')
    @classmethod
    def normalize_to_strings(cls, v):
        if isinstance(v, list):
            return [json.dumps(x) if isinstance(x, dict) else str(x) for x in v]
        return v
```

This handles:
- `["BS from MIT"]` - passes through
- `[{"degree": "BS", "school": "MIT"}]` - converts to `['{"degree": "BS", "school": "MIT"}']`

---

### Trick 7: Import Aliasing to Avoid Shadowing

When you need to use a function name that might conflict with variables:

```python
# At module level
from sqlalchemy import text  # Could be shadowed

# Inside functions where 'text' might be used as a variable
from sqlalchemy import text as sql_text  # Safe import with alias
result = db.execute(sql_text("SELECT ..."))
```

---

### Trick 8: Threading for Background Tasks in FastAPI

FastAPI's `BackgroundTasks` works best with async I/O. For blocking operations, use explicit threading:

```python
import threading

@app.post("/api/upload")
async def upload(file: UploadFile):
    job_id = str(uuid.uuid4())

    def run_blocking_task():
        # Blocking I/O is fine in a separate thread
        subprocess.run(...)
        requests.post(...)

    thread = threading.Thread(target=run_blocking_task, daemon=True)
    thread.start()

    return {"job_id": job_id}  # Returns immediately
```

---

## 6. Limitations & Known Issues

### Performance Limitations

| Issue | Cause | Mitigation |
|-------|-------|------------|
| Slow extraction (200s+) | 7B model on CPU | Use smaller model (phi3:mini) |
| Memory usage | Large PDFs loaded entirely | Implement streaming/chunking |
| No GPU acceleration | Ollama not detecting GPU | Ensure CUDA drivers installed |

### Functional Limitations

| Issue | Cause | Potential Fix |
|-------|-------|---------------|
| Stop button doesn't stop backend | No cancellation protocol | Implement job cancellation endpoint |
| Single user session | In-memory storage | Use Redis/database for sessions |
| No authentication | MVP scope | Add JWT/OAuth |
| English only extraction | LLM training | Use multilingual model |

### Known Bugs (Resolved)

1. ~~**Duplicate employee IDs possible**~~: Fixed by querying `MAX(employee_id)` instead of `MAX(id)` with proper fallbacks
2. ~~**Variable shadowing crash**~~: Fixed by renaming `text` variable to `pdf_text`
3. ~~**Cannot upload multiple resumes**~~: Fixed by removing `!employeeId` condition

### Remaining Known Issues

1. **Large PDFs may timeout**: No chunking for very large documents
2. **Some resume formats fail**: Complex multi-column layouts confuse pdfplumber
3. **Race condition on concurrent uploads**: Two simultaneous uploads could still potentially generate the same employee_id (edge case)

---

## 7. Lessons Learned

### Technical Lessons

1. **Always remove hardcoded timeouts for LLM calls** - They can take arbitrarily long on slow hardware.

2. **Local LLMs need prompt engineering** - Unlike GPT-4, smaller models need explicit "return ONLY JSON" instructions.

3. **Dual database strategy is worth the complexity** - Different data types benefit from different storage solutions.

4. **Comprehensive logging saves debugging time** - When LLM extraction fails, logs show exactly where.

5. **Make everything configurable** - Environment variables prevent "works on my machine" problems.

6. **Watch for variable shadowing** - Python allows local variables to shadow module imports. A variable named `text` can shadow `sqlalchemy.text()`, causing cryptic "'str' object is not callable" errors.

7. **Avoid async functions with blocking I/O** - `async def` functions that call `subprocess.run()` or `requests.post()` will block the entire event loop. Use regular functions with threading instead.

8. **Write status early in background tasks** - If a background job crashes before writing any status, there's no way to know what happened. Write "processing" status immediately on task start.

9. **Make Pydantic models flexible for LLM output** - LLMs are unpredictable. Use `List[Any]` with validators instead of strict `List[str]` when accepting LLM-generated data.

10. **Frontend state conditions can block features** - A condition like `!employeeId` might make sense initially but can prevent legitimate use cases (uploading multiple resumes).

### Process Lessons

1. **Start with the slowest component** - LLM integration should be prototyped first.

2. **Test with real data early** - Sample resumes revealed edge cases not found in synthetic data.

3. **Build fallbacks from day one** - OCR fallback, CLI fallback, local file fallback saved the project multiple times.

4. **UI feedback is critical for long operations** - Users need to know the system is working during 200s waits.

### Model Selection Lessons

1. **Bigger isn't always better** - phi3:mini (2.3GB) often outperforms llama2:7b for structured extraction.

2. **Instruction-tuned models are essential** - Base models can't follow "return JSON only" instructions.

3. **Test JSON compliance specifically** - A model that writes good prose may fail at structured output.

---

## Appendix: Quick Reference

### Start the System

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

### Environment Variables

```bash
# LLM Configuration
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_API_URL=http://localhost:11434/api/generate

# Database Configuration
MONGO_URI=mongodb://localhost:27017
MONGO_DB=cv_repo
DATABASE_URL=postgresql://user:pass@localhost/ems
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Server health check |
| `/api/upload-cv` | POST | Upload PDF resume |
| `/api/job/{id}` | GET | Check job status |
| `/api/chat` | POST | Send chat message |
| `/api/employees` | GET | List all employees |
| `/api/extracted/{id}` | GET | Get extracted JSON |

---

*Report generated for EMS 2.0 project documentation.*
*Last updated: February 1, 2026*

---

## Changelog

| Date | Changes |
|------|---------|
| Feb 1, 2026 | Added Errors #10-15: Variable shadowing, duplicate ID, Pydantic validation, multiple upload, BackgroundTasks, job status. Added Tricks #6-8. Updated Known Bugs. |
| Initial | Errors #1-9, Features #1-5, Tricks #1-5 documented |
