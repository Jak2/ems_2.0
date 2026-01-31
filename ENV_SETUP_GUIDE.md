# Environment Configuration Guide

This guide explains how to configure the environment variables for the CV Chat PoC application.

## Overview

The application uses `.env` files to manage configuration for both backend and frontend components. This approach:
- Keeps sensitive credentials out of source control
- Makes it easy to switch between development/staging/production environments
- Allows different team members to use their own local settings

## Quick Start

### 1. Backend Setup

```powershell
cd backend
```

**Option A: Use the default configuration (recommended for quick start)**
```powershell
# The .env file is already created with sensible defaults
# Just ensure Ollama is running and you're good to go!
```

**Option B: Customize your configuration**
```powershell
# Edit backend/.env with your preferred settings
notepad .env
```

### 2. Frontend Setup

```powershell
cd frontend
```

**Option A: Use the default configuration**
```powershell
# The .env file is already created with defaults
# It points to http://localhost:8000 by default
```

**Option B: Customize your configuration**
```powershell
# Edit frontend/.env with your preferred settings
notepad .env
```

### 3. Start the Application

```powershell
# Terminal 1 - Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev
```

## Configuration Reference

### Backend Environment Variables

#### 🗄️ Database Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DATABASE_URL` | Database connection string | `sqlite:///./backend_dev.db` | `postgresql://user:pass@localhost:5432/cvdb` |

**Supported Databases:**
- **SQLite** (default): `sqlite:///./backend_dev.db`
- **PostgreSQL**: `postgresql://username:password@host:port/database`
- **MySQL**: `mysql://username:password@host:port/database`

#### 📦 MongoDB Configuration (File Storage)

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MONGO_URI` | MongoDB connection URI | _(empty = local files)_ | `mongodb://localhost:27017/` |
| `MONGO_DB` | MongoDB database name | `cv_repo` | `cv_repo` |

**Storage Behavior:**
- If `MONGO_URI` is set: Uses GridFS for file storage (scalable)
- If `MONGO_URI` is empty: Uses local filesystem under `backend/data/files/`

#### 🤖 Ollama LLM Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `OLLAMA_MODEL` | Model name | `qwen2.5:7b-instruct` | `llama2`, `mistral` |
| `OLLAMA_API_URL` | HTTP API endpoint | `http://localhost:11434/api/generate` | _Same_ |

**LLM Behavior:**
- If `OLLAMA_API_URL` is set: Uses HTTP API (recommended)
- If `OLLAMA_API_URL` is empty: Falls back to CLI (`ollama` command)

**Popular Models:**
- `qwen2.5:7b-instruct` - Fast, good for extraction tasks
- `llama2` - General purpose, well-rounded
- `mistral` - Excellent instruction following
- `codellama` - Best for code-related tasks

#### ⚙️ Application Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `HOST` | Server host | `0.0.0.0` | `127.0.0.1` |
| `PORT` | Server port | `8000` | `8000` |
| `ENVIRONMENT` | Environment mode | `development` | `production` |
| `DEBUG` | Enable debug mode | `true` | `false` |
| `CORS_ORIGINS` | Allowed CORS origins | `*` | `http://localhost:5173` |

#### 📄 File Processing

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MAX_UPLOAD_SIZE_MB` | Max file size | `10` | `20` |
| `TESSERACT_CMD` | Tesseract executable path | _(auto-detect)_ | `C:\Program Files\Tesseract-OCR\tesseract.exe` |

**Note:** Tesseract is required for OCR fallback (scanned PDFs). Install from:
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Linux: `sudo apt-get install tesseract-ocr`
- Mac: `brew install tesseract`

#### 🔍 Embeddings & RAG

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `EMBEDDING_MODEL` | Sentence transformer model | `all-MiniLM-L6-v2` | `all-mpnet-base-v2` |
| `RAG_TOP_K` | Number of chunks to retrieve | `5` | `10` |
| `CHUNK_SIZE` | Text chunk size (chars) | `500` | `800` |
| `CHUNK_OVERLAP` | Chunk overlap (chars) | `100` | `150` |

### Frontend Environment Variables

All Vite environment variables must be prefixed with `VITE_` to be exposed to the frontend.

#### 🌐 Backend API Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:8000` | `https://api.example.com` |
| `VITE_API_UPLOAD_ENDPOINT` | Upload endpoint path | `/api/upload-cv` | `/api/upload-cv` |
| `VITE_API_CHAT_ENDPOINT` | Chat endpoint path | `/api/chat` | `/api/chat` |

#### 🎨 UI Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VITE_APP_TITLE` | Application title | `ChatBot` | `CV Assistant` |
| `VITE_THEME_MODE` | Theme mode | `light` | `dark` |
| `VITE_ENABLE_DARK_MODE_TOGGLE` | Show dark mode toggle | `true` | `false` |

#### 🔧 Feature Flags

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VITE_DEBUG` | Enable debug logging | `true` | `false` |
| `VITE_ENABLE_ATTACHMENT_PREVIEW` | Show file preview | `true` | `true` |
| `VITE_MAX_FILE_SIZE_MB` | Max upload size | `10` | `20` |

#### ⏱️ Polling Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VITE_JOB_POLL_INTERVAL` | Poll interval (ms) | `1000` | `2000` |
| `VITE_JOB_POLL_TIMEOUT` | Poll timeout (ms) | `60000` | `120000` |

## Common Scenarios

### Scenario 1: Local Development (Default)

```env
# backend/.env
DATABASE_URL=sqlite:///./backend_dev.db
MONGO_URI=
OLLAMA_API_URL=http://localhost:11434/api/generate

# frontend/.env
VITE_API_BASE_URL=http://localhost:8000
```

**This is the default setup.** It uses:
- SQLite for database (no setup required)
- Local filesystem for file storage
- Ollama HTTP API on localhost

### Scenario 2: Using PostgreSQL and MongoDB

```env
# backend/.env
DATABASE_URL=postgresql://postgres:mypassword@localhost:5432/cv_database
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=cv_repo
OLLAMA_API_URL=http://localhost:11434/api/generate
```

**Prerequisites:**
1. Install PostgreSQL: https://www.postgresql.org/download/
2. Install MongoDB: https://www.mongodb.com/try/download/community
3. Create database: `createdb cv_database`

### Scenario 3: Production Deployment

```env
# backend/.env
DATABASE_URL=postgresql://user:pass@prod-db.example.com:5432/cvdb
MONGO_URI=mongodb://user:pass@prod-mongo.example.com:27017/
OLLAMA_API_URL=http://ollama-service:11434/api/generate
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=https://app.example.com
SECRET_KEY=<generate-with-openssl-rand-hex-32>

# frontend/.env
VITE_API_BASE_URL=https://api.example.com
VITE_DEBUG=false
VITE_ENVIRONMENT=production
```

### Scenario 4: Team Development (Different Ports)

If port 8000 is already in use by another team member:

```env
# backend/.env
PORT=8001

# frontend/.env
VITE_API_BASE_URL=http://localhost:8001
```

## Accessing Environment Variables

### In Backend (Python)

```python
import os

# Get a variable
database_url = os.getenv("DATABASE_URL")

# With default value
model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

# Required variable (raises error if missing)
secret = os.environ["SECRET_KEY"]
```

### In Frontend (React/Vite)

```javascript
// Vite automatically loads VITE_* variables
const apiUrl = import.meta.env.VITE_API_BASE_URL

// With default value
const debug = import.meta.env.VITE_DEBUG === 'true'

// Check if variable exists
if (import.meta.env.VITE_GA_ID) {
  // Initialize analytics
}
```

## Security Best Practices

### ✅ DO:
- ✅ Keep `.env` files in `.gitignore` (already configured)
- ✅ Use `.env.example` files to document required variables
- ✅ Use strong passwords and secure connection strings in production
- ✅ Rotate secrets regularly
- ✅ Use different credentials for dev/staging/prod
- ✅ Generate secure random keys: `openssl rand -hex 32`

### ❌ DON'T:
- ❌ Commit `.env` files to git
- ❌ Share `.env` files via email or chat
- ❌ Use production credentials in development
- ❌ Hard-code secrets in source code
- ❌ Use default/weak passwords

## Troubleshooting

### Problem: Backend can't connect to Ollama

**Solution:**
1. Check if Ollama is running: `ollama list`
2. Verify the API URL: `curl http://localhost:11434/api/generate`
3. Try setting `OLLAMA_API_URL=` (empty) to use CLI fallback

### Problem: Frontend can't reach backend

**Solution:**
1. Check backend is running: `curl http://localhost:8000/health`
2. Verify `VITE_API_BASE_URL` matches your backend port
3. Check CORS settings in `backend/.env`

### Problem: Database connection failed

**Solution:**
1. Verify database is running (PostgreSQL/MongoDB)
2. Check connection string format in `DATABASE_URL`
3. Test connection: `psql <DATABASE_URL>` (PostgreSQL) or `mongosh <MONGO_URI>` (MongoDB)

### Problem: Environment variables not loading

**Backend:**
- Ensure `.env` file is in the `backend/` directory
- Restart the uvicorn server
- Check for typos in variable names

**Frontend:**
- Ensure `.env` file is in the `frontend/` directory
- Variables must start with `VITE_`
- Run `npm run dev` to reload

## Advanced Configuration

### Using Multiple Environment Files

Vite supports mode-specific env files:

```
frontend/
  .env                # Loaded in all cases
  .env.local          # Loaded in all cases, ignored by git
  .env.development    # Only loaded in development
  .env.production     # Only loaded in production
```

Example:
```powershell
# Development
npm run dev

# Production build
npm run build
```

### Environment Variable Validation

For production, consider adding validation:

```python
# backend/app/config.py
import os

def validate_env():
    required = ["DATABASE_URL", "OLLAMA_API_URL", "SECRET_KEY"]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        raise EnvironmentError(f"Missing required env vars: {missing}")
```

## References

- [Vite Environment Variables](https://vitejs.dev/guide/env-and-mode.html)
- [Python-dotenv Documentation](https://github.com/theskumar/python-dotenv)
- [PostgreSQL Connection Strings](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING)
- [MongoDB Connection Strings](https://www.mongodb.com/docs/manual/reference/connection-string/)

## Need Help?

Check the `PROJECT_GUIDE.md` for overall architecture and setup instructions.
