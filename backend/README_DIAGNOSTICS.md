# Backend Diagnostics Guide

## Quick Health Check

If you suspect the backend is not communicating with the database or other services, run the diagnostic script:

### Windows (PowerShell)

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python check_db_connection.py
```

### Linux/Mac

```bash
cd backend
source .venv/bin/activate
python check_db_connection.py
```

## What It Tests

The diagnostic script verifies:

### 1. Database Connection
- ✓ Tests SQLAlchemy connection
- ✓ Verifies `employees` table exists
- ✓ Checks all required columns (id, name, email, phone, raw_text)
- ✓ Runs full CRUD cycle (create/read/update/delete test record)

### 2. Storage Backend
- ✓ Identifies storage type (GridFS or filesystem)
- ✓ Tests file save operation
- ✓ Tests file retrieve operation
- ✓ Verifies MongoDB connection (if MONGO_URI set)

### 3. LLM Adapter
- ✓ Tests Ollama connectivity
- ✓ Verifies model response
- ✓ Checks HTTP endpoint (if OLLAMA_API_URL set)
- ✓ Falls back to CLI if needed

## Sample Output

```
============================================================
BACKEND CONNECTIVITY DIAGNOSTIC
============================================================

This script checks:
  1. Database connection (SQLAlchemy)
  2. Storage backend (GridFS or filesystem)
  3. LLM adapter (Ollama)

============================================================
DATABASE CONNECTION CHECK
============================================================

✓ Database URL: sqlite:///./backend_dev.db
✓ Database connection: SUCCESS

✓ Tables found: ['employees']
✓ 'employees' table exists
  Columns: ['id', 'name', 'email', 'raw_text', 'phone']

============================================================
CRUD OPERATIONS TEST
============================================================

✓ Current employee count: 5
✓ CREATE: Created test employee with id=6
✓ READ: Successfully fetched employee id=6, name=Test Employee (Diagnostic)
✓ UPDATE: Updated email to updated@diagnostic.local
✓ DELETE: Removed test employee

✓ Final employee count: 5

============================================================
STORAGE BACKEND CHECK
============================================================

✓ Storage backend: Storage
⚠ MONGO_URI not set - using filesystem fallback
  Files will be stored in: D:\delete me later\ems_2.0\backend\data\files

✓ SAVE: Saved test file with id=diagnostic_test.txt
✓ RETRIEVE: Successfully retrieved test file

============================================================
LLM ADAPTER CHECK
============================================================

✓ LLM Model: qwen2.5:latest
✓ OLLAMA_API_URL: http://localhost:11434/api/generate

Testing LLM generation (5s timeout)...
✓ LLM Response: DIAGNOSTIC_OK - All systems operational.
✓ LLM is responding correctly

============================================================
SUMMARY
============================================================
✓ PASS - Database
✓ PASS - Storage
✓ PASS - LLM

✓ All checks passed! Backend is ready.
```

## Common Issues & Fixes

### Database Issues

**Error**: `Table 'employees' NOT FOUND`
```
Fix: Start the backend once to auto-create tables
     uvicorn app.main:app --reload
```

**Error**: `Database connection FAILED`
```
Fix: Check DATABASE_URL environment variable
     Default is SQLite - should work out of box
     For Postgres: export DATABASE_URL="postgresql://user:pass@localhost/dbname"
```

**Error**: `Missing columns: ['phone']`
```
Fix: Run a migration or let the app auto-add the column
     The app attempts to ALTER TABLE on startup
```

### Storage Issues

**Error**: `GridFS NOT initialized (check MONGO_URI)`
```
Fix: If you want GridFS, set MONGO_URI:
     $env:MONGO_URI = "mongodb://localhost:27017/cv_chat"
     
     Otherwise, filesystem fallback works fine for PoC
```

**Error**: `Storage test failed: [Errno 13] Permission denied`
```
Fix: Ensure data/files/ directory has write permissions
     mkdir data\files (PowerShell)
```

### LLM Issues

**Error**: `LLM generation failed: Connection refused`
```
Fix: Start Ollama server
     ollama serve
     
     Or check if running:
     curl http://localhost:11434/api/generate
```

**Error**: `LLM generation failed: 'ollama' is not recognized`
```
Fix: Set OLLAMA_API_URL to use HTTP instead of CLI:
     $env:OLLAMA_API_URL = "http://localhost:11434/api/generate"
     
     Or install Ollama and add to PATH
```

## API Health Endpoints

You can also test individual components via API endpoints:

### Check LLM
```bash
curl http://localhost:8000/api/llm-health
```

### Check Database
```bash
curl http://localhost:8000/api/db-status
```

### Check Storage
```bash
curl http://localhost:8000/api/storage-status
```

### Quick Debug
```bash
curl http://localhost:8000/api/chat-debug
```

## Integration Testing

After diagnostics pass, test the full pipeline:

1. Start backend:
   ```powershell
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```

2. Start frontend:
   ```powershell
   cd frontend
   npm run dev
   ```

3. Upload a test PDF and chat

4. Check logs and job artifacts:
   - Backend logs: uvicorn terminal output
   - Job status: `data/jobs/{job_id}.json`
   - Prompts: `data/prompts/chat_*.json`
   - Extracted text: `data/jobs/{job_id}.extracted.txt`

## Environment Variables Summary

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DATABASE_URL` | No | `sqlite:///./backend_dev.db` | PostgreSQL connection string |
| `MONGO_URI` | No | None (filesystem fallback) | MongoDB for GridFS storage |
| `OLLAMA_API_URL` | No | CLI fallback | Ollama HTTP endpoint |

Set in PowerShell:
```powershell
$env:DATABASE_URL = "postgresql://user:pass@localhost/db"
$env:MONGO_URI = "mongodb://localhost:27017/cv_chat"
$env:OLLAMA_API_URL = "http://localhost:11434/api/generate"
```

## Getting Help

If all diagnostics pass but you still have issues:

1. Check browser console (F12) for frontend errors
2. Check uvicorn logs for backend errors
3. Verify CORS isn't blocking requests (check Network tab)
4. Ensure ports 8000 (backend) and 5173 (frontend) are not blocked
5. Try the `/api/chat-debug` endpoint to see component health

For specific errors, check the troubleshooting section in PROJECT_GUIDE.md
