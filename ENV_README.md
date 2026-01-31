# Environment Configuration - Quick Reference

## 📁 File Structure

```
ems_2.0/
├── backend/
│   ├── .env              # Active backend configuration (DO NOT COMMIT)
│   └── .env.example      # Template with all available options
├── frontend/
│   ├── .env              # Active frontend configuration (DO NOT COMMIT)
│   └── .env.example      # Template with all available options
└── ENV_SETUP_GUIDE.md    # Detailed configuration guide
```

## 🚀 Quick Start

### First Time Setup

1. **Backend Configuration**
   ```powershell
   # The .env files are already created with defaults
   # Just verify Ollama is running and you're ready!
   
   # Optional: Test your backend config
   cd backend
   python -m app.config
   ```

2. **Frontend Configuration**
   ```powershell
   # Frontend .env is pre-configured to point to localhost:8000
   # No changes needed for local development
   ```

3. **Start the Application**
   ```powershell
   # Terminal 1 - Backend
   cd backend
   uvicorn app.main:app --reload --port 8000

   # Terminal 2 - Frontend  
   cd frontend
   npm run dev
   ```

## 🔧 Current Configuration

### Backend (backend/.env)
```env
DATABASE_URL=sqlite:///./backend_dev.db     # SQLite for quick start
MONGO_URI=                                   # Empty = local file storage
OLLAMA_MODEL=qwen2.5:7b-instruct            # LLM model
OLLAMA_API_URL=http://localhost:11434/api/generate
```

### Frontend (frontend/.env)
```env
VITE_API_BASE_URL=http://localhost:8000     # Points to backend
VITE_APP_TITLE=ChatBot                       # App title
VITE_DEBUG=true                              # Enable debug logs
```

## 🎯 Common Configuration Tasks

### Change Backend Port

```env
# backend/.env
PORT=8001

# frontend/.env  
VITE_API_BASE_URL=http://localhost:8001
```

### Use PostgreSQL Instead of SQLite

```env
# backend/.env
DATABASE_URL=postgresql://username:password@localhost:5432/cv_database
```

### Enable MongoDB for File Storage

```env
# backend/.env
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=cv_repo
```

### Use a Different LLM Model

```env
# backend/.env
OLLAMA_MODEL=llama2
# or
OLLAMA_MODEL=mistral
# or  
OLLAMA_MODEL=codellama
```

### Configure for Production

```env
# backend/.env
DATABASE_URL=postgresql://user:pass@prod-db:5432/cvdb
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=https://yourdomain.com
SECRET_KEY=<generate-with: openssl rand -hex 32>

# frontend/.env
VITE_API_BASE_URL=https://api.yourdomain.com
VITE_DEBUG=false
VITE_ENVIRONMENT=production
```

## 📝 Key Environment Variables

### Backend - Most Important

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | Database connection | `sqlite:///./backend_dev.db` |
| `OLLAMA_API_URL` | LLM endpoint | `http://localhost:11434/api/generate` |
| `MONGO_URI` | File storage (optional) | _(empty = local files)_ |
| `PORT` | Backend port | `8000` |

### Frontend - Most Important

| Variable | Purpose | Default |
|----------|---------|---------|
| `VITE_API_BASE_URL` | Backend URL | `http://localhost:8000` |
| `VITE_APP_TITLE` | App title | `ChatBot` |
| `VITE_DEBUG` | Debug mode | `true` |

## 🔒 Security Notes

- ✅ `.env` files are in `.gitignore` - they won't be committed
- ✅ `.env.example` files show what variables are available
- ⚠️ **Never commit actual credentials** to version control
- ⚠️ **Use different credentials** for dev/staging/production
- ⚠️ Generate strong `SECRET_KEY` for production: `openssl rand -hex 32`

## 🐛 Troubleshooting

### Backend won't start

```powershell
# Check configuration
cd backend
python -m app.config

# Common issues:
# - Ollama not running: Start Ollama app or run `ollama serve`
# - Port in use: Change PORT in backend/.env
# - Database error: Check DATABASE_URL format
```

### Frontend can't reach backend

```powershell
# Verify backend is running
curl http://localhost:8000/health

# Check frontend .env
cd frontend
cat .env  # Should show: VITE_API_BASE_URL=http://localhost:8000

# Make sure PORT matches!
```

### Environment variables not loading

**Backend:** Restart uvicorn after changing `.env`

**Frontend:** Restart dev server (`npm run dev`) after changing `.env`

**Important:** Frontend variables **must** start with `VITE_`

## 📖 Full Documentation

For comprehensive documentation including:
- All available environment variables
- Configuration scenarios
- Security best practices  
- Advanced features
- Validation and troubleshooting

See: **[ENV_SETUP_GUIDE.md](ENV_SETUP_GUIDE.md)**

## 🧪 Testing Your Configuration

### Backend Configuration Test
```powershell
cd backend
python -m app.config
```

This will:
- Load all environment variables
- Display current configuration (with masked passwords)
- Validate required variables
- Show any missing configuration

### Frontend Configuration Test

Frontend env variables are available in browser console:
```javascript
// Open browser dev console and run:
console.log(import.meta.env)
```

## 🆘 Need Help?

1. **Check the detailed guide:** [ENV_SETUP_GUIDE.md](ENV_SETUP_GUIDE.md)
2. **Review project setup:** [PROJECT_GUIDE.md](PROJECT_GUIDE.md)  
3. **Check recent changes:** [CHANGELOG.md](CHANGELOG.md)
4. **Example configurations:** Look at `.env.example` files

## 📦 Environment Variable Loading

**Backend** (Python/FastAPI):
- Loaded automatically from `backend/.env` by the OS/shell
- Access via `os.getenv("VARIABLE_NAME")`
- Use `app.config.config` for type-safe access

**Frontend** (React/Vite):
- Loaded from `frontend/.env` during build
- Must prefix with `VITE_` to be exposed
- Access via `import.meta.env.VITE_VARIABLE_NAME`
- Only variables present at build time are included
