import os
import uuid
import tempfile
import subprocess
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()  # This must be called before importing other modules that use os.getenv()

from app.services.storage import Storage
from app.services.extractor import extract_text_from_bytes
from app.services.llm_adapter import OllamaAdapter
from app.services.embeddings import Embeddings
from app.services.vectorstore_faiss import FaissVectorStore
from app.db.session import SessionLocal, engine
from app.db import models

# Configure logging BEFORE migrations (needed for migration logging)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cv-chat")

models.Base.metadata.create_all(bind=engine)

# Comprehensive migration for all Employee fields
try:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    cols = [c["name"] for c in inspector.get_columns("employees")]

    # Define all new columns with their types
    new_columns = {
        "employee_id": "VARCHAR(6) UNIQUE",
        "phone": "VARCHAR(64)",
        "department": "VARCHAR(128)",
        "position": "VARCHAR(128)",
        "linkedin_url": "VARCHAR(512)",
        "portfolio_url": "VARCHAR(512)",
        "github_url": "VARCHAR(512)",
        "career_objective": "TEXT",
        "summary": "TEXT",
        "work_experience": "TEXT",
        "education": "TEXT",
        "technical_skills": "TEXT",
        "soft_skills": "TEXT",
        "languages": "TEXT",
        "certifications": "TEXT",
        "achievements": "TEXT",
        "hobbies": "TEXT",
        "cocurricular_activities": "TEXT",
        "address": "TEXT",
        "city": "VARCHAR(128)",
        "country": "VARCHAR(128)",
        "extracted_text": "TEXT"
    }

    # Add missing columns
    with engine.connect() as conn:
        for col_name, col_type in new_columns.items():
            if col_name not in cols:
                try:
                    conn.execute(text(f"ALTER TABLE employees ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                    logger.info(f"Added column: {col_name}")
                except Exception as e:
                    logger.warning(f"Could not add column {col_name}: {e}")

        # Create sequence for employee_id if it doesn't exist (PostgreSQL)
        try:
            conn.execute(text("CREATE SEQUENCE IF NOT EXISTS employee_id_seq START 1"))
            conn.commit()
        except Exception:
            pass  # SQLite doesn't support sequences

        # Update existing records with employee_id if NULL
        try:
            result = conn.execute(text("SELECT id FROM employees WHERE employee_id IS NULL ORDER BY id"))
            for row in result:
                emp_id = row[0]
                # Generate employee_id in format 013449 (6 digits, zero-padded)
                employee_id = str(emp_id).zfill(6)
                conn.execute(text(f"UPDATE employees SET employee_id = '{employee_id}' WHERE id = {emp_id}"))
            conn.commit()
        except Exception as e:
            logger.warning(f"Could not update employee_id: {e}")

except Exception as e:
    logger.error(f"Migration error: {e}")
    # non-fatal; if alter fails it's likely the DB doesn't support it or column exists
    pass

app = FastAPI(title="CV Chat PoC")


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

# Conversation memory store (session_id -> conversation history)
# In production, use Redis or PostgreSQL for persistence
from collections import defaultdict, deque
conversation_store = defaultdict(lambda: deque(maxlen=10))  # Keep last 10 messages per session

# Active employee store (session_id -> employee_id)
# Tracks which employee is being discussed in each session for context continuity
active_employee_store = {}  # {session_id: employee_id}


@app.get("/api/llm-health")
def llm_health():
    """Health check for Ollama availability. Returns basic diagnostics.

    - If OLLAMA_API_URL is set, tries HTTP endpoint.
    - Otherwise tries the CLI.
    """
    try:
        sample = llm.generate("Say hello and return a short token: HELLO_TEST")
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
async def upload_cv(file: UploadFile = File(...)):
    """Upload a CV/resume PDF for processing."""
    import threading

    logger.info(f"[UPLOAD] ========== UPLOAD REQUEST RECEIVED ==========")
    logger.info(f"[UPLOAD] Filename: {file.filename}")

    # save raw file to storage (GridFS or local fallback)
    contents = await file.read()
    logger.info(f"[UPLOAD] Read {len(contents)} bytes from upload")

    file_id = storage.save_file(contents, filename=file.filename)
    logger.info(f"[UPLOAD] Saved file with id: {file_id}")

    job_id = str(uuid.uuid4())
    logger.info(f"[UPLOAD] Generated job_id: {job_id}")

    # Use a direct thread instead of BackgroundTasks to ensure it runs
    # BackgroundTasks can sometimes have issues with blocking calls
    logger.info(f"[UPLOAD] Starting background thread for processing...")

    def run_process_cv():
        try:
            logger.info(f"[THREAD] Thread started for job {job_id}")
            process_cv(file_id, file.filename, job_id)
            logger.info(f"[THREAD] Thread completed for job {job_id}")
        except Exception as e:
            logger.exception(f"[THREAD] Thread exception for job {job_id}: {e}")

    thread = threading.Thread(target=run_process_cv, daemon=True)
    thread.start()
    logger.info(f"[UPLOAD] Background thread started, returning response")

    return {"job_id": job_id, "status": "queued"}


def process_cv(file_id: str, filename: str, job_id: str):
    """Process CV in background thread.

    NOTE: This is intentionally NOT async because it contains blocking calls
    (subprocess.run, requests.post). FastAPI's BackgroundTasks will run this
    in a thread pool automatically when it's a regular function.
    """
    logger.info(f"[PROCESS_CV] ========== STARTING BACKGROUND TASK ==========")
    logger.info(f"[PROCESS_CV] job_id={job_id}, file_id={file_id}, filename={filename}")
    logger.info(f"[PROCESS_CV] JOB_DIR={JOB_DIR}")
    logger.info(f"[PROCESS_CV] JOB_DIR exists: {os.path.exists(JOB_DIR)}")

    # Write initial "processing" status
    try:
        os.makedirs(JOB_DIR, exist_ok=True)  # Ensure directory exists
        job_path = os.path.join(JOB_DIR, f"{job_id}.json")
        with open(job_path, "w", encoding="utf-8") as jf:
            jf.write('{"status":"processing","filename":"' + filename + '"}')
        logger.info(f"[PROCESS_CV] ✓ Wrote initial job status to {job_path}")
    except Exception as e:
        logger.error(f"[PROCESS_CV] ✗ Failed to write initial job status: {e}")

    # fetch file bytes
    logger.info(f"[PROCESS_CV] → Fetching file from storage: {file_id}")
    data = storage.get_file(file_id)
    if not data:
        logger.error(f"[PROCESS_CV] ✗ Failed to fetch file from storage: {file_id}")
        # mark job as failed
        try:
            with open(os.path.join(JOB_DIR, f"{job_id}.json"), "w", encoding="utf-8") as jf:
                jf.write('{"status":"failed","reason":"file_not_found"}')
        except Exception as e:
            logger.error(f"[PROCESS_CV] ✗ Failed to write failure status: {e}")
        return

    logger.info(f"[PROCESS_CV] ✓ Fetched {len(data)} bytes from storage")

    # extract text
    logger.info(f"[PROCESS_CV] → Extracting text from PDF...")
    pdf_text = extract_text_from_bytes(data)
    logger.info(f"[PROCESS_CV] ✓ Extracted {len(pdf_text)} characters from PDF")

    # log the raw extracted text excerpt for debugging
    try:
        with open(os.path.join(JOB_DIR, f"{job_id}.extracted.txt"), "w", encoding="utf-8") as ef:
            ef.write(pdf_text[:5000])
        logger.info(f"[PROCESS_CV] ✓ Wrote extracted text to {job_id}.extracted.txt")
    except Exception as e:
        logger.error(f"[PROCESS_CV] ✗ Failed to write extracted text: {e}")
    # write a small debug marker for extraction length
    try:
        with open(os.path.join(JOB_DIR, f"{job_id}.meta.txt"), "w", encoding="utf-8") as mf:
            mf.write(f"extracted_len={len(pdf_text)}")
    except Exception:
        pass
    # Store employee into SQL DB with auto-generated employeeID
    from sqlalchemy.orm import Session
    import json as _json
    # Note: Extracted data will be saved as human-readable JSON after LLM extraction
    # using storage.save_extracted_data() which stores to MongoDB collection + local JSON file

    db: Session = SessionLocal()
    try:
        logger.info(f"[PROCESS_CV] {'='*50}")
        logger.info(f"[PROCESS_CV] Processing CV: {filename}")
        logger.info(f"[PROCESS_CV] Extracted text length: {len(pdf_text)} chars")
        logger.info(f"[PROCESS_CV] Text preview: {pdf_text[:200]}...")

        # Generate employee_id in format 013449 (6 digits, zero-padded)
        # Query the actual max employee_id value (not the auto-increment id)
        from sqlalchemy import text as sql_text  # Import with alias to avoid shadowing
        try:
            # Cast employee_id to integer to get the max, handling NULL and empty cases
            result = db.execute(sql_text(
                "SELECT COALESCE(MAX(CAST(employee_id AS INTEGER)), 0) + 1 FROM employees WHERE employee_id IS NOT NULL"
            )).scalar()
            next_id = result if result else 1
            logger.info(f"[PROCESS_CV] Next employee_id will be: {next_id}")
        except Exception as e:
            logger.warning(f"[PROCESS_CV] Could not get max employee_id: {e}")
            # Fallback: count existing records + 1
            try:
                count = db.query(models.Employee).count()
                next_id = count + 1
                logger.info(f"[PROCESS_CV] Using count-based fallback: {next_id}")
            except Exception as e2:
                logger.warning(f"[PROCESS_CV] Count fallback also failed: {e2}, using UUID-based ID")
                # Last resort: use UUID-based unique ID
                import time
                next_id = int(time.time()) % 1000000  # Use timestamp-based ID
                logger.info(f"[PROCESS_CV] Using timestamp-based ID: {next_id}")

        employee_id = str(next_id).zfill(6)  # Format: 013449
        logger.info(f"[PROCESS_CV] Generated employee_id: {employee_id}")

        emp = models.Employee(
            employee_id=employee_id,
            name=filename,  # Will be updated by LLM extraction
            raw_text=pdf_text,
            extracted_text=pdf_text
        )
        db.add(emp)
        db.commit()
        db.refresh(emp)
        logger.info(f"[PROCESS_CV] ✓ Created employee record: ID={emp.id}, employee_id={emp.employee_id}")
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

            chunks = chunk_text(pdf_text, chunk_size=500, overlap=100)
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
        # LLM-driven COMPREHENSIVE structured extraction
        logger.info(f"[PROCESS_CV] → Starting LLM extraction...")
        try:
            extraction_prompt = (
                "You are a professional resume parser. Extract ALL information from the resume into JSON format.\n\n"
                "CRITICAL RULES:\n"
                "1. Return ONLY valid JSON - no explanations\n"
                "2. Use null for missing fields\n"
                "3. Do NOT guess or infer - only extract what's explicitly stated\n"
                "4. For arrays (work_experience, education, skills), use proper JSON arrays\n\n"
                "Required JSON structure:\n"
                "{\n"
                '  "name": "Full name",\n'
                '  "email": "email@example.com",\n'
                '  "phone": "+1-234-567-8900",\n'
                '  "linkedin_url": "https://linkedin.com/in/...",\n'
                '  "portfolio_url": "https://...",\n'
                '  "github_url": "https://github.com/...",\n'
                '  "department": "IT/HR/Engineering/etc",\n'
                '  "position": "Job title",\n'
                '  "career_objective": "Career objective/summary text",\n'
                '  "summary": "Professional summary",\n'
                '  "work_experience": ["Company: XYZ, Role: Engineer, Duration: 2020-2023, Responsibilities: ..."],\n'
                '  "education": ["Degree: BS Computer Science, University: MIT, Year: 2020, GPA: 3.8"],\n'
                '  "technical_skills": ["Python", "Java", "React", "AWS"],\n'
                '  "soft_skills": ["Leadership", "Communication"],\n'
                '  "languages": ["English (Native)", "Spanish (Fluent)"],\n'
                '  "certifications": ["AWS Certified", "PMP"],\n'
                '  "achievements": ["Won hackathon", "Published paper"],\n'
                '  "hobbies": ["Photography", "Hiking"],\n'
                '  "cocurricular_activities": ["President of CS Club"],\n'
                '  "address": "Full address",\n'
                '  "city": "City name",\n'
                '  "country": "Country name"\n'
                "}\n\n"
                f"Resume text:\n\n{pdf_text[:8000]}\n\n"
                "JSON output:"
            )
            # write prompt log for this job
            try:
                with open(os.path.join(JOB_DIR, f"{job_id}.prompt.txt"), "w", encoding="utf-8") as pf:
                    pf.write(extraction_prompt[:10000])
            except Exception:
                pass

            logger.info(f"[PROCESS_CV] → Sending extraction prompt to LLM ({len(extraction_prompt)} chars)...")
            extraction_resp = llm.generate(extraction_prompt)
            logger.info(f"[PROCESS_CV] ✓ LLM response received: {len(extraction_resp)} chars")
            logger.info(f"[PROCESS_CV] → LLM response preview: {extraction_resp[:300]}...")
            # attempt to parse JSON from the response
            import json as _json

            parsed = None
            try:
                parsed = _json.loads(extraction_resp)
                logger.info(f"[PROCESS_CV] ✓ JSON parsed directly from LLM response")
            except Exception as e:
                logger.warning(f"[PROCESS_CV] ✗ Direct JSON parse failed: {e}")
                # try to extract JSON substring
                import re

                m = re.search(r"\{.*\}", extraction_resp, re.S)
                if m:
                    logger.info(f"[PROCESS_CV] → Found JSON substring in response, attempting parse...")
                    try:
                        parsed = _json.loads(m.group(0))
                        logger.info(f"[PROCESS_CV] ✓ JSON extracted from substring")
                    except Exception as e2:
                        logger.error(f"[PROCESS_CV] ✗ JSON substring parse also failed: {e2}")
                        parsed = None
                else:
                    logger.error(f"[PROCESS_CV] ✗ No JSON found in LLM response!")

            # Log parsed content
            if parsed:
                logger.info(f"[PROCESS_CV] → Parsed JSON keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'NOT A DICT'}")
                if isinstance(parsed, dict):
                    logger.info(f"[PROCESS_CV] → Parsed name: '{parsed.get('name')}'")
                    logger.info(f"[PROCESS_CV] → Parsed email: '{parsed.get('email')}'")
            else:
                logger.error(f"[PROCESS_CV] ✗ No parsed data available - employee will have default values!")

            # Validate using comprehensive Pydantic model
            from pydantic import BaseModel, ValidationError, field_validator
            from typing import List, Any
            import json as _json_validator

            class ComprehensiveExtractionModel(BaseModel):
                # Basic Information
                name: str | None = None
                email: str | None = None
                phone: str | None = None

                # Online Presence
                linkedin_url: str | None = None
                portfolio_url: str | None = None
                github_url: str | None = None

                # Professional Info
                department: str | None = None
                position: str | None = None
                career_objective: str | None = None
                summary: str | None = None

                # Experience & Education (arrays) - Accept strings or dicts, convert dicts to JSON strings
                work_experience: List[Any] | None = None
                education: List[Any] | None = None

                # Skills (arrays) - Accept strings or dicts
                technical_skills: List[Any] | None = None
                soft_skills: List[Any] | None = None
                languages: List[Any] | None = None

                # Additional (arrays) - Accept strings or dicts
                certifications: List[Any] | None = None
                achievements: List[Any] | None = None
                hobbies: List[Any] | None = None
                cocurricular_activities: List[Any] | None = None

                # Convert dict items to JSON strings for storage
                @field_validator('work_experience', 'education', 'technical_skills', 'soft_skills',
                               'languages', 'certifications', 'achievements', 'hobbies',
                               'cocurricular_activities', mode='before')
                @classmethod
                def convert_dicts_to_strings(cls, v):
                    if v is None:
                        return None
                    if isinstance(v, list):
                        result = []
                        for item in v:
                            if isinstance(item, dict):
                                # Convert dict to readable string
                                result.append(_json_validator.dumps(item, ensure_ascii=False))
                            else:
                                result.append(str(item) if item is not None else None)
                        return result
                    return v

                # Location
                address: str | None = None
                city: str | None = None
                country: str | None = None

            parsed_model = None
            if isinstance(parsed, dict):
                try:
                    parsed_model = ComprehensiveExtractionModel(**parsed)
                    logger.info(f"[PROCESS_CV] ✓ Pydantic validation passed")
                    logger.info(f"[PROCESS_CV] → Validated name: '{parsed_model.name}'")
                    logger.info(f"[PROCESS_CV] → Validated email: '{parsed_model.email}'")
                except ValidationError as ve:
                    logger.warning(f"[PROCESS_CV] ✗ Validation error during extraction: {ve}")
                    parsed_model = None
            else:
                logger.error(f"[PROCESS_CV] ✗ Parsed data is not a dict: {type(parsed)}")

            # If parsed_model is missing 'name', try a stricter re-prompt once
            if not parsed_model or not parsed_model.name:
                logger.warning(f"[PROCESS_CV] → Name not found in first extraction, trying retry prompt...")
                try:
                    retry_prompt = (
                        "CRITICAL: Extract resume data as STRICT JSON only. NO explanations.\n\n"
                        "Return JSON with these keys (use null if not found):\n"
                        "name, email, phone, linkedin_url, portfolio_url, github_url, department, position, "
                        "career_objective, summary, work_experience, education, technical_skills, soft_skills, "
                        "languages, certifications, achievements, hobbies, cocurricular_activities, address, city, country\n\n"
                        "Arrays must use JSON array format: [\"item1\", \"item2\"]\n\n"
                        f"Resume:\n\n{pdf_text[:8000]}\n\nJSON:"
                    )
                    # write retry prompt log
                    try:
                        with open(os.path.join(JOB_DIR, f"{job_id}.prompt.retry.txt"), "w", encoding="utf-8") as pf:
                            pf.write(retry_prompt[:10000])
                    except Exception:
                        pass
                    logger.info(f"[PROCESS_CV] → Sending retry prompt to LLM...")
                    retry_resp = llm.generate(retry_prompt)
                    logger.info(f"[PROCESS_CV] ✓ Retry response received: {len(retry_resp)} chars")
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
                            parsed_model = ComprehensiveExtractionModel(**parsed2)
                        except ValidationError as ve:
                            logger.warning(f"Retry validation error: {ve}")
                            parsed_model = None
                except Exception as e:
                    logger.error(f"Retry extraction failed: {e}")
                    parsed_model = parsed_model

            if parsed_model:
                logger.info(f"[PROCESS_CV] ✓ Final parsed_model available, setting fields...")
                logger.info(f"[PROCESS_CV] → Final extracted name: '{parsed_model.name}'")
                logger.info(f"[PROCESS_CV] → Final extracted email: '{parsed_model.email}'")
                logger.info(f"[PROCESS_CV] → Final extracted phone: '{parsed_model.phone}'")
                logger.info(f"[PROCESS_CV] → Final extracted position: '{parsed_model.position}'")

                # Helper function to safely set attributes and convert arrays to JSON
                def safe_set(obj, attr, value):
                    if value is not None:
                        try:
                            # Convert lists to JSON string for TEXT columns
                            if isinstance(value, list):
                                value = _json.dumps(value, ensure_ascii=False)
                            setattr(obj, attr, value)
                            logger.info(f"[PROCESS_CV] → Set {attr} = '{str(value)[:50]}{'...' if len(str(value)) > 50 else ''}'")
                        except Exception as e:
                            logger.warning(f"[PROCESS_CV] ✗ Could not set {attr}: {e}")
                    else:
                        logger.debug(f"[PROCESS_CV] → Skipping {attr} (value is None)")

                # Set all basic information
                safe_set(emp, "name", parsed_model.name)
                safe_set(emp, "email", parsed_model.email)
                safe_set(emp, "phone", parsed_model.phone)

                # Set online presence
                safe_set(emp, "linkedin_url", parsed_model.linkedin_url)
                safe_set(emp, "portfolio_url", parsed_model.portfolio_url)
                safe_set(emp, "github_url", parsed_model.github_url)

                # Set professional info
                safe_set(emp, "department", parsed_model.department)
                safe_set(emp, "position", parsed_model.position)
                safe_set(emp, "career_objective", parsed_model.career_objective)
                safe_set(emp, "summary", parsed_model.summary)

                # Set experience & education (arrays → JSON)
                safe_set(emp, "work_experience", parsed_model.work_experience)
                safe_set(emp, "education", parsed_model.education)

                # Set skills (arrays → JSON)
                safe_set(emp, "technical_skills", parsed_model.technical_skills)
                safe_set(emp, "soft_skills", parsed_model.soft_skills)
                safe_set(emp, "languages", parsed_model.languages)

                # Set additional info (arrays → JSON)
                safe_set(emp, "certifications", parsed_model.certifications)
                safe_set(emp, "achievements", parsed_model.achievements)
                safe_set(emp, "hobbies", parsed_model.hobbies)
                safe_set(emp, "cocurricular_activities", parsed_model.cocurricular_activities)

                # Set location
                safe_set(emp, "address", parsed_model.address)
                safe_set(emp, "city", parsed_model.city)
                safe_set(emp, "country", parsed_model.country)

                db.add(emp)
                db.commit()
                logger.info(f"[PROCESS_CV] ✓ Successfully extracted and saved comprehensive data for employee {emp.employee_id}")
                logger.info(f"[PROCESS_CV] → Final employee record: name='{emp.name}', email='{emp.email}'")

                # Save extracted data as human-readable JSON to MongoDB and file
                try:
                    extracted_json = {
                        "name": parsed_model.name,
                        "email": parsed_model.email,
                        "phone": parsed_model.phone,
                        "linkedin_url": parsed_model.linkedin_url,
                        "portfolio_url": parsed_model.portfolio_url,
                        "github_url": parsed_model.github_url,
                        "department": parsed_model.department,
                        "position": parsed_model.position,
                        "career_objective": parsed_model.career_objective,
                        "summary": parsed_model.summary,
                        "work_experience": parsed_model.work_experience,
                        "education": parsed_model.education,
                        "technical_skills": parsed_model.technical_skills,
                        "soft_skills": parsed_model.soft_skills,
                        "languages": parsed_model.languages,
                        "certifications": parsed_model.certifications,
                        "achievements": parsed_model.achievements,
                        "hobbies": parsed_model.hobbies,
                        "cocurricular_activities": parsed_model.cocurricular_activities,
                        "address": parsed_model.address,
                        "city": parsed_model.city,
                        "country": parsed_model.country,
                        "raw_text_preview": pdf_text[:1000] if pdf_text else None
                    }
                    doc_id = storage.save_extracted_data(emp.employee_id, filename, extracted_json)
                    logger.info(f"[PROCESS_CV] ✓ Saved extracted JSON to MongoDB/file: {doc_id}")
                except Exception as e:
                    logger.warning(f"[PROCESS_CV] ✗ Failed to save extracted JSON: {e}")
            else:
                logger.error(f"[PROCESS_CV] ✗ EXTRACTION FAILED - parsed_model is None!")
                logger.error(f"[PROCESS_CV] ✗ Employee will only have filename as name and raw_text!")
                logger.error(f"[PROCESS_CV] → Check the LLM response and prompt logs in {JOB_DIR}")
        except Exception as e:
            logger.exception(f"[PROCESS_CV] ✗ Exception during LLM extraction: {e}")
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
    session_id: str | None = None  # For conversation memory


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
    logger.info(f"{'='*60}")
    logger.info(f"[CHAT] Request received via {request.method}")
    logger.info(f"[CHAT] Prompt: '{req.prompt[:100]}{'...' if len(req.prompt) > 100 else ''}'")
    logger.info(f"[CHAT] Employee ID from request: {req.employee_id}")
    logger.info(f"[CHAT] Session ID from request: {req.session_id}")

    prompt = req.prompt
    session_id = req.session_id or str(uuid.uuid4())  # Generate session ID if not provided
    logger.info(f"[CHAT] Using session ID: {session_id}")

    # Retrieve conversation history for this session
    conversation_history = list(conversation_store[session_id])
    logger.info(f"[CHAT] Conversation history: {len(conversation_history)} messages")

    # Detect if this is a CRUD command and route accordingly
    crud_keywords = ["update", "delete", "remove", "create", "add", "change", "modify", "set"]
    is_crud = any(keyword in prompt.lower() for keyword in crud_keywords)

    # Check for employee-related context (e.g., "employee", "record", name patterns)
    # Also check if any employee name from the database is mentioned in the prompt
    has_employee_context = any(word in prompt.lower() for word in ["employee", "record", "person", "user", "from", "to", "candidate", "resume", "cv"])

    # For delete/remove commands, also try to find employee by name in DB
    if not has_employee_context and any(kw in prompt.lower() for kw in ["delete", "remove"]):
        # Check if any employee name is mentioned
        try:
            from sqlalchemy.orm import Session as TempSession
            temp_db: TempSession = SessionLocal()
            all_emps = temp_db.query(models.Employee).all()
            for e in all_emps:
                if e.name and e.name.lower() in prompt.lower():
                    has_employee_context = True
                    break
                # Also check partial name match
                if e.name:
                    for part in e.name.lower().split():
                        if len(part) > 2 and part in prompt.lower():
                            has_employee_context = True
                            break
            temp_db.close()
        except Exception:
            pass
    logger.info(f"[CHAT] CRUD detection: is_crud={is_crud}, has_employee_context={has_employee_context}")

    # =====================================================
    # COMPREHENSIVE LIST/READ DETECTION WITH ANTI-HALLUCINATION
    # Handles: "show me all employee records", "list employees",
    # "display everyone", "let me see all records", "what are the employee details",
    # "show John and Sarah's details", "get all employees with emails", etc.
    #
    # ANTI-HALLUCINATION: When query is ambiguous (mentions employees but
    # doesn't specify which one or "all"), ask for clarification instead
    # of letting the LLM hallucinate fake data.
    # =====================================================
    prompt_lower = prompt.lower()
    word_count = len(prompt_lower.split())

    # Comprehensive action keywords for LIST/READ operations
    action_keywords = [
        "show", "show me", "display", "list", "get", "fetch", "give me",
        "tell me", "what", "what are", "what is", "what's", "let me see", "i want to see",
        "can you show", "could you show", "please show", "view", "see",
        "who are", "who is", "how many", "count", "total"
    ]

    # Keywords indicating "all employees" / list query (including singular forms)
    all_employees_patterns = [
        "all employees", "all employee", "everyone", "all records", "all people",
        "all candidates", "employee records", "employee details", "employees",
        "all the employees", "all the records", "every employee", "each employee",
        "list of employees", "employee list", "people in the system",
        "everyone in the system", "all staff", "all personnel"
    ]

    # Keywords indicating SINGULAR/AMBIGUOUS employee reference (needs clarification)
    singular_employee_patterns = [
        "the employee record", "employee record", "the record", "this employee",
        "the employee", "that employee", "an employee", "employee details",
        "the candidate", "this candidate", "that candidate", "the person",
        "this person", "that person", "their details", "their info",
        "employee info", "employee information", "the employee's"
    ]

    # Check if this is a LIST ALL query
    has_action = any(kw in prompt_lower for kw in action_keywords)
    has_all_pattern = any(p in prompt_lower for p in all_employees_patterns)
    has_singular_pattern = any(p in prompt_lower for p in singular_employee_patterns)

    # Also detect direct patterns
    is_list_query = (has_action and has_all_pattern) or \
                    "show me all" in prompt_lower or \
                    "list all" in prompt_lower or \
                    "display all" in prompt_lower or \
                    "get all" in prompt_lower or \
                    "fetch all" in prompt_lower or \
                    "all employees" in prompt_lower or \
                    "employee records" in prompt_lower or \
                    "how many employees" in prompt_lower or \
                    "count employees" in prompt_lower or \
                    "total employees" in prompt_lower

    # =====================================================
    # Check for READ queries about SPECIFIC employees
    # "Show John's details", "What is Sarah's email?",
    # "Tell me about John and Sarah", etc.
    # =====================================================
    from sqlalchemy.orm import Session
    db: Session = SessionLocal()

    try:
        all_employees = db.query(models.Employee).all()

        # Find which employees are mentioned in the prompt
        mentioned_employees = []
        for emp in all_employees:
            if emp.name:
                name_lower = emp.name.lower()
                # Check full name match
                if name_lower in prompt_lower:
                    if emp not in mentioned_employees:
                        mentioned_employees.append(emp)
                else:
                    # Check partial name match (first name, last name)
                    for part in name_lower.split():
                        if len(part) > 2 and part in prompt_lower:
                            if emp not in mentioned_employees:
                                mentioned_employees.append(emp)
                            break

        # Detect READ query for specific person(s)
        # Patterns: "John's details", "about John", "tell me about", "show me John"
        read_patterns = [
            "'s details", "'s info", "'s information", "'s profile", "'s record",
            "'s email", "'s phone", "'s department", "'s position", "'s role",
            "'s skills", "'s experience", "'s education", "'s contact",
            "about ", "details of ", "info of ", "information about ", "profile of "
        ]
        is_read_specific = len(mentioned_employees) > 0 and (
            any(p in prompt_lower for p in read_patterns) or
            any(p in prompt_lower for p in action_keywords)
        )

        # =====================================================
        # HANDLE LIST ALL EMPLOYEES QUERY
        # =====================================================
        if is_list_query and len(mentioned_employees) == 0:
            logger.info(f"[CHAT] → Detected LIST ALL employees query")

            if not all_employees:
                return {
                    "reply": "No employee records found in the database.",
                    "session_id": session_id,
                    "employee_id": None,
                    "employee_name": None
                }

            # Determine which fields the user wants to see
            want_email = any(w in prompt_lower for w in ["email", "emails", "mail", "contact"])
            want_phone = any(w in prompt_lower for w in ["phone", "phones", "number", "numbers", "mobile", "telephone"])
            want_department = any(w in prompt_lower for w in ["department", "departments", "dept", "team"])
            want_position = any(w in prompt_lower for w in ["position", "positions", "role", "roles", "title", "job", "designation"])
            want_skills = any(w in prompt_lower for w in ["skill", "skills", "technical", "expertise"])
            want_education = any(w in prompt_lower for w in ["education", "degree", "university", "college", "qualification"])
            want_experience = any(w in prompt_lower for w in ["experience", "work history", "worked", "previous"])
            want_address = any(w in prompt_lower for w in ["address", "location", "city"])
            want_id = any(w in prompt_lower for w in ["id", "emp_id", "employee_id", "employee id"])

            # If no specific fields requested, show basic info
            no_specific_fields = not any([want_email, want_phone, want_department, want_position, want_skills, want_education, want_experience, want_address])

            # Handle count queries
            if "how many" in prompt_lower or "count" in prompt_lower or "total" in prompt_lower:
                return {
                    "reply": f"There are **{len(all_employees)}** employee(s) in the database.",
                    "session_id": session_id,
                    "employee_id": None,
                    "employee_name": None
                }

            # Build the response
            response_lines = []
            response_lines.append(f"## Employee Records ({len(all_employees)} total)\n")

            for emp in all_employees:
                line_parts = [f"### {emp.name or 'Unknown'}"]
                line_parts.append(f"- **Employee ID**: {emp.employee_id or emp.id}")

                if no_specific_fields or want_email:
                    email = emp.email or 'N/A'
                    line_parts.append(f"- **Email**: {email}")

                if no_specific_fields or want_phone:
                    phone = getattr(emp, 'phone', None) or 'N/A'
                    line_parts.append(f"- **Phone**: {phone}")

                if no_specific_fields or want_department:
                    dept = getattr(emp, 'department', None) or 'N/A'
                    line_parts.append(f"- **Department**: {dept}")

                if no_specific_fields or want_position:
                    pos = getattr(emp, 'position', None) or 'N/A'
                    line_parts.append(f"- **Position**: {pos}")

                if want_skills:
                    skills = getattr(emp, 'technical_skills', None) or 'N/A'
                    if skills and len(skills) > 150:
                        skills = skills[:150] + "..."
                    line_parts.append(f"- **Skills**: {skills}")

                if want_education:
                    edu = getattr(emp, 'education', None) or 'N/A'
                    if isinstance(edu, list):
                        edu = ", ".join(str(e) for e in edu[:3])
                    elif edu and len(str(edu)) > 100:
                        edu = str(edu)[:100] + "..."
                    line_parts.append(f"- **Education**: {edu}")

                if want_experience:
                    exp = getattr(emp, 'work_experience', None) or 'N/A'
                    if isinstance(exp, list):
                        exp = ", ".join(str(e) for e in exp[:3])
                    elif exp and len(str(exp)) > 100:
                        exp = str(exp)[:100] + "..."
                    line_parts.append(f"- **Experience**: {exp}")

                if want_address:
                    addr = getattr(emp, 'address', None) or getattr(emp, 'location', None) or 'N/A'
                    line_parts.append(f"- **Address**: {addr}")

                response_lines.append("\n".join(line_parts))

            reply = "\n\n".join(response_lines)

            # Save to conversation memory
            conversation_store[session_id].append({"role": "user", "content": req.prompt})
            conversation_store[session_id].append({"role": "assistant", "content": reply})

            return {
                "reply": reply,
                "session_id": session_id,
                "employee_id": None,
                "employee_name": None
            }

        # =====================================================
        # HANDLE READ QUERY FOR SPECIFIC EMPLOYEE(S)
        # ALL queries go through LLM for natural conversation
        # We just set the employee context here and let it fall through
        # =====================================================
        elif is_read_specific or (len(mentioned_employees) > 0 and has_action):
            logger.info(f"[CHAT] → READ query for specific employee(s): {[e.name for e in mentioned_employees]}")
            logger.info(f"[CHAT] → Routing to LLM with employee context for natural response")

            # Store mentioned employees for LLM context
            # We'll use the first mentioned employee as context
            if mentioned_employees:
                first_emp = mentioned_employees[0]
                active_employee_store[session_id] = first_emp.id
                logger.info(f"[CHAT] → Set active employee for LLM context: {first_emp.name}")

            # Don't return here - fall through to LLM section for ALL queries

    finally:
        db.close()

    # =====================================================
    # ANTI-HALLUCINATION GUARD #1: AMBIGUOUS EMPLOYEE QUERIES
    # When query mentions employees but doesn't specify which one(s)
    # AND isn't clearly asking for "all", ask for clarification
    # instead of letting the LLM hallucinate fake data.
    # =====================================================

    # Check if query is about employees but ambiguous (no specific name, not "all")
    is_employee_related = has_action and (has_singular_pattern or has_employee_context)
    is_ambiguous_employee_query = is_employee_related and not is_list_query and len(mentioned_employees) == 0

    if is_ambiguous_employee_query and not is_crud:
        logger.info(f"[CHAT] → Detected AMBIGUOUS employee query - asking for clarification")

        # Get list of available employees for the clarification message
        from sqlalchemy.orm import Session as ClarifySession
        clarify_db: ClarifySession = SessionLocal()
        try:
            available_employees = clarify_db.query(models.Employee).all()
            if available_employees:
                emp_names = [e.name for e in available_employees if e.name]
                if emp_names:
                    emp_list = ", ".join(emp_names[:10])  # Show first 10
                    if len(emp_names) > 10:
                        emp_list += f", ... ({len(emp_names)} total)"
                    clarification_reply = (
                        f"Which employee would you like me to show?\n\n"
                        f"**Available employees:** {emp_list}\n\n"
                        f"You can say:\n"
                        f"- \"Show me **[name]**'s details\"\n"
                        f"- \"Display **all** employee records\"\n"
                        f"- \"What is **[name]**'s email?\""
                    )
                else:
                    clarification_reply = (
                        "Which employee would you like me to show? "
                        "Please specify the employee's name or say \"all employees\" to see everyone."
                    )
            else:
                clarification_reply = (
                    "There are no employee records in the database yet. "
                    "Please upload a CV/resume first to create an employee record."
                )
        finally:
            clarify_db.close()

        conversation_store[session_id].append({"role": "user", "content": req.prompt})
        conversation_store[session_id].append({"role": "assistant", "content": clarification_reply})

        return {
            "reply": clarification_reply,
            "session_id": session_id,
            "employee_id": None,
            "employee_name": None
        }

    # =====================================================
    # ANTI-HALLUCINATION GUARD #2: VERY SHORT PROMPTS
    # Prompts with < 3 words that mention employee-related terms
    # are likely ambiguous and need clarification
    # =====================================================
    short_employee_keywords = ["employee", "record", "details", "info", "skills", "experience", "email", "phone"]
    is_short_ambiguous = word_count <= 3 and any(kw in prompt_lower for kw in short_employee_keywords)

    if is_short_ambiguous and not is_crud and len(mentioned_employees) == 0:
        logger.info(f"[CHAT] → Detected SHORT AMBIGUOUS prompt - asking for clarification")

        clarification_reply = (
            f"Could you please be more specific? I'd be happy to help with employee information.\n\n"
            f"**You can ask things like:**\n"
            f"- \"Show me all employees\"\n"
            f"- \"What is John's email?\"\n"
            f"- \"Display Sarah's skills\"\n"
            f"- \"List everyone's department\""
        )

        conversation_store[session_id].append({"role": "user", "content": req.prompt})
        conversation_store[session_id].append({"role": "assistant", "content": clarification_reply})

        return {
            "reply": clarification_reply,
            "session_id": session_id,
            "employee_id": None,
            "employee_name": None
        }

    # =====================================================
    # ANTI-HALLUCINATION GUARD #3: NON-EXISTENT EMPLOYEE QUERIES
    # When user asks about a specific name that doesn't exist
    # =====================================================
    # Check for patterns like "tell me about X" or "X's details" where X is not in DB
    potential_name_patterns = [
        r"about\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",  # "about John Smith"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'s\s+",     # "John's details"
        r"employee\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", # "employee John"
    ]

    import re
    potential_names = []
    for pattern in potential_name_patterns:
        matches = re.findall(pattern, prompt)  # Use original case
        potential_names.extend(matches)

    if potential_names and len(mentioned_employees) == 0 and has_action:
        # User mentioned a name but no match found in DB
        from sqlalchemy.orm import Session as NameCheckSession
        name_db: NameCheckSession = SessionLocal()
        try:
            all_emp_names = [e.name.lower() for e in name_db.query(models.Employee).all() if e.name]

            # Check if any potential name is NOT in the database
            unmatched_names = [n for n in potential_names if n.lower() not in all_emp_names]

            if unmatched_names:
                logger.info(f"[CHAT] → Detected query about NON-EXISTENT employee: {unmatched_names}")

                available = name_db.query(models.Employee).all()
                if available:
                    emp_list = ", ".join([e.name for e in available if e.name][:10])
                    not_found_reply = (
                        f"I couldn't find an employee named **{unmatched_names[0]}** in the database.\n\n"
                        f"**Available employees:** {emp_list}\n\n"
                        f"Would you like to see one of these instead?"
                    )
                else:
                    not_found_reply = (
                        f"I couldn't find an employee named **{unmatched_names[0]}** in the database. "
                        f"There are no employee records yet. Please upload a CV first."
                    )

                conversation_store[session_id].append({"role": "user", "content": req.prompt})
                conversation_store[session_id].append({"role": "assistant", "content": not_found_reply})

                return {
                    "reply": not_found_reply,
                    "session_id": session_id,
                    "employee_id": None,
                    "employee_name": None
                }
        finally:
            name_db.close()

    # =====================================================
    # ANTI-HALLUCINATION GUARD #4: LEADING QUESTION TRAPS
    # Detect prompts that try to confirm false information
    # =====================================================
    leading_patterns = [
        r"(?:i heard|someone said|they said|i was told)\s+.*(?:worked at|knows|has|is)",
        r"(?:confirm|verify|validate)\s+(?:that|if)\s+",
        r"(?:isn't it true|it's true that|obviously|everyone knows)",
        r"(?:just say yes|just confirm|can you confirm)\s+",
    ]

    is_leading_question = any(re.search(p, prompt_lower) for p in leading_patterns)

    # =====================================================
    # ANTI-HALLUCINATION GUARD #5: PRESSURE/URGENCY PROMPTS
    # Detect emotional manipulation attempts
    # =====================================================
    pressure_patterns = [
        r"urgent", r"asap", r"immediately", r"right now", r"my job depends",
        r"ceo is waiting", r"board meeting", r"please.*really need",
        r"just this once", r"make an exception"
    ]

    is_pressure_prompt = any(re.search(p, prompt_lower) for p in pressure_patterns)

    # Re-open database for CRUD operations if needed
    # (The db was closed in the finally block above)

    if is_crud and has_employee_context:
        logger.info(f"[CHAT] → Routing to CRUD pipeline")
        # Route to NL-CRUD pipeline
        try:
            # Parse the command using the NL-CRUD parser
            parse_prompt = (
                "You are a JSON action parser. Convert the user's natural language command into a JSON object with keys:\n"
                "action: one of [create, read, update, delete],\n"
                "employee_id: integer or null,\n"
                "employee_name: name of the employee (string) or null (if name is mentioned in command, extract it here),\n"
                "fields: object of fields to set (for create/update). Allowed fields: name, email, phone, department, position.\n"
                "Return ONLY valid JSON.\n"
                "Examples:\n"
                "- 'Update Arun from IT to HR department' -> {\"action\":\"update\", \"employee_id\":null, \"employee_name\":\"Arun\", \"fields\":{\"department\":\"HR\"}}\n"
                "- 'Update employee 123 email to x@y.com' -> {\"action\":\"update\", \"employee_id\":123, \"employee_name\":null, \"fields\":{\"email\":\"x@y.com\"}}\n"
                "- 'Create employee John in IT' -> {\"action\":\"create\", \"employee_id\":null, \"employee_name\":null, \"fields\":{\"name\":\"John\", \"department\":\"IT\"}}\n"
                "- 'Delete John' -> {\"action\":\"delete\", \"employee_id\":null, \"employee_name\":\"John\", \"fields\":{}}\n"
                "- 'Remove employee 5' -> {\"action\":\"delete\", \"employee_id\":5, \"employee_name\":null, \"fields\":{}}\n"
                "- 'Delete the employee Arun Kumar' -> {\"action\":\"delete\", \"employee_id\":null, \"employee_name\":\"Arun Kumar\", \"fields\":{}}\n\n"
                f"User command:\n{prompt}\n"
            )

            parse_resp = llm.generate(parse_prompt)

            # Parse JSON
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

            if not proposal:
                # If parsing failed, fall back to normal chat
                logger.warning("CRUD detection triggered but parsing failed, falling back to normal chat")
            else:
                # Validate and execute the CRUD operation
                from sqlalchemy.orm import Session
                db: Session = SessionLocal()

                def resolve_employee(db, emp_id, emp_name):
                    if emp_id:
                        return db.query(models.Employee).filter(models.Employee.id == emp_id).first()
                    elif emp_name:
                        emp = db.query(models.Employee).filter(models.Employee.name.ilike(f"%{emp_name}%")).first()
                        if not emp:
                            emp = db.query(models.Employee).filter(models.Employee.name == emp_name).first()
                        return emp
                    return None

                try:
                    action = proposal.get("action")
                    emp_id = proposal.get("employee_id")
                    emp_name = proposal.get("employee_name")
                    fields = proposal.get("fields") or {}

                    if action == "update":
                        emp = resolve_employee(db, emp_id, emp_name)
                        if not emp:
                            return {"reply": f"I couldn't find an employee named '{emp_name}' or with ID {emp_id}. Could you provide more details?"}

                        # Build a confirmation message
                        changes = []
                        for k, v in fields.items():
                            if hasattr(emp, k):
                                old_val = getattr(emp, k)
                                setattr(emp, k, v)
                                changes.append(f"{k}: '{old_val}' → '{v}'")

                        db.add(emp)
                        db.commit()

                        reply = f"Updated employee **{emp.name}** (ID: {emp.id}):\n" + "\n".join(f"- {c}" for c in changes)
                        return {"reply": reply}

                    elif action == "create":
                        emp = models.Employee(
                            name=fields.get("name") or "Unknown",
                            email=fields.get("email"),
                            phone=fields.get("phone"),
                            department=fields.get("department"),
                            position=fields.get("position"),
                            raw_text=fields.get("raw_text")
                        )
                        db.add(emp)
                        db.commit()
                        db.refresh(emp)
                        return {"reply": f"Created new employee **{emp.name}** (ID: {emp.id}) in {emp.department or 'no department'}."}

                    elif action == "delete":
                        emp = resolve_employee(db, emp_id, emp_name)
                        if not emp:
                            return {"reply": f"I couldn't find an employee to delete with name '{emp_name}' or ID {emp_id}."}
                        emp_name_copy = emp.name
                        emp_id_copy = emp.id
                        db.delete(emp)
                        db.commit()
                        return {"reply": f"Deleted employee **{emp_name_copy}** (ID: {emp_id_copy})."}

                    elif action == "read":
                        emp = resolve_employee(db, emp_id, emp_name)
                        if not emp:
                            return {"reply": f"I couldn't find an employee with name '{emp_name}' or ID {emp_id}."}
                        info = [
                            f"**Name:** {emp.name}",
                            f"**ID:** {emp.id}",
                            f"**Email:** {emp.email or 'N/A'}",
                            f"**Phone:** {getattr(emp, 'phone', 'N/A') or 'N/A'}",
                            f"**Department:** {getattr(emp, 'department', 'N/A') or 'N/A'}",
                            f"**Position:** {getattr(emp, 'position', 'N/A') or 'N/A'}"
                        ]
                        return {"reply": "\n".join(info)}

                finally:
                    db.close()

        except Exception as e:
            logger.exception("CRUD operation failed in chat endpoint")
            # Fall back to normal chat on error
            pass

    # Fetch employee context - either by ID, session memory, or searching for name in prompt
    logger.info(f"[CHAT] → Starting employee lookup...")
    from sqlalchemy.orm import Session
    db: Session = SessionLocal()
    emp = None

    try:
        # =====================================================
        # PRIORITY FIX: ALWAYS search for employee in CURRENT prompt FIRST
        # This ensures we respond to the employee actually being asked about,
        # even if req.employee_id is set from a previous upload
        # =====================================================
        all_employees = db.query(models.Employee).all()
        logger.info(f"[CHAT] → Total employees in database: {len(all_employees)}")

        # Log all employee names for debugging
        if all_employees:
            names = [e.name for e in all_employees if e.name]
            logger.info(f"[CHAT] → Employee names in DB: {names}")

        # Step 1: Search for employee name in CURRENT prompt FIRST
        logger.info(f"[CHAT] → Searching for employee name in current prompt...")
        prompt_lower_for_search = req.prompt.lower()  # Use req.prompt directly

        # Try exact full name match first
        for candidate in all_employees:
            if candidate.name and candidate.name.lower() in prompt_lower_for_search:
                emp = candidate
                logger.info(f"[CHAT] ✓ Found employee by EXACT name match: '{emp.name}' (ID: {emp.id})")
                # Store as active employee for this session
                active_employee_store[session_id] = emp.id
                logger.info(f"[CHAT] → Updated active employee for session")
                break

        # If no exact match, try partial matching (first name or last name)
        if not emp:
            logger.info(f"[CHAT] → No exact match, trying partial name matching...")
            for candidate in all_employees:
                if candidate.name:
                    # Split name into parts and check if any part is in the prompt
                    name_parts = candidate.name.lower().split()
                    for part in name_parts:
                        if len(part) > 2 and part in prompt_lower_for_search:  # Skip very short parts
                            emp = candidate
                            logger.info(f"[CHAT] ✓ Found employee by PARTIAL name match: '{emp.name}' (matched on '{part}')")
                            # Store as active employee for this session
                            active_employee_store[session_id] = emp.id
                            logger.info(f"[CHAT] → Updated active employee for session")
                            break
                if emp:
                    break

        # Step 2: If no employee mentioned in prompt, fall back to:
        # a) active_employee_store (session memory - MOST RECENTLY discussed employee)
        # b) req.employee_id (from frontend - only useful for first query after CV upload)
        #
        # IMPORTANT: Session memory comes FIRST because it reflects the current
        # conversation context. When user says "what are his skills?", they mean
        # the employee they JUST asked about, not the one from the CV upload.
        if not emp:
            active_emp_id = active_employee_store.get(session_id)
            if active_emp_id:
                logger.info(f"[CHAT] → No employee in prompt, using session's active employee (most recent): ID {active_emp_id}")
                emp = db.query(models.Employee).filter(models.Employee.id == active_emp_id).first()
                if emp:
                    logger.info(f"[CHAT] ✓ Using session's active employee: '{emp.name}' (ID: {emp.id})")

            # Only fall back to req.employee_id if session has no active employee
            # (e.g., first query after uploading a CV)
            if not emp and req.employee_id:
                logger.info(f"[CHAT] → No session employee, using employee_id from request: {req.employee_id}")
                emp = db.query(models.Employee).filter(models.Employee.id == req.employee_id).first()
                if emp:
                    logger.info(f"[CHAT] ✓ Using employee from request: '{emp.name}' (ID: {emp.id})")
                    active_employee_store[session_id] = emp.id
                else:
                    logger.warning(f"[CHAT] ✗ No employee found with ID: {req.employee_id}")

            if not emp:
                logger.warning(f"[CHAT] ✗ No employee found - no active session employee and no name match in prompt")

        if emp:
            logger.info(f"[CHAT] → Using employee: {emp.name} (ID: {emp.id})")
            logger.info(f"[CHAT] → Employee raw_text length: {len(emp.raw_text) if emp.raw_text else 0} chars")

            # RAG: retrieve top relevant chunks for this employee and include them first
            logger.info(f"[CHAT] → Performing RAG search...")
            try:
                retrieved = vectorstore.search(req.prompt, top_k=5, employee_id=emp.id)
                logger.info(f"[CHAT] ✓ RAG retrieved {len(retrieved)} chunks")
            except Exception as e:
                logger.warning(f"[CHAT] ✗ RAG search failed: {e}")
                retrieved = []
            retrieved_text = "\n\n---\n\n".join([r.get("text", "") for r in retrieved])

            # Build conversation history context
            history_text = ""
            if conversation_history:
                history_text = "Previous conversation:\n"
                for msg in conversation_history[-5:]:  # Last 5 exchanges
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    history_text += f"{role.capitalize()}: {content}\n"
                history_text += "\n"

            # Build structured employee data from database fields
            structured_data = f"""
=== EMPLOYEE DATABASE RECORD ===
Employee ID: {emp.employee_id if hasattr(emp, 'employee_id') and emp.employee_id else 'N/A'}
Name: {emp.name or 'N/A'}
Email: {emp.email or 'N/A'}
Phone: {emp.phone if hasattr(emp, 'phone') and emp.phone else 'N/A'}
Department: {emp.department if hasattr(emp, 'department') and emp.department else 'N/A'}
Position: {emp.position if hasattr(emp, 'position') and emp.position else 'N/A'}
LinkedIn: {emp.linkedin_url if hasattr(emp, 'linkedin_url') and emp.linkedin_url else 'N/A'}
Portfolio: {emp.portfolio_url if hasattr(emp, 'portfolio_url') and emp.portfolio_url else 'N/A'}
GitHub: {emp.github_url if hasattr(emp, 'github_url') and emp.github_url else 'N/A'}
City: {emp.city if hasattr(emp, 'city') and emp.city else 'N/A'}
Country: {emp.country if hasattr(emp, 'country') and emp.country else 'N/A'}
Career Objective: {emp.career_objective[:200] if hasattr(emp, 'career_objective') and emp.career_objective else 'N/A'}
Technical Skills: {emp.technical_skills if hasattr(emp, 'technical_skills') and emp.technical_skills else 'N/A'}
Soft Skills: {emp.soft_skills if hasattr(emp, 'soft_skills') and emp.soft_skills else 'N/A'}
Education: {emp.education if hasattr(emp, 'education') and emp.education else 'N/A'}
Work Experience: {emp.work_experience[:500] if hasattr(emp, 'work_experience') and emp.work_experience else 'N/A'}
Certifications: {emp.certifications if hasattr(emp, 'certifications') and emp.certifications else 'N/A'}
Languages: {emp.languages if hasattr(emp, 'languages') and emp.languages else 'N/A'}
Achievements: {emp.achievements if hasattr(emp, 'achievements') and emp.achievements else 'N/A'}
Hobbies: {emp.hobbies if hasattr(emp, 'hobbies') and emp.hobbies else 'N/A'}
================================
"""
            logger.info(f"[CHAT] → Built structured employee data block")

            # Enhanced prompt with pronoun resolution and comprehensive hallucination prevention
            context_instruction = (
                "You are answering questions about an employee/candidate.\n\n"
                "=== CRITICAL ANTI-HALLUCINATION RULES ===\n"
                "1. ONLY use information from the DATABASE RECORD and RESUME TEXT provided below.\n"
                "2. For Employee ID, email, phone, department - use the DATABASE RECORD section.\n"
                "3. For experience, skills, projects - use the resume/CV content.\n"
                "4. If information is NOT available, say: 'That information is not available in the records.'\n"
                "5. NEVER guess, infer, assume, or fabricate information.\n"
                "6. NEVER confirm claims the user makes unless verified in the data.\n"
                "7. If the user says 'I heard they worked at X' - verify against records first.\n"
                "8. If the user asks leading questions, stick to the facts.\n"
                "9. Do NOT invent salaries, dates, companies, or skills not in the data.\n"
                "10. For short/ambiguous questions, ask for clarification.\n"
                "11. Pronouns (he/she/they/him/her/his/their) refer to this employee.\n\n"
                "=== RESPONSE GUIDELINES ===\n"
                "- Preface answers with 'Based on the records...' or 'According to their resume...'\n"
                "- For missing info: 'I don't have information about [topic] in the records.'\n"
                "- For unverifiable claims: 'I cannot verify that claim from the available data.'\n"
                "- Keep responses factual and grounded.\n\n"
            )

            logger.info(f"[CHAT] → Building enriched prompt with context...")
            if retrieved_text.strip():
                prompt = (
                    f"{context_instruction}"
                    f"{history_text}"
                    f"{structured_data}\n"
                    f"=== RELEVANT RESUME EXCERPTS ===\n{retrieved_text}\n\n"
                    f"=== FULL RESUME TEXT ===\n{emp.raw_text[:1500] if emp.raw_text else 'N/A'}\n\n"
                    f"User Question: {req.prompt}"
                )
                logger.info(f"[CHAT] ✓ Prompt enriched with DB record + RAG chunks + resume")
            else:
                prompt = (
                    f"{context_instruction}"
                    f"{history_text}"
                    f"{structured_data}\n"
                    f"=== RESUME TEXT ===\n{emp.raw_text[:2000] if emp.raw_text else 'N/A'}\n\n"
                    f"User Question: {req.prompt}"
                )
                logger.info(f"[CHAT] ✓ Prompt enriched with DB record + resume (no RAG chunks)")
            logger.info(f"[CHAT] → Final prompt length: {len(prompt)} chars")
        else:
            # =====================================================
            # ANTI-HALLUCINATION GUARD #6: NO EMPLOYEE CONTEXT
            # Instead of sending raw prompt to LLM (which causes hallucination),
            # return a helpful message asking for clarification or offering options
            # =====================================================
            logger.warning(f"[CHAT] ✗ NO EMPLOYEE CONTEXT - checking if employee-related query")

            # Check if this is an employee-related query that needs context
            employee_related_keywords = [
                "employee", "record", "details", "info", "skills", "experience",
                "email", "phone", "department", "resume", "cv", "candidate",
                "their", "his", "her", "profile", "data", "position"
            ]
            is_employee_query = any(kw in prompt_lower for kw in employee_related_keywords)

            if is_employee_query:
                logger.info(f"[CHAT] → Employee-related query without context - returning guidance")

                # Get available employees for the response
                guidance_employees = db.query(models.Employee).all()
                if guidance_employees:
                    emp_names = [e.name for e in guidance_employees if e.name][:10]
                    emp_list = ", ".join(emp_names) if emp_names else "No named employees"

                    no_context_reply = (
                        "I need to know which employee you're asking about.\n\n"
                        f"**Available employees:** {emp_list}\n\n"
                        "**You can:**\n"
                        "- Ask about a specific person: \"Show me **John's** details\"\n"
                        "- See all employees: \"List **all employees**\"\n"
                        "- Upload a new CV to add an employee"
                    )
                else:
                    no_context_reply = (
                        "There are no employee records in the database yet.\n\n"
                        "**To get started:**\n"
                        "1. Upload a CV/resume using the file picker\n"
                        "2. Wait for it to be processed\n"
                        "3. Then you can ask questions about that employee"
                    )

                conversation_store[session_id].append({"role": "user", "content": req.prompt})
                conversation_store[session_id].append({"role": "assistant", "content": no_context_reply})

                return {
                    "reply": no_context_reply,
                    "session_id": session_id,
                    "employee_id": None,
                    "employee_name": None
                }
            else:
                # Non-employee query - we can send to LLM but with strict instructions
                logger.info(f"[CHAT] → Non-employee query, using general response mode")
                prompt = (
                    "You are an Employee Management System assistant. "
                    "The user's query doesn't seem to be about a specific employee.\n\n"
                    "IMPORTANT: Do NOT make up employee data. If asked about employees, "
                    "tell them to specify which employee or ask to see all employees.\n\n"
                    f"User Query: {req.prompt}\n\n"
                    "Respond helpfully but DO NOT fabricate any employee information."
                )
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

    logger.info(f"[CHAT] → Calling LLM (Ollama) with 60s timeout...")
    try:
        resp = llm.generate(prompt)
        logger.info(f"[CHAT] ✓ LLM response received: {len(resp)} chars")
        logger.info(f"[CHAT] → Response preview: '{resp[:150]}{'...' if len(resp) > 150 else ''}'")
    except Exception as e:
        logger.exception("[CHAT] ✗ LLM generation failed")
        raise HTTPException(status_code=500, detail=str(e))

    # Save conversation to memory
    conversation_store[session_id].append({"role": "user", "content": req.prompt})
    conversation_store[session_id].append({"role": "assistant", "content": resp})
    logger.info(f"[CHAT] ✓ Conversation saved to memory (session: {session_id})")

    # Return the employee_id (either from request or from name search)
    found_employee_id = req.employee_id
    if emp and not found_employee_id:
        found_employee_id = emp.id

    logger.info(f"[CHAT] → Returning response:")
    logger.info(f"[CHAT]   - employee_id: {found_employee_id}")
    logger.info(f"[CHAT]   - employee_name: {emp.name if emp else None}")
    logger.info(f"[CHAT]   - session_id: {session_id}")
    logger.info(f"{'='*60}")

    return {
        "reply": resp,
        "session_id": session_id,  # Return session_id for subsequent requests
        "employee_id": found_employee_id,  # Return found employee (by ID or name search)
        "employee_name": emp.name if emp else None  # Also return name for context
    }



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
        sample = llm.generate("Debug ping: return short token DEBUG_OK")
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


@app.get("/api/extracted/{employee_id}")
def get_extracted_data(employee_id: str):
    """Get extracted resume data in human-readable JSON format.

    Args:
        employee_id: The 6-digit employee ID (e.g., "000001")

    Returns:
        The extracted resume data as JSON
    """
    data = storage.get_extracted_data(employee_id)
    if data:
        return data
    raise HTTPException(status_code=404, detail=f"No extracted data found for employee {employee_id}")


@app.get("/api/employees")
def list_employees():
    """List all employees with their basic info.

    Returns a summary of all employees in the database.
    """
    from sqlalchemy.orm import Session
    db: Session = SessionLocal()
    try:
        employees = db.query(models.Employee).all()
        result = []
        for emp in employees:
            result.append({
                "id": emp.id,
                "employee_id": emp.employee_id,
                "name": emp.name,
                "email": emp.email,
                "phone": getattr(emp, "phone", None),
                "department": getattr(emp, "department", None),
                "position": getattr(emp, "position", None),
                "city": getattr(emp, "city", None),
                "has_raw_text": bool(emp.raw_text),
                "has_technical_skills": bool(getattr(emp, "technical_skills", None)),
                "has_work_experience": bool(getattr(emp, "work_experience", None))
            })
        return {"count": len(result), "employees": result}
    finally:
        db.close()



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
        "employee_name: name of the employee (string) or null (if name is mentioned in command, extract it here),\n"
        "fields: object of fields to set (for create/update). Allowed fields: name, email, phone, department, position.\n"
        "Return ONLY valid JSON.\n"
        "Examples:\n"
        "- 'Update Arun from IT to HR department' -> {\"action\":\"update\", \"employee_id\":null, \"employee_name\":\"Arun\", \"fields\":{\"department\":\"HR\"}}\n"
        "- 'Update employee 123 email to x@y.com' -> {\"action\":\"update\", \"employee_id\":123, \"employee_name\":null, \"fields\":{\"email\":\"x@y.com\"}}\n"
        "- 'Create employee John in IT' -> {\"action\":\"create\", \"employee_id\":null, \"employee_name\":null, \"fields\":{\"name\":\"John\", \"department\":\"IT\"}}\n"
        "- 'Delete John' -> {\"action\":\"delete\", \"employee_id\":null, \"employee_name\":\"John\", \"fields\":{}}\n"
        "- 'Remove employee 5' -> {\"action\":\"delete\", \"employee_id\":5, \"employee_name\":null, \"fields\":{}}\n"
        "- 'Delete the employee Arun Kumar' -> {\"action\":\"delete\", \"employee_id\":null, \"employee_name\":\"Arun Kumar\", \"fields\":{}}\n\n"
        f"User command:\n{cmd}\n"
    )

    try:
        parse_resp = llm.generate(parse_prompt)
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

    # Validate the proposal for safety (hallucination protection)
    validation_errors = []
    warnings = []

    if proposal and isinstance(proposal, dict):
        # Validate action
        action = proposal.get("action")
        if action not in ["create", "read", "update", "delete"]:
            validation_errors.append(f"Invalid action: {action}. Must be one of: create, read, update, delete")

        # Validate fields
        fields = proposal.get("fields") or {}
        ALLOWED_FIELDS = {"name", "email", "phone", "department", "position", "raw_text"}
        invalid_fields = set(fields.keys()) - ALLOWED_FIELDS
        if invalid_fields:
            validation_errors.append(f"Invalid fields detected: {', '.join(invalid_fields)}. Allowed fields: {', '.join(ALLOWED_FIELDS)}")

        # Validate email format if present
        if "email" in fields and fields["email"]:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, str(fields["email"])):
                warnings.append(f"Email format looks invalid: {fields['email']}")

        # Validate phone format if present (basic check)
        if "phone" in fields and fields["phone"]:
            # Remove common separators and check if it's mostly digits
            phone_clean = str(fields["phone"]).replace("-", "").replace(" ", "").replace("(", "").replace(")", "").replace("+", "")
            if not phone_clean.isdigit() or len(phone_clean) < 10:
                warnings.append(f"Phone format looks invalid: {fields['phone']}")

        # Validate employee exists (for update/delete/read)
        if action in ["update", "delete", "read"]:
            emp_id = proposal.get("employee_id")
            emp_name = proposal.get("employee_name")

            if not emp_id and not emp_name:
                validation_errors.append(f"For {action} action, either employee_id or employee_name must be provided")
            else:
                # Check if employee exists in database
                from sqlalchemy.orm import Session
                db: Session = SessionLocal()
                try:
                    emp = None
                    if emp_id:
                        emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
                        if not emp:
                            validation_errors.append(f"Employee with ID {emp_id} not found in database")
                    elif emp_name:
                        emp = db.query(models.Employee).filter(models.Employee.name.ilike(f"%{emp_name}%")).first()
                        if not emp:
                            validation_errors.append(f"Employee with name '{emp_name}' not found in database")
                        else:
                            # Add info about which employee was found
                            warnings.append(f"Found employee: {emp.name} (ID: {emp.id})")
                finally:
                    db.close()

    pending_id = str(uuid.uuid4())
    pending = {
        "command": cmd,
        "proposal": proposal,
        "raw_response": parse_resp,
        "validation_errors": validation_errors,
        "warnings": warnings,
        "validated": len(validation_errors) == 0
    }
    try:
        with open(os.path.join(JOB_DIR, f"nl_{pending_id}.json"), "w", encoding="utf-8") as pf:
            pf.write(_json.dumps(pending))
    except Exception:
        pass

    return {
        "pending_id": pending_id,
        "proposal": proposal,
        "raw": parse_resp,
        "validation_errors": validation_errors,
        "warnings": warnings,
        "validated": len(validation_errors) == 0
    }


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

    # Check if proposal was validated and has no errors
    if not pending.get("validated", False):
        validation_errors = pending.get("validation_errors", [])
        if validation_errors:
            raise HTTPException(status_code=400, detail=f"Cannot apply proposal with validation errors: {'; '.join(validation_errors)}")

    action = proposal.get("action")
    emp_id = proposal.get("employee_id")
    emp_name = proposal.get("employee_name")
    fields = proposal.get("fields") or {}

    from sqlalchemy.orm import Session

    db: Session = SessionLocal()

    # Helper function to resolve employee by ID or name
    def resolve_employee(db, emp_id, emp_name):
        if emp_id:
            return db.query(models.Employee).filter(models.Employee.id == emp_id).first()
        elif emp_name:
            # Case-insensitive partial name match
            emp = db.query(models.Employee).filter(models.Employee.name.ilike(f"%{emp_name}%")).first()
            if not emp:
                # Try exact match
                emp = db.query(models.Employee).filter(models.Employee.name == emp_name).first()
            return emp
        return None

    try:
        if action == "create":
            emp = models.Employee(
                name=fields.get("name") or "",
                email=fields.get("email"),
                phone=fields.get("phone"),
                department=fields.get("department"),
                position=fields.get("position"),
                raw_text=fields.get("raw_text")
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            res = {"status": "created", "employee_id": emp.id, "employee": {"id": emp.id, "name": emp.name, "email": emp.email, "department": emp.department, "position": emp.position}}
        elif action == "update":
            emp = resolve_employee(db, emp_id, emp_name)
            if not emp:
                if emp_name:
                    raise HTTPException(status_code=404, detail=f"Employee with name '{emp_name}' not found")
                else:
                    raise HTTPException(status_code=404, detail=f"Employee with id {emp_id} not found")
            # Store old values for confirmation
            old_vals = {}
            for k, v in fields.items():
                if hasattr(emp, k):
                    old_vals[k] = getattr(emp, k)
                    setattr(emp, k, v)
            db.add(emp)
            db.commit()
            res = {"status": "updated", "employee_id": emp.id, "employee": {"id": emp.id, "name": emp.name, "email": emp.email, "department": emp.department, "position": emp.position}, "old_values": old_vals}
        elif action == "delete":
            emp = resolve_employee(db, emp_id, emp_name)
            if not emp:
                if emp_name:
                    raise HTTPException(status_code=404, detail=f"Employee with name '{emp_name}' not found")
                else:
                    raise HTTPException(status_code=404, detail=f"Employee with id {emp_id} not found")
            emp_data = {"id": emp.id, "name": emp.name, "email": emp.email, "department": emp.department, "position": emp.position}
            db.delete(emp)
            db.commit()
            res = {"status": "deleted", "employee_id": emp.id, "deleted_employee": emp_data}
        elif action == "read":
            emp = resolve_employee(db, emp_id, emp_name)
            if not emp:
                if emp_name:
                    raise HTTPException(status_code=404, detail=f"Employee with name '{emp_name}' not found")
                else:
                    raise HTTPException(status_code=404, detail=f"Employee with id {emp_id} not found")
            res = {"status": "ok", "employee": {"id": emp.id, "name": emp.name, "email": emp.email, "phone": getattr(emp, "phone", None), "department": getattr(emp, "department", None), "position": getattr(emp, "position", None), "raw_len": len(emp.raw_text or "")}}
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
