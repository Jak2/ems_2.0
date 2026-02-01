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

### Known Bugs

1. **Duplicate employee IDs possible**: Race condition if two uploads happen simultaneously
2. **Large PDFs may timeout**: No chunking for very large documents
3. **Some resume formats fail**: Complex multi-column layouts confuse pdfplumber

---

## 7. Lessons Learned

### Technical Lessons

1. **Always remove hardcoded timeouts for LLM calls** - They can take arbitrarily long on slow hardware.

2. **Local LLMs need prompt engineering** - Unlike GPT-4, smaller models need explicit "return ONLY JSON" instructions.

3. **Dual database strategy is worth the complexity** - Different data types benefit from different storage solutions.

4. **Comprehensive logging saves debugging time** - When LLM extraction fails, logs show exactly where.

5. **Make everything configurable** - Environment variables prevent "works on my machine" problems.

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
*Last updated: February 2026*
