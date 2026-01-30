import os
import uuid
import tempfile
import subprocess
import logging
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.storage import Storage
from app.services.extractor import extract_text_from_bytes
from app.services.llm_adapter import OllamaAdapter
from app.db.session import SessionLocal, engine
from app.db import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="CV Chat PoC")

# configure simple logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cv-chat")


# HTTP middleware to log incoming requests (method + path)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code} for {request.method} {request.url.path}")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = Storage()
llm = OllamaAdapter()
# simple job directory to map job_id -> result metadata (employee_id, status)
JOB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "jobs"))
os.makedirs(JOB_DIR, exist_ok=True)


@app.get("/api/llm-health")
def llm_health():
    """Health check for Ollama availability. Returns basic diagnostics.

    - If OLLAMA_API_URL is set, tries HTTP endpoint.
    - Otherwise tries the CLI.
    """
    try:
        sample = llm.generate("Say hello and return a short token: HELLO_TEST", timeout=10)
        return {"ok": True, "model": llm.model, "sample": sample}
    except Exception as e:
        return {"ok": False, "error": str(e), "model": llm.model}


@app.get("/health")
def health():
    """Simple server health endpoint (handy for load balancers / quick checks)."""
    return {"ok": True}


class UploadResponse(BaseModel):
    job_id: str
    status: str


@app.post("/api/upload-cv", response_model=UploadResponse)
async def upload_cv(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # save raw file to storage (GridFS or local fallback)
    contents = await file.read()
    file_id = storage.save_file(contents, filename=file.filename)
    job_id = str(uuid.uuid4())
    # enqueue background task
    background_tasks.add_task(process_cv, file_id, file.filename, job_id)
    return {"job_id": job_id, "status": "queued"}


async def process_cv(file_id: str, filename: str, job_id: str):
    # fetch file bytes
    data = storage.get_file(file_id)
    if not data:
        # log/raise
        # mark job as failed
        try:
            with open(os.path.join(JOB_DIR, f"{job_id}.json"), "w", encoding="utf-8") as jf:
                jf.write('{"status":"failed","reason":"file_not_found"}')
        except Exception:
            pass
        return
    # extract text
    text = extract_text_from_bytes(data)
    # write a small debug marker for extraction length
    try:
        with open(os.path.join(JOB_DIR, f"{job_id}.meta.txt"), "w", encoding="utf-8") as mf:
            mf.write(f"extracted_len={len(text)}")
    except Exception:
        pass
    # simple demo: store employee into SQL DB with minimal fields
    from sqlalchemy.orm import Session

    db: Session = SessionLocal()
    try:
        emp = models.Employee(name=filename, raw_text=text)
        db.add(emp)
        db.commit()
        db.refresh(emp)
        # map job -> employee id for frontend polling
        try:
            import json as _json

            job_info = {"status": "done", "employee_id": emp.id, "filename": filename}
            with open(os.path.join(JOB_DIR, f"{job_id}.json"), "w", encoding="utf-8") as jf:
                jf.write(_json.dumps(job_info))
        except Exception:
            pass
    finally:
        db.close()


class ChatRequest(BaseModel):
    prompt: str
    employee_id: int | None = None


@app.api_route("/api/chat", methods=["POST", "OPTIONS"])
async def chat(request: Request, req: ChatRequest | None = None):
    """Chat endpoint (POST). Also accepts OPTIONS for browser preflight.

    When called with OPTIONS this returns allowed methods to avoid 405 preflight errors.
    When called with POST it expects a JSON body matching ChatRequest.
    """
    if request.method == "OPTIONS":
        # respond to preflight with allowed methods; actual CORS headers come from middleware
        return {"ok": True, "methods": ["POST"]}

    # request.method == POST from here
    if req is None:
        # FastAPI should have validated body; return a 400 if missing
        raise HTTPException(status_code=400, detail="Missing JSON body for chat request")

    # log incoming chat call and method
    logger.info(f"/api/chat invoked via {request.method}")

    prompt = req.prompt
    if req.employee_id:
        # minimal enrichment: fetch employee and include first 1000 chars
        from sqlalchemy.orm import Session

        db: Session = SessionLocal()
        try:
            emp = db.query(models.Employee).filter(models.Employee.id == req.employee_id).first()
            if emp:
                prompt = f"Employee record:\n{emp.raw_text[:1000]}\n\nUser prompt:\n{req.prompt}"
        finally:
            db.close()

    try:
        resp = llm.generate(prompt)
    except Exception as e:
        logger.exception("LLM generation failed")
        raise HTTPException(status_code=500, detail=str(e))
    return {"reply": resp}


@app.get("/api/chat")
def chat_get():
    """Friendly GET handler for the chat endpoint.

    Some tools or manual requests may do a GET against this path (browser address bar,
    link previews, or devtools). Return an informative JSON instead of a 405 so the
    client sees how to call the endpoint correctly.
    """
    return {
        "detail": "This endpoint expects POST with a JSON body: { \"prompt\": \"...\" }. Use POST /api/chat",
        "methods": ["POST"],
    }


@app.get("/api/chat-debug")
def chat_debug():
    """Lightweight debug endpoint for manual checks from a browser.

    Returns:
    - a quick LLM sample (or error message)
    - a count of Employee rows in the SQL DB
    - which storage backend is active
    """
    # LLM quick probe (use a short timeout so this stays snappy)
    try:
        sample = llm.generate("Debug ping: return short token DEBUG_OK", timeout=5)
        llm_ok = True
    except Exception as e:
        sample = str(e)
        llm_ok = False

    # DB quick probe: count employees (fast)
    from sqlalchemy.orm import Session

    db: Session = SessionLocal()
    try:
        emp_count = db.query(models.Employee).count()
    except Exception:
        emp_count = None
    finally:
        db.close()

    return {
        "llm_ok": llm_ok,
        "llm_sample_or_error": sample,
        "employee_count": emp_count,
        "storage_backend": storage.__class__.__name__,
    }



@app.get("/api/job/{job_id}")
def job_status(job_id: str):
    """Return job status and linked employee_id when available.

    This is a lightweight file-backed job status used by the frontend demo to poll
    the background processing result.
    """
    import json

    path = os.path.join(JOB_DIR, f"{job_id}.json")
    if not os.path.exists(path):
        return {"status": "pending"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        return {"status": "error", "error": str(e)}
