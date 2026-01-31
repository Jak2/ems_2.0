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
from app.services.embeddings import Embeddings
from app.services.vectorstore_faiss import FaissVectorStore
from app.db.session import SessionLocal, engine
from app.db import models

models.Base.metadata.create_all(bind=engine)
# Ensure employees table has a `phone` column (simple demo migration)
try:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    cols = [c["name"] for c in inspector.get_columns("employees")]
    if "phone" not in cols:
        # SQLite / Postgres compatible ALTER (SQLite allows ADD COLUMN)
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE employees ADD COLUMN phone VARCHAR(64)"))
except Exception:
    # non-fatal; if alter fails it's likely the DB doesn't support it or column exists
    pass

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
PROMPT_LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "prompts"))
os.makedirs(PROMPT_LOG_DIR, exist_ok=True)
FAISS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "faiss"))
os.makedirs(FAISS_DIR, exist_ok=True)
vectorstore = FaissVectorStore(FAISS_DIR)


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
    # log the raw extracted text excerpt for debugging
    try:
        with open(os.path.join(JOB_DIR, f"{job_id}.extracted.txt"), "w", encoding="utf-8") as ef:
            ef.write(text[:5000])
    except Exception:
        pass
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
        # RAG: chunk the text and index embeddings into FAISS
        try:
            def chunk_text(s: str, chunk_size: int = 500, overlap: int = 100):
                s = s or ""
                chunks = []
                i = 0
                L = len(s)
                while i < L:
                    chunk = s[i: i + chunk_size]
                    chunks.append(chunk)
                    i += chunk_size - overlap
                return chunks

            chunks = chunk_text(text, chunk_size=500, overlap=100)
            if chunks:
                vectorstore.add_chunks(emp.id, chunks)
                # annotate job meta with chunk count
                try:
                    import json as _json

                    ppath = os.path.join(JOB_DIR, f"{job_id}.json")
                    if os.path.exists(ppath):
                        with open(ppath, "r", encoding="utf-8") as jf:
                            info = _json.load(jf)
                    else:
                        info = {"status": "done", "employee_id": emp.id, "filename": filename}
                    info["chunks_indexed"] = len(chunks)
                    with open(ppath, "w", encoding="utf-8") as jf:
                        jf.write(_json.dumps(info))
                except Exception:
                    pass
        except Exception:
            pass
        # LLM-driven structured extraction: ask the model to return JSON with name/email/phone
        try:
            extraction_prompt = (
                "You are a JSON extraction assistant. Given the following resume text,"
                " extract the candidate's full name, primary email address, and phone number."
                " Return ONLY valid JSON with keys: name, email, phone. If a value is not present, return null."
                " Resume text:\n\n" + (text[:4000] or "")
            )
            # write prompt log for this job
            try:
                with open(os.path.join(JOB_DIR, f"{job_id}.prompt.txt"), "w", encoding="utf-8") as pf:
                    pf.write(extraction_prompt[:10000])
            except Exception:
                pass

            extraction_resp = llm.generate(extraction_prompt, timeout=30)
            # attempt to parse JSON from the response
            import json as _json

            parsed = None
            try:
                parsed = _json.loads(extraction_resp)
            except Exception:
                # try to extract JSON substring
                import re

                m = re.search(r"\{.*\}", extraction_resp, re.S)
                if m:
                    try:
                        parsed = _json.loads(m.group(0))
                    except Exception:
                        parsed = None
            # Validate and potentially re-prompt using pydantic
            from pydantic import BaseModel, ValidationError

            class ExtractionModel(BaseModel):
                name: str | None = None
                email: str | None = None
                phone: str | None = None

            parsed_model = None
            if isinstance(parsed, dict):
                try:
                    parsed_model = ExtractionModel(**parsed)
                except ValidationError:
                    parsed_model = None

            # If parsed_model is missing 'name', try a stricter re-prompt once
            if not parsed_model or not parsed_model.name:
                try:
                    retry_prompt = (
                        "You are a JSON extraction assistant. Return STRICT JSON only with keys:"
                        " name, email, phone. Use null for missing values. Do NOT include any explanation."
                        " Here is the resume text:\n\n" + (text[:6000] or "")
                    )
                    # write retry prompt log
                    try:
                        with open(os.path.join(JOB_DIR, f"{job_id}.prompt.retry.txt"), "w", encoding="utf-8") as pf:
                            pf.write(retry_prompt[:10000])
                    except Exception:
                        pass
                    retry_resp = llm.generate(retry_prompt, timeout=20)
                    parsed2 = None
                    try:
                        parsed2 = _json.loads(retry_resp)
                    except Exception:
                        m2 = re.search(r"\{.*\}", retry_resp, re.S)
                        if m2:
                            try:
                                parsed2 = _json.loads(m2.group(0))
                            except Exception:
                                parsed2 = None
                    if isinstance(parsed2, dict):
                        try:
                            parsed_model = ExtractionModel(**parsed2)
                        except ValidationError:
                            parsed_model = None
                except Exception:
                    parsed_model = parsed_model

            if parsed_model:
                name_val = parsed_model.name
                email_val = parsed_model.email
                phone_val = parsed_model.phone
                if name_val:
                    emp.name = name_val
                if email_val:
                    emp.email = email_val
                if phone_val:
                    try:
                        setattr(emp, "phone", phone_val)
                    except Exception:
                        pass
                db.add(emp)
                db.commit()
        except Exception as e:
            # non-fatal: record extraction error in job file
            try:
                with open(os.path.join(JOB_DIR, f"{job_id}.json"), "r", encoding="utf-8") as jf:
                    info = _json.load(jf)
            except Exception:
                info = {"status": "done", "employee_id": emp.id, "filename": filename}
            info["extraction_error"] = str(e)
            try:
                with open(os.path.join(JOB_DIR, f"{job_id}.json"), "w", encoding="utf-8") as jf:
                    jf.write(_json.dumps(info))
            except Exception:
                pass
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
                # RAG: retrieve top relevant chunks for this employee and include them first
                try:
                    retrieved = vectorstore.search(req.prompt, top_k=5, employee_id=req.employee_id)
                except Exception:
                    retrieved = []
                retrieved_text = "\n\n---\n\n".join([r.get("text", "") for r in retrieved])
                if retrieved_text.strip():
                    prompt = f"Relevant resume excerpts:\n{retrieved_text}\n\nEmployee record:\n{emp.raw_text[:1000]}\n\nUser prompt:\n{req.prompt}"
                else:
                    prompt = f"Employee record:\n{emp.raw_text[:1000]}\n\nUser prompt:\n{req.prompt}"
        finally:
            db.close()

    # log chat prompt to file for debugging (timestamped)
    try:
        import time, json as _json

        ts = int(time.time() * 1000)
        fname = os.path.join(PROMPT_LOG_DIR, f"chat_{ts}.json")
        with open(fname, "w", encoding="utf-8") as pf:
            pf.write(_json.dumps({"employee_id": req.employee_id, "prompt": prompt})[:20000])
    except Exception:
        pass

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



@app.get("/api/employee/{employee_id}/raw")
def employee_raw(employee_id: int, chars: int = 2000):
    """Return a short excerpt and metadata for an employee's raw_text for debugging.

    Query params:
      - chars (int): how many characters to return (default 2000)
    """
    from sqlalchemy.orm import Session

    db: Session = SessionLocal()
    try:
        emp = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
        if not emp:
            return {"error": "not_found"}
        raw = emp.raw_text or ""
        return {"employee_id": emp.id, "filename": emp.name, "raw_len": len(raw), "excerpt": raw[:chars]}
    finally:
        db.close()


@app.get("/api/storage-status")
def storage_status():
    """Return storage backend diagnostics: whether GridFS is configured and a quick test save/read when possible."""
    info = {"storage_backend": storage.__class__.__name__}
    # if GridFS is active, try a small roundtrip
    try:
        if getattr(storage, "fs", None):
            tid = storage.save_file(b"healthcheck", filename="_health.txt")
            data = storage.get_file(tid)
            ok = data == b"healthcheck"
            info.update({"gridfs": True, "roundtrip_ok": ok, "last_id": tid})
        else:
            info.update({"gridfs": False})
    except Exception as e:
        info.update({"error": str(e)})
    return info


@app.get("/api/db-status")
def db_status():
    """Return simple DB diagnostics: which URL is in use and whether a simple query works."""
    try:
        url = os.getenv("DATABASE_URL") or f"sqlite:///./backend_dev.db"
        # quick query
        from sqlalchemy import text

        with engine.connect() as conn:
            res = conn.execute(text("SELECT 1"))
            ok = True
    except Exception as e:
        return {"ok": False, "error": str(e), "database_url": url}
    return {"ok": True, "database_url": url}


@app.post("/api/nl-command")
def nl_command(body: dict):
    """Parse a natural-language CRUD command into a proposed DB action using the LLM and record it as pending.

    Request JSON: { "command": "Update employee X's email to ..." }
    Response: { "pending_id": "...", "proposal": {...} }
    """
    cmd = body.get("command") if isinstance(body, dict) else None
    if not cmd:
        raise HTTPException(status_code=400, detail="Missing 'command' in request body")

    # Ask the LLM to convert NL to a JSON action
    parse_prompt = (
        "You are a JSON action parser. Convert the user's natural language command into a JSON object with keys:\n"
        "action: one of [create, read, update, delete],\n"
        "employee_id: integer or null,\n"
        "fields: object of fields to set (for create/update),\n"
        "Return ONLY valid JSON. Example: {\"action\":\"update\", \"employee_id\":123, \"fields\":{\"email\":\"x@y.com\"}}\n\n"
        f"User command:\n{cmd}\n"
    )

    try:
        parse_resp = llm.generate(parse_prompt, timeout=20)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM parse failed: {e}")

    # try to parse JSON out of response
    import json as _json, re

    proposal = None
    try:
        proposal = _json.loads(parse_resp)
    except Exception:
        m = re.search(r"\{.*\}", parse_resp, re.S)
        if m:
            try:
                proposal = _json.loads(m.group(0))
            except Exception:
                proposal = None

    pending_id = str(uuid.uuid4())
    pending = {"command": cmd, "proposal": proposal, "raw_response": parse_resp}
    try:
        with open(os.path.join(JOB_DIR, f"nl_{pending_id}.json"), "w", encoding="utf-8") as pf:
            pf.write(_json.dumps(pending))
    except Exception:
        pass

    return {"pending_id": pending_id, "proposal": proposal, "raw": parse_resp}


@app.get("/api/nl/{pending_id}")
def nl_get(pending_id: str):
    path = os.path.join(JOB_DIR, f"nl_{pending_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="not found")
    import json

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/nl/{pending_id}/confirm")
def nl_confirm(pending_id: str, confirm: dict | None = None):
    """Apply a previously parsed NL proposal to the DB.

    Body may include { "apply": true } (optional). Returns the DB result.
    """
    path = os.path.join(JOB_DIR, f"nl_{pending_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="not found")
    import json

    with open(path, "r", encoding="utf-8") as f:
        pending = json.load(f)

    proposal = pending.get("proposal")
    if not proposal or not isinstance(proposal, dict):
        raise HTTPException(status_code=400, detail="No valid proposal to apply")

    action = proposal.get("action")
    emp_id = proposal.get("employee_id")
    fields = proposal.get("fields") or {}

    from sqlalchemy.orm import Session

    db: Session = SessionLocal()
    try:
        if action == "create":
            emp = models.Employee(name=fields.get("name") or "", email=fields.get("email"), raw_text=fields.get("raw_text"))
            db.add(emp)
            db.commit()
            db.refresh(emp)
            res = {"status": "created", "employee_id": emp.id}
        elif action == "update":
            if not emp_id:
                raise HTTPException(status_code=400, detail="employee_id required for update")
            emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
            if not emp:
                raise HTTPException(status_code=404, detail="employee not found")
            for k, v in fields.items():
                if hasattr(emp, k):
                    setattr(emp, k, v)
            db.add(emp)
            db.commit()
            res = {"status": "updated", "employee_id": emp.id}
        elif action == "delete":
            if not emp_id:
                raise HTTPException(status_code=400, detail="employee_id required for delete")
            emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
            if not emp:
                raise HTTPException(status_code=404, detail="employee not found")
            db.delete(emp)
            db.commit()
            res = {"status": "deleted", "employee_id": emp_id}
        elif action == "read":
            if not emp_id:
                raise HTTPException(status_code=400, detail="employee_id required for read")
            emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
            if not emp:
                raise HTTPException(status_code=404, detail="employee not found")
            res = {"status": "ok", "employee": {"id": emp.id, "name": emp.name, "email": emp.email, "raw_len": len(emp.raw_text or "")}}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    finally:
        db.close()

    # mark pending as applied
    pending["applied"] = res
    try:
        with open(path, "w", encoding="utf-8") as pf:
            pf.write(json.dumps(pending))
    except Exception:
        pass

    return res
