CV Chat PoC (backend)
======================

This folder contains a minimal FastAPI backend scaffold for the interview PoC.

What is included
- FastAPI app with `/api/upload-cv` and `/api/chat` endpoints
- BackgroundTasks-based ingestion (no Celery) for a simple demo
- Storage adapter: Mongo GridFS if `MONGO_URI` is provided, else local file storage
- Ollama adapter that calls the `ollama` CLI (uses model name from `OLLAMA_MODEL` env var)
- SQLAlchemy with a simple `Employee` model (defaults to a local sqlite DB file)

How to run (quick)
1. Create a Python venv and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Set environment variables if you have Postgres/Mongo installed (optional):

 - `DATABASE_URL` (e.g. postgres://user:pass@localhost:5432/dbname)
 - `MONGO_URI` (e.g. mongodb://localhost:27017)
 - `OLLAMA_MODEL` (default: qwen-2.5)

3. Run FastAPI:

```powershell
uvicorn app.main:app --reload --port 8000
```

Notes
- This is a scaffold: extractor/embedding/indexing steps are minimal and intended to be extended.
- For the interview demo we intentionally keep the pipeline simple and modular so each component can be explained and swapped.
