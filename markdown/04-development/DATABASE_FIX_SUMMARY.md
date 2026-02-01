# Database Storage Issue - Diagnosis & Resolution

## Problem Summary

**Issue:** Data was not being stored in PostgreSQL and MongoDB databases as configured.

**Root Cause:** Environment variables from `.env` file were not being loaded, causing the application to fall back to default SQLite storage.

## Diagnostic Results

### Before Fix ❌
```
Configuration in .env file:
  DATABASE_URL=postgresql://postgres:p@localhost:5432/ems
  MONGO_URI=mongodb://localhost:27017

Actual runtime values:
  DATABASE_URL=None  (defaults to sqlite:///./backend_dev.db)
  MONGO_URI=None     (defaults to local file storage)

Result: All data stored in SQLite, not PostgreSQL!
```

### After Fix ✅
```
Configuration in .env file:
  DATABASE_URL=postgresql://postgres:p@localhost:5432/ems
  MONGO_URI=mongodb://localhost:27017

Actual runtime values:
  DATABASE_URL=postgresql://postgres:****@localhost:5432/ems
  MONGO_URI=mongodb://localhost:27017

Result: Data now properly stored in PostgreSQL and MongoDB!
```

## What Was Wrong

### The Missing Piece
The backend had `python-dotenv` installed but **never called `load_dotenv()`** to actually read the `.env` file.

**In `app/main.py`:**
```python
# ❌ Before (missing):
import os
from app.services.storage import Storage
# ... code uses os.getenv() but .env was never loaded!

# ✅ After (fixed):
import os
from dotenv import load_dotenv
load_dotenv()  # Now .env file is loaded!
from app.services.storage import Storage
```

## Current Database Status

### PostgreSQL ✅
- **Status:** Connected and running
- **Version:** PostgreSQL 16.11
- **Database:** ems
- **Tables:** employees (created)
- **Records:** 0 (empty - but ready to receive data)
- **Connection:** postgresql://postgres:p@localhost:5432/ems

### MongoDB ✅
- **Status:** Connected and running
- **Database:** cv_repo
- **Collections:** (empty - will be created on first file upload)
- **GridFS Files:** 0
- **Connection:** mongodb://localhost:27017

### Ollama LLM ✅
- **Status:** Reachable via HTTP
- **URL:** http://localhost:11434/api/generate
- **Model:** qwen2.5:7b-instruct

### Local Storage ✅
- **Jobs:** 56 files in data/jobs/
- **Prompts:** 34 files in data/prompts/
- **FAISS:** 2 files in data/faiss/

## What Data Goes Where

### Employee Records → PostgreSQL
```sql
-- Table: employees
-- Columns: id, name, email, phone, raw_text
-- Location: PostgreSQL database 'ems'
```

**When:** After CV is uploaded and processed, structured data (name, email, phone) is saved here.

**Check data:**
```powershell
psql -U postgres -d ems
SELECT * FROM employees;
```

### PDF Files → MongoDB GridFS
```javascript
// Collection: fs.files, fs.chunks
// Database: cv_repo
// Storage: Binary file data
```

**When:** When a PDF is uploaded, the raw file is stored here (or local filesystem if MongoDB unavailable).

**Check data:**
```powershell
mongosh
use cv_repo
db.fs.files.find()
```

### Text Embeddings → FAISS Index
```
Location: backend/data/faiss/
Files: index.bin, metadata.json
```

**When:** After text extraction, chunks are embedded and indexed for RAG retrieval.

### Job Metadata → Local JSON
```
Location: backend/data/jobs/
Files: {job_id}.json, {job_id}.meta.txt, {job_id}.prompt.txt
```

**When:** Background processing creates these tracking files.

## Why Data Wasn't Appearing

### Before the Fix

1. User uploads PDF
2. Backend reads `.env` config...
   - ❌ `load_dotenv()` not called
   - ❌ `os.getenv("DATABASE_URL")` returns `None`
   - ❌ Falls back to SQLite: `sqlite:///./backend_dev.db`
3. Data saves to SQLite (backend_dev.db file)
4. User checks PostgreSQL: Empty! ❌
5. User checks MongoDB: Empty! ❌
6. User thinks: "Data not storing!" ❌

### After the Fix

1. User uploads PDF
2. Backend reads `.env` config...
   - ✅ `load_dotenv()` called at startup
   - ✅ `os.getenv("DATABASE_URL")` returns PostgreSQL URL
   - ✅ Connects to PostgreSQL database 'ems'
3. Data saves to PostgreSQL
4. User checks PostgreSQL: Data there! ✅
5. Files stored in MongoDB GridFS ✅

## Files Modified

1. **backend/app/main.py**
   - Added: `from dotenv import load_dotenv`
   - Added: `load_dotenv()` call before imports
   - Effect: Environment variables now loaded at server startup

2. **backend/app/config.py**
   - Added: `from dotenv import load_dotenv`
   - Added: `load_dotenv()` call
   - Effect: Config module can correctly load env vars

3. **backend/diagnose_databases.py**
   - Created: Comprehensive diagnostic script
   - Tests: PostgreSQL, MongoDB, Ollama, local storage
   - Output: Clear success/failure messages

4. **CHANGELOG.md**
   - Updated: Documented the fix and diagnostic tool

## How to Verify It's Working

### Test 1: Check Configuration
```powershell
cd backend
python -m app.config
```

**Expected output:**
```
Database:
  URL: postgresql://postgres:****@localhost:5432/ems  ✅
MongoDB:
  URI: mongodb://localhost:27017  ✅
```

### Test 2: Run Diagnostics
```powershell
cd backend
python diagnose_databases.py
```

**Expected output:**
```
✅ SUCCESS: Connected to PostgreSQL
✅ SUCCESS: Connected to MongoDB
✅ SUCCESS: Ollama is reachable
```

### Test 3: Upload a CV and Check

1. **Start backend:**
   ```powershell
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```

2. **Upload a PDF via frontend**

3. **Check PostgreSQL:**
   ```powershell
   psql -U postgres -d ems
   SELECT id, name, email FROM employees;
   ```
   You should see the extracted candidate data!

4. **Check MongoDB:**
   ```powershell
   mongosh
   use cv_repo
   db.fs.files.find()
   ```
   You should see the uploaded PDF file!

## Important: Restart Required

**⚠️ CRITICAL:** The uvicorn server must be **restarted** for the `load_dotenv()` changes to take effect!

```powershell
# Stop current server (Ctrl+C)
# Then restart:
cd backend
uvicorn app.main:app --reload --port 8000
```

The `.env` file is loaded **once at startup**, not on each request.

## Common Issues & Solutions

### Issue 1: Still using SQLite after fix
**Cause:** Backend server not restarted
**Solution:** Restart uvicorn server

### Issue 2: PostgreSQL connection refused
**Cause:** PostgreSQL not running
**Solution:** 
```powershell
# Check service
Get-Service postgresql*

# Start if stopped
Start-Service postgresql-x64-16
```

### Issue 3: Database 'ems' does not exist
**Cause:** Database not created
**Solution:**
```powershell
createdb -U postgres ems
# or via psql:
psql -U postgres
CREATE DATABASE ems;
```

### Issue 4: MongoDB connection timeout
**Cause:** MongoDB not running
**Solution:**
```powershell
# Check service
Get-Service MongoDB

# Start if stopped
Start-Service MongoDB
```

### Issue 5: Tables not created
**Cause:** SQLAlchemy doesn't have permissions or database connection failed
**Solution:**
```powershell
# The backend creates tables automatically on startup
# Check backend logs for errors
# Manually create if needed:
psql -U postgres -d ems
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(64),
    raw_text TEXT
);
```

## Data Migration (Optional)

If you had data in SQLite that you want to move to PostgreSQL:

```powershell
cd backend

# Export from SQLite
sqlite3 backend_dev.db ".dump employees" > employees_export.sql

# Import to PostgreSQL (after editing SQL if needed)
psql -U postgres -d ems -f employees_export.sql
```

## Monitoring & Debugging

### Watch Backend Logs
```powershell
# The uvicorn server shows all SQL queries in debug mode
# Look for lines like:
# INFO:sqlalchemy.engine.Engine:SELECT employees.id, ...
# INFO:sqlalchemy.engine.Engine:INSERT INTO employees ...
```

### Query Databases Directly

**PostgreSQL:**
```sql
-- Count records
SELECT COUNT(*) FROM employees;

-- View recent records
SELECT * FROM employees ORDER BY id DESC LIMIT 10;

-- Check table structure
\d employees
```

**MongoDB:**
```javascript
// Count files
db.fs.files.countDocuments()

// List recent uploads
db.fs.files.find().sort({uploadDate: -1}).limit(10)

// Check database size
db.stats()
```

## Summary

✅ **Problem:** Environment variables not loading  
✅ **Solution:** Added `load_dotenv()` calls  
✅ **Verified:** Databases now connected  
✅ **Status:** Ready to store data  

**Next steps:**
1. Restart backend server
2. Upload a test PDF
3. Check PostgreSQL for employee record
4. Check MongoDB for file
5. Celebrate! 🎉

## Diagnostic Script Usage

The `diagnose_databases.py` script is now available for ongoing monitoring:

```powershell
cd backend
python diagnose_databases.py
```

Run this anytime you suspect database issues. It will:
- Test PostgreSQL connection
- Test MongoDB connection  
- Check table/collection existence
- Count records
- Test Ollama connectivity
- Check local file storage
- Provide troubleshooting tips

Keep this script handy for debugging!
