# Environment Configuration Architecture

## Configuration Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     DEVELOPMENT MACHINE                          │
│                                                                   │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │   backend/.env   │         │  frontend/.env   │             │
│  │                  │         │                  │             │
│  │ DATABASE_URL=... │         │ VITE_API_BASE... │             │
│  │ OLLAMA_API_URL.. │         │ VITE_APP_TITLE.. │             │
│  │ MONGO_URI=...    │         │ VITE_DEBUG=...   │             │
│  └────────┬─────────┘         └─────────┬────────┘             │
│           │                             │                       │
│           │ Loaded at runtime          │ Loaded at build       │
│           │                             │                       │
│           ▼                             ▼                       │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │  FastAPI Server  │◄────────┤   React App      │             │
│  │  (port 8000)     │  HTTP   │  (Vite dev)      │             │
│  │                  ├────────►│  (port 5173)     │             │
│  └────┬─────┬───┬───┘         └──────────────────┘             │
│       │     │   │                                               │
│       │     │   └─────────────────────┐                        │
│       │     │                         │                        │
│       ▼     ▼                         ▼                        │
│  ┌─────┐ ┌──────┐             ┌──────────────┐                │
│  │SQLite MongoD│             │   Ollama     │                │
│  │  or  │ │ (opt)│             │   LLM API    │                │
│  │Postgr│ │GridFS│             │  (port 11434)│                │
│  └─────┘ └──────┘             └──────────────┘                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Environment Variable Loading

### Backend (Python/FastAPI)

```
┌─────────────────────────────────────────────────────────────┐
│                    Backend Startup                          │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ 1. Shell loads .env
                           │    (PowerShell/bash)
                           ▼
            ┌─────────────────────────┐
            │  Environment Variables  │
            │  in Process Memory      │
            └────────────┬────────────┘
                         │
                         │ 2. Import app.config
                         ▼
            ┌─────────────────────────┐
            │   app/config.py         │
            │   - load_config()       │
            │   - validate_required() │
            │   - Config dataclass    │
            └────────────┬────────────┘
                         │
                         │ 3. Create typed config
                         ▼
            ┌─────────────────────────┐
            │  config instance        │
            │  config.DATABASE_URL    │
            │  config.OLLAMA_MODEL    │
            │  config.CHUNK_SIZE      │
            └────────────┬────────────┘
                         │
                         │ 4. Used by services
                         ▼
        ┌────────────────┴───────────────┐
        │                                 │
        ▼                                 ▼
┌──────────────┐                 ┌──────────────┐
│ LLM Adapter  │                 │   Storage    │
│ os.getenv()  │                 │  os.getenv() │
└──────────────┘                 └──────────────┘
```

### Frontend (React/Vite)

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Build                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ 1. Vite reads .env
                           │    at build time
                           ▼
            ┌─────────────────────────┐
            │  VITE_* variables only  │
            │  Others are ignored     │
            └────────────┬────────────┘
                         │
                         │ 2. Embedded in bundle
                         ▼
            ┌─────────────────────────┐
            │   import.meta.env       │
            │   (read-only object)    │
            └────────────┬────────────┘
                         │
                         │ 3. Access in components
                         ▼
            ┌─────────────────────────┐
            │  React Components       │
            │  const api =            │
            │    import.meta.env      │
            │      .VITE_API_BASE_URL │
            └─────────────────────────┘
```

## Configuration Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                  Configuration Priority                      │
│                  (Lowest to Highest)                         │
└─────────────────────────────────────────────────────────────┘

1. Hard-coded defaults in code
   └─► config = os.getenv("VAR", "default_value")
           │
           │ Overridden by
           ▼
2. .env file
   └─► DATABASE_URL=sqlite:///./backend_dev.db
           │
           │ Overridden by
           ▼
3. .env.local file (gitignored, personal overrides)
   └─► DATABASE_URL=postgresql://localhost:5432/mydb
           │
           │ Overridden by
           ▼
4. Shell environment variables
   └─► $env:DATABASE_URL = "postgresql://prod-db:5432/cvdb"
           │
           │ Overridden by
           ▼
5. CI/CD environment (GitHub Actions secrets, etc.)
   └─► Set in deployment platform
```

## Security Model

```
┌─────────────────────────────────────────────────────────────┐
│                      Git Repository                          │
│                                                               │
│  ✅ Committed (tracked):                                     │
│     - .env.example (template with docs)                      │
│     - .gitignore (includes .env)                             │
│     - app/config.py (loader with validation)                 │
│                                                               │
│  ❌ Not Committed (gitignored):                              │
│     - .env (active configuration)                            │
│     - .env.local (personal overrides)                        │
│     - .env.*.local (environment-specific overrides)          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ Developer clones repo
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Developer Machine                          │
│                                                               │
│  1. Copy .env.example to .env                                │
│  2. Fill in personal credentials                             │
│  3. Never commit .env                                        │
│                                                               │
│  Each developer has own .env with:                           │
│  - Own database credentials                                  │
│  - Own API keys                                              │
│  - Own port preferences                                      │
│                                                               │
└────────────────────────────────────────────────────────────��┘
                           │
                           │ Deploy to production
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Production Server                          │
│                                                               │
│  Environment variables set by:                               │
│  - Platform UI (Heroku, Vercel, etc.)                        │
│  - CI/CD secrets (GitHub Actions)                            │
│  - Kubernetes ConfigMaps/Secrets                             │
│  - Cloud secret manager (AWS/Azure/GCP)                      │
│                                                               │
│  No .env file on production server!                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Configuration Testing Flow

```
┌────────────────────────────────────────────────────────┐
│  Developer wants to test configuration                 │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │ Backend Test:  │
        │ python -m      │
        │ app.config     │
        └───────┬────────┘
                │
                ▼
┌───────────────────────────────────────────────────────┐
│  Configuration Loader Runs:                           │
│  1. Load all env vars from .env                       │
│  2. Apply defaults for missing vars                   │
│  3. Create typed Config object                        │
│  4. Validate required vars for environment            │
│  5. Print config summary (with password masking)      │
│  6. Report success or missing vars                    │
└───────────────────────────────────────────────────────┘
                │
                ├─► ✅ Success: All required vars present
                │
                └─► ❌ Error: Missing DATABASE_URL, SECRET_KEY
                           See ENV_SETUP_GUIDE.md for help
```

## Multi-Environment Strategy

```
Development          Staging             Production
    │                   │                    │
    ▼                   ▼                    ▼
┌─────────┐       ┌─────────┐         ┌─────────┐
│  .env   │       │  .env   │         │  Cloud  │
│ (local) │       │ (server)│         │ Secrets │
└────┬────┘       └────┬────┘         └────┬────┘
     │                 │                    │
     │ Uses:           │ Uses:              │ Uses:
     │                 │                    │
     ├─SQLite          ├─PostgreSQL         ├─PostgreSQL
     ├─Local files     │  (staging DB)      │  (prod DB)
     ├─localhost       ├─Staging LLM        ├─Production LLM
     └─Debug ON        └─Debug ON           └─Debug OFF
                                             └─Auth ON
                                             └─Rate limiting
                                             └─TLS required
```

## Configuration Change Workflow

```
Developer needs to change a configuration:

1. Edit .env file
   └─► vi backend/.env
   
2. Restart service
   └─► uvicorn app.main:app --reload
   
3. Verify change loaded
   └─► python -m app.config
   
4. Test functionality
   └─► curl http://localhost:8000/health
   
5. Document change (if applicable)
   └─► Update .env.example with new variable
   └─► Add to ENV_SETUP_GUIDE.md
   └─► Update CHANGELOG.md
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────┐
│  Application starts with invalid configuration          │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
      ┌───────────────────────┐
      │ app/config.py loads   │
      │ validate_required_env()│
      └───────────┬───────────┘
                  │
                  │ Checks required vars
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
    ✅ Valid            ❌ Invalid
        │                   │
        │                   ├─► Raise EnvironmentError
        │                   │   with helpful message:
        │                   │   "Missing: SECRET_KEY, DATABASE_URL"
        │                   │   "See ENV_SETUP_GUIDE.md"
        │                   │
        │                   └─► Application exits with code 1
        │
        └─► Continue startup
```

## Best Practices Applied

1. **Separation of Concerns**
   - Config separated from code
   - Easy to change without redeployment

2. **Security by Default**
   - Secrets never in git
   - Password masking in logs
   - Validation before use

3. **Developer Experience**
   - Sensible defaults work out of box
   - Clear error messages
   - Comprehensive documentation

4. **Production Ready**
   - Environment-specific validation
   - Required security vars in prod
   - Multiple deployment strategies

5. **Type Safety (Backend)**
   - Typed Config dataclass
   - IDE autocomplete
   - Prevents typos

6. **Flexibility**
   - Override at multiple levels
   - Personal .env.local files
   - Platform-specific options
