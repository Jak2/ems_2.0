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
from app.services.extractor import extract_text_from_bytes, extract_text_auto, is_image_file, is_pdf_file
from app.services.llm_adapter import OllamaAdapter
from app.services.embeddings import Embeddings
from app.services.vectorstore_faiss import FaissVectorStore
from app.services.extraction_utils import (
    array_to_text,
    create_extraction_prompt,
    create_retry_prompt,
    validate_extraction,
    parse_llm_json,
    extract_skills_from_text,
    quick_verify_extraction,
    create_ensemble_prompts,
    merge_ensemble_results,
    get_ensemble_temperatures,
    detect_multi_query,
    create_decomposition_prompt,
    parse_decomposed_tasks,
    create_aggregation_prompt
)
from app.services.validators import (
    sanitize_input,
    validate_input_length,
    validate_is_resume,
    enforce_schema,
    validate_and_clean_extraction,
    ValidationResult
)
from app.services.search_utils import (
    expand_skill_search,
    skills_match,
    calculate_experience_years,
    find_employees_by_experience,
    expand_city_search,
    get_title_seniority,
    parse_negative_search,
    apply_negative_filter,
    find_employees_in_date_range,
    parse_date_flexible,
    SKILL_SYNONYMS,
    CITY_SYNONYMS,
    TITLE_SENIORITY,
    # New edge case handlers
    normalize_unicode,
    soundex,
    names_sound_similar,
    strip_honorifics,
    expand_abbreviations,
    titles_match,
    parse_temporal_reference,
    parse_null_field_query,
    find_employees_with_null_field,
    parse_compound_query,
    apply_compound_filter,
    parse_numeric_range,
    HONORIFICS,
    TITLE_ABBREVIATIONS,
)
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
        "summary": "TEXT",
        "work_experience": "TEXT",
        "education": "TEXT",
        "technical_skills": "TEXT",
        "languages": "TEXT",
        "hobbies": "TEXT",
        "cocurricular_activities": "TEXT",
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


# ============================================================
# DUPLICATE EMPLOYEE DETECTION
# ============================================================

def check_duplicate_employee(db, name: str = None, email: str = None, phone: str = None) -> dict:
    """Check if an employee with similar details already exists in the database.

    Args:
        db: Database session
        name: Employee name to check
        email: Employee email to check
        phone: Employee phone to check

    Returns:
        dict with:
        - is_duplicate: bool
        - matching_employees: list of matching employee records
        - match_reasons: list of reasons why they matched
    """
    matching_employees = []
    match_reasons = []

    if not name and not email and not phone:
        return {"is_duplicate": False, "matching_employees": [], "match_reasons": []}

    all_employees = db.query(models.Employee).all()

    for emp in all_employees:
        reasons = []

        # Check email match (exact match, case-insensitive)
        if email and emp.email:
            if email.strip().lower() == emp.email.strip().lower():
                reasons.append(f"Email match: {emp.email}")

        # Check phone match (normalize and compare)
        if phone and emp.phone:
            # Normalize phone numbers (remove spaces, dashes, parentheses)
            import re
            norm_phone = re.sub(r'[\s\-\(\)\+]', '', str(phone))
            norm_emp_phone = re.sub(r'[\s\-\(\)\+]', '', str(emp.phone))
            if len(norm_phone) >= 7 and len(norm_emp_phone) >= 7:
                # Check if last 10 digits match (handles country code differences)
                if norm_phone[-10:] == norm_emp_phone[-10:]:
                    reasons.append(f"Phone match: {emp.phone}")

        # Check name match (case-insensitive, handles variations)
        if name and emp.name:
            name_lower = name.strip().lower()
            emp_name_lower = emp.name.strip().lower()

            # Exact match
            if name_lower == emp_name_lower:
                reasons.append(f"Exact name match: {emp.name}")
            else:
                # Check if names are very similar (one contains the other)
                name_parts = set(name_lower.split())
                emp_name_parts = set(emp_name_lower.split())

                # If all parts of one name are in the other (handles "John" vs "John Doe")
                if name_parts and emp_name_parts:
                    if name_parts.issubset(emp_name_parts) or emp_name_parts.issubset(name_parts):
                        # Only flag if at least 2 parts match or names are short
                        common_parts = name_parts.intersection(emp_name_parts)
                        if len(common_parts) >= 2 or (len(name_parts) == 1 and len(emp_name_parts) == 1):
                            reasons.append(f"Similar name: {emp.name}")

        # If any match reason found, add to matching employees
        if reasons:
            matching_employees.append(emp)
            match_reasons.extend(reasons)

    is_duplicate = len(matching_employees) > 0

    if is_duplicate:
        logger.info(f"[DUPLICATE_CHECK] Found {len(matching_employees)} potential duplicate(s) for "
                   f"name='{name}', email='{email}', phone='{phone}'")
        logger.info(f"[DUPLICATE_CHECK] Match reasons: {match_reasons}")

    return {
        # "is_duplicate": is_duplicate,
        # "matching_employees": matching_employees,
        # "match_reasons": list(set(match_reasons)) 
        "is_duplicate": False,
        "matching_employees": [],
        "match_reasons": [] # Remove duplicate reasons
    }


def format_duplicate_error(duplicate_result: dict, action: str = "create") -> str:
    """Format a user-friendly error message for duplicate detection.

    Args:
        duplicate_result: Result from check_duplicate_employee()
        action: The action being attempted (create, upload, etc.)

    Returns:
        Formatted error message string
    """
    if not duplicate_result["is_duplicate"]:
        return ""

    matches = duplicate_result["matching_employees"]
    reasons = duplicate_result["match_reasons"]

    msg = f"**Cannot {action} - Duplicate Employee Detected!**\n\n"
    msg += f"An employee with similar details already exists in the database.\n\n"
    msg += f"**Match reason(s):** {', '.join(reasons)}\n\n"
    msg += "**Existing employee record(s):**\n"

    for i, emp in enumerate(matches[:5], 1):
        msg += f"\n**{i}. {emp.name}**\n"
        msg += f"   - Employee ID: **{emp.employee_id}**\n"
        msg += f"   - Email: {emp.email or 'N/A'}\n"
        msg += f"   - Phone: {emp.phone or 'N/A'}\n"
        msg += f"   - Department: {getattr(emp, 'department', None) or 'N/A'}\n"
        msg += f"   - Position: {getattr(emp, 'position', None) or 'N/A'}\n"

    if len(matches) > 5:
        msg += f"\n*...and {len(matches) - 5} more potential matches*\n"

    msg += "\n**What you can do:**\n"
    msg += "- If this is the same person, update their existing record instead\n"
    msg += "- If this is a different person, ensure the name/email/phone are different\n"
    msg += f"- To update existing record: \"Update employee {matches[0].employee_id} ...\"\n"

    return msg


class UploadResponse(BaseModel):
    job_id: str
    status: str


@app.post("/api/upload-cv", response_model=UploadResponse)
async def upload_cv(file: UploadFile = File(...)):
    """Upload a CV/resume (PDF or image) for processing.

    Supported formats:
    - PDF files (.pdf)
    - Image files (.jpg, .jpeg, .png, .gif, .bmp, .webp)

    Images are processed using OCR (Optical Character Recognition).
    """
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

    # extract text - auto-detect file type (PDF or image)
    is_image = is_image_file(filename)
    file_type = "image" if is_image else "PDF"
    logger.info(f"[PROCESS_CV] → Extracting text from {file_type}...")
    try:
        pdf_text = extract_text_auto(data, filename)
    except Exception as e:
        logger.error(f"[PROCESS_CV] ✗ Text extraction failed: {e}")
        # For images, provide more detailed error
        if is_image:
            logger.error(f"[PROCESS_CV] ✗ OCR failed - ensure Tesseract is installed and in PATH")
            logger.error(f"[PROCESS_CV] → Windows: https://github.com/UB-Mannheim/tesseract/wiki")
            logger.error(f"[PROCESS_CV] → Linux: sudo apt install tesseract-ocr")
        pdf_text = ""
    logger.info(f"[PROCESS_CV] ✓ Extracted {len(pdf_text)} characters from {file_type}")

    # Log first 500 chars for debugging - helps verify extraction quality
    if pdf_text:
        preview = pdf_text[:500].replace('\n', '\\n')
        logger.info(f"[PROCESS_CV] → Extracted text preview: {preview}")
    else:
        logger.warning(f"[PROCESS_CV] ✗ Text extraction returned empty! File may be corrupted or unreadable.")

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
    # =====================================================
    # INPUT VALIDATION & SANITIZATION
    # =====================================================
    logger.info(f"[PROCESS_CV] → Validating and sanitizing input...")

    # Sanitize input to prevent injection attacks
    pdf_text = sanitize_input(pdf_text)

    # Validate input length
    length_result = validate_input_length(pdf_text, "resume_text")
    if not length_result.is_valid:
        logger.error(f"[PROCESS_CV] ✗ Input validation failed: {length_result.errors}")
        # Continue with whatever we have, but log the warning
    if length_result.warnings:
        logger.warning(f"[PROCESS_CV] ⚠ Input warnings: {length_result.warnings}")
    pdf_text = length_result.value or pdf_text

    logger.info(f"[PROCESS_CV] ✓ Input validated and sanitized")

    # =====================================================
    # RESUME DOCUMENT VALIDATION
    # Verify the uploaded document is actually a resume/CV
    # Reject non-resume documents before storing in database
    # NOTE: Images are more lenient since OCR can be imperfect
    # =====================================================
    logger.info(f"[PROCESS_CV] → Validating document is a resume...")
    resume_validation = validate_is_resume(pdf_text)
    logger.info(f"[PROCESS_CV] → Validation score: {resume_validation.confidence * 100:.1f}%, is_valid: {resume_validation.is_valid}")

    # For images, be more lenient - only reject if completely empty or very low confidence
    # OCR text is often messy and may not have clear resume structure
    if is_image and not resume_validation.is_valid:
        if len(pdf_text.strip()) > 100 and resume_validation.confidence >= 0.15:
            logger.info(f"[PROCESS_CV] → Image file - accepting with lower confidence (OCR text may be imperfect)")
            resume_validation = ValidationResult(
                is_valid=True,
                value=resume_validation.value,
                errors=[],
                warnings=resume_validation.warnings + ["Accepted with lower confidence for image file"],
                confidence=resume_validation.confidence
            )
        elif len(pdf_text.strip()) > 50:
            # Even more lenient - if there's some text, accept it for images
            logger.info(f"[PROCESS_CV] → Image file - accepting minimal OCR text")
            resume_validation = ValidationResult(
                is_valid=True,
                value=resume_validation.value,
                errors=[],
                warnings=["Minimal OCR text - accepted for image file"],
                confidence=0.1
            )

    if not resume_validation.is_valid:
        logger.warning(f"[PROCESS_CV] ✗ Document rejected - NOT a resume")
        logger.warning(f"[PROCESS_CV] → Rejection reason: {resume_validation.errors}")

        # Mark job as failed with clear error message
        error_message = resume_validation.errors[0] if resume_validation.errors else "Document is not a valid resume"
        try:
            import json as _json
            job_path = os.path.join(JOB_DIR, f"{job_id}.json")
            failure_data = {
                "status": "failed",
                "reason": "not_a_resume",
                "message": error_message,
                "filename": filename,
                "confidence": resume_validation.confidence,
                "warnings": resume_validation.warnings
            }
            with open(job_path, "w", encoding="utf-8") as jf:
                jf.write(_json.dumps(failure_data))
            logger.info(f"[PROCESS_CV] ✓ Wrote failure status to {job_path}")
        except Exception as e:
            logger.error(f"[PROCESS_CV] ✗ Failed to write failure status: {e}")

        # Note: File cleanup from storage is optional
        # The file will remain in storage but won't be linked to any employee record
        logger.info(f"[PROCESS_CV] → Rejected file {file_id} not stored in database (file remains in storage for review)")

        return  # Exit without storing in database

    logger.info(f"[PROCESS_CV] ✓ Document validated as resume (confidence: {resume_validation.confidence:.2f})")
    if resume_validation.warnings:
        logger.info(f"[PROCESS_CV] → Validation warnings: {resume_validation.warnings}")

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
        # LLM-driven COMPREHENSIVE structured extraction with enterprise-level prompts
        logger.info(f"[PROCESS_CV] → Starting LLM extraction with enterprise prompt wrapper...")
        try:
            # Use the enterprise-level extraction prompt
            extraction_prompt = create_extraction_prompt(pdf_text, max_chars=10000)

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

            # Use robust JSON parsing with multiple fallback strategies
            # Pass pdf_text for fallback extraction (email, phone, soft skills)
            import json as _json

            parsed = parse_llm_json(extraction_resp, raw_text=pdf_text)
            if parsed:
                logger.info(f"[PROCESS_CV] ✓ JSON parsed successfully")

                # Quick verification against original text (reduces hallucination)
                parsed = quick_verify_extraction(parsed, pdf_text)
                logger.info(f"[PROCESS_CV] ✓ Quick verification completed")

                # Validate extraction quality
                is_valid, issues = validate_extraction(parsed)
                if not is_valid:
                    logger.warning(f"[PROCESS_CV] ⚠ Extraction validation issues: {issues}")

                # Enterprise validation with schema enforcement
                validation_result = validate_and_clean_extraction(parsed, pdf_text)
                if validation_result.validation_errors:
                    logger.warning(f"[PROCESS_CV] ⚠ Schema validation errors: {validation_result.validation_errors}")
                if validation_result.validation_warnings:
                    logger.info(f"[PROCESS_CV] → Schema warnings: {validation_result.validation_warnings}")
                logger.info(f"[PROCESS_CV] → Extraction confidence: {validation_result.overall_confidence:.2f}")

                # Use the validated data
                parsed = validation_result.data
            else:
                logger.error(f"[PROCESS_CV] ✗ JSON parsing failed with all strategies - extraction will be incomplete")

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

                # Professional Info
                department: str | None = None
                position: str | None = None
                summary: str | None = None

                # Experience & Education (arrays) - Accept strings or dicts, convert dicts to JSON strings
                work_experience: List[Any] | None = None
                education: List[Any] | None = None

                # Skills (arrays) - Accept strings or dicts
                technical_skills: List[Any] | None = None
                languages: List[Any] | None = None

                # Additional (arrays) - Accept strings or dicts
                hobbies: List[Any] | None = None
                cocurricular_activities: List[Any] | None = None

                # Convert dict items to JSON strings for storage
                @field_validator('work_experience', 'education', 'technical_skills',
                               'languages', 'hobbies',
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
                    # Use the enterprise retry prompt
                    retry_prompt = create_retry_prompt(pdf_text, max_chars=8000)

                    # write retry prompt log
                    try:
                        with open(os.path.join(JOB_DIR, f"{job_id}.prompt.retry.txt"), "w", encoding="utf-8") as pf:
                            pf.write(retry_prompt[:10000])
                    except Exception:
                        pass
                    logger.info(f"[PROCESS_CV] → Sending retry prompt to LLM...")
                    retry_resp = llm.generate(retry_prompt)
                    logger.info(f"[PROCESS_CV] ✓ Retry response received: {len(retry_resp)} chars")

                    # Use robust JSON parsing with fallback extraction
                    parsed2 = parse_llm_json(retry_resp, raw_text=pdf_text)
                    if isinstance(parsed2, dict):
                        # OUTPUT VERIFICATION for retry extraction
                        parsed2 = quick_verify_extraction(parsed2, pdf_text)
                        validation_result = validate_and_clean_extraction(parsed2, pdf_text)
                        parsed2 = validation_result.data
                        try:
                            parsed_model = ComprehensiveExtractionModel(**parsed2)
                            logger.info(f"[PROCESS_CV] ✓ Retry extraction successful: name='{parsed_model.name}'")
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

                # =====================================================
                # DUPLICATE EMPLOYEE CHECK
                # Before saving, check if this employee already exists
                # =====================================================
                logger.info(f"[PROCESS_CV] → Checking for duplicate employees...")
                duplicate_result = check_duplicate_employee(
                    db,
                    name=parsed_model.name,
                    email=parsed_model.email,
                    phone=parsed_model.phone
                )

                if duplicate_result["is_duplicate"]:
                    logger.warning(f"[PROCESS_CV] ✗ DUPLICATE DETECTED - Rejecting upload")

                    # Delete the employee record we just created (before extraction)
                    try:
                        db.delete(emp)
                        db.commit()
                        logger.info(f"[PROCESS_CV] → Cleaned up temporary employee record")
                    except Exception as del_err:
                        logger.warning(f"[PROCESS_CV] → Could not clean up temp record: {del_err}")
                        db.rollback()

                    # Remove from FAISS if added
                    try:
                        vectorstore.remove_employee(emp.id)
                    except Exception:
                        pass

                    # Mark job as failed with duplicate error
                    error_msg = format_duplicate_error(duplicate_result, "upload this resume")
                    try:
                        import json as _dup_json
                        job_path = os.path.join(JOB_DIR, f"{job_id}.json")
                        failure_data = {
                            "status": "failed",
                            "reason": "duplicate_employee",
                            "message": "An employee with similar details already exists",
                            "filename": filename,
                            "matching_employees": duplicate_result["matching_employees"],
                            "match_reasons": duplicate_result["match_reasons"]
                        }
                        with open(job_path, "w", encoding="utf-8") as jf:
                            jf.write(_dup_json.dumps(failure_data))
                        logger.info(f"[PROCESS_CV] ✓ Wrote duplicate failure status")
                    except Exception as e:
                        logger.error(f"[PROCESS_CV] ✗ Failed to write failure status: {e}")

                    return  # Exit without completing the upload

                logger.info(f"[PROCESS_CV] ✓ No duplicates found - proceeding with save")

                # Helper function to safely set attributes and convert arrays to readable text
                def safe_set(obj, attr, value):
                    if value is not None:
                        try:
                            # Convert lists to readable text format (not JSON)
                            if isinstance(value, list):
                                value = array_to_text(value)
                            if value:  # Only set if we have a value after conversion
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

                # Set professional info
                safe_set(emp, "department", parsed_model.department)
                safe_set(emp, "position", parsed_model.position)
                safe_set(emp, "summary", parsed_model.summary)

                # Set experience & education (arrays → JSON)
                safe_set(emp, "work_experience", parsed_model.work_experience)
                safe_set(emp, "education", parsed_model.education)

                # Set skills (arrays → JSON)
                safe_set(emp, "technical_skills", parsed_model.technical_skills)
                safe_set(emp, "languages", parsed_model.languages)

                # Set additional info (arrays → JSON)
                safe_set(emp, "hobbies", parsed_model.hobbies)
                safe_set(emp, "cocurricular_activities", parsed_model.cocurricular_activities)

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
                        "department": parsed_model.department,
                        "position": parsed_model.position,
                        "summary": parsed_model.summary,
                        "work_experience": parsed_model.work_experience,
                        "education": parsed_model.education,
                        "technical_skills": parsed_model.technical_skills,
                        "languages": parsed_model.languages,
                        "hobbies": parsed_model.hobbies,
                        "cocurricular_activities": parsed_model.cocurricular_activities,
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

    # =====================================================
    # EDGE CASE #24: PRONOUN RESOLUTION
    # Resolve "his/her/their/that employee's" to the active employee
    # Example: "what is his email?" → "what is [John's] email?"
    # =====================================================
    pronoun_patterns = [
        (r"\bhis\b", "his"), (r"\bher\b", "her"), (r"\btheir\b", "their"),
        (r"\bthat\s+employee'?s?\b", "that employee's"),
        (r"\bthis\s+employee'?s?\b", "this employee's"),
        (r"\bthe\s+employee'?s?\b", "the employee's"),
        (r"\bthem\b", "them"), (r"\bhim\b", "him"),
    ]

    import re as _re_pronoun
    prompt_lower_check = prompt.lower()
    has_pronoun = any(_re_pronoun.search(pattern, prompt_lower_check) for pattern, _ in pronoun_patterns)

    if has_pronoun and session_id in active_employee_store:
        active_emp_id = active_employee_store[session_id]
        try:
            from sqlalchemy.orm import Session as PronounSession
            pronoun_db: PronounSession = SessionLocal()
            active_emp = pronoun_db.query(models.Employee).filter(models.Employee.id == active_emp_id).first()
            if active_emp and active_emp.name:
                # Replace pronouns with the employee's name
                original_prompt = prompt
                for pattern, pronoun_text in pronoun_patterns:
                    if _re_pronoun.search(pattern, prompt_lower_check):
                        # Replace the pronoun with "[Name]'s" or "[Name]"
                        if "'s" in pronoun_text or pronoun_text in ["his", "her", "their"]:
                            replacement = f"{active_emp.name}'s"
                        else:
                            replacement = active_emp.name
                        prompt = _re_pronoun.sub(pattern, replacement, prompt, flags=_re_pronoun.IGNORECASE)

                if prompt != original_prompt:
                    logger.info(f"[CHAT] → Pronoun resolution: '{original_prompt}' → '{prompt}'")
                    logger.info(f"[CHAT] → Resolved to active employee: {active_emp.name} (ID: {active_emp_id})")
            pronoun_db.close()
        except Exception as e:
            logger.warning(f"[CHAT] Pronoun resolution failed: {e}")

    # Retrieve conversation history for this session
    conversation_history = list(conversation_store[session_id])
    logger.info(f"[CHAT] Conversation history: {len(conversation_history)} messages")

    # =====================================================
    # MULTI-QUERY DETECTION AND HANDLING
    # Detects complex queries with multiple tasks and processes them
    # Example: "what skills does X have and compare with Y"
    # NOTE: Skip for "create" commands - they contain resume text with many "and" words
    # =====================================================
    is_create_command = prompt.lower().strip().startswith("create ")
    if detect_multi_query(prompt) and len(prompt) > 50 and not is_create_command:
        logger.info(f"[CHAT] *** MULTI-QUERY DETECTED ***")
        try:
            # Step 1: Decompose the query into sub-tasks using LLM
            decomposition_prompt = create_decomposition_prompt(prompt)
            decomposition_response = llm.generate(decomposition_prompt)
            sub_tasks = parse_decomposed_tasks(decomposition_response)

            if sub_tasks and len(sub_tasks) > 1:
                logger.info(f"[CHAT] Decomposed into {len(sub_tasks)} sub-tasks")

                # Step 2: Execute each sub-task
                task_results = []
                task_context = {}  # Store results for dependent tasks

                for task in sub_tasks:
                    task_id = task.get("task_id", len(task_results) + 1)
                    task_query = task.get("query", "")
                    task_type = task.get("type", "search")
                    depends_on = task.get("depends_on")

                    logger.info(f"[CHAT] Executing sub-task {task_id}: {task_query[:50]}...")

                    # Build context from dependent tasks
                    context_info = ""
                    if depends_on:
                        deps = [depends_on] if isinstance(depends_on, int) else depends_on
                        for dep_id in deps:
                            if dep_id in task_context:
                                context_info += f"\n[Context from Task {dep_id}]: {task_context[dep_id]}"

                    # Execute the sub-task query
                    # Create a simple search/query prompt
                    sub_task_prompt = task_query
                    if context_info:
                        sub_task_prompt = f"{task_query}\n\nContext:{context_info}"

                    # Search for relevant employees mentioned in the sub-task
                    db = SessionLocal()
                    all_employees = db.query(models.Employee).all()

                    # Find employees mentioned in this sub-task
                    task_query_lower = task_query.lower()
                    mentioned_in_task = []
                    for emp in all_employees:
                        if emp.name and emp.name.lower() in task_query_lower:
                            mentioned_in_task.append(emp)
                        elif emp.name:
                            # Check first name
                            first_name = emp.name.split()[0].lower()
                            if first_name in task_query_lower and len(first_name) > 2:
                                mentioned_in_task.append(emp)

                    # Build response based on task type
                    sub_response = ""

                    if task_type == "search" and mentioned_in_task:
                        emp = mentioned_in_task[0]
                        skills = emp.technical_skills or "No skills listed"
                        sub_response = f"{emp.name}'s skills: {skills}"
                        task_context[task_id] = sub_response

                    elif task_type == "count" and mentioned_in_task:
                        emp = mentioned_in_task[0]
                        skills_text = emp.technical_skills or ""
                        skills_list = [s.strip() for s in skills_text.split(",") if s.strip()]

                        # Count specific skill categories if mentioned
                        cloud_devops_keywords = ["aws", "azure", "gcp", "docker", "kubernetes", "k8s",
                                                  "jenkins", "ci/cd", "devops", "terraform", "ansible",
                                                  "cloud", "ec2", "s3", "lambda", "ecs", "eks"]
                        relevant_skills = [s for s in skills_list
                                           if any(kw in s.lower() for kw in cloud_devops_keywords)]

                        sub_response = f"{emp.name} has {len(skills_list)} total skills. "
                        sub_response += f"Cloud/DevOps related: {len(relevant_skills)} skills"
                        if relevant_skills:
                            sub_response += f" ({', '.join(relevant_skills)})"
                        task_context[task_id] = sub_response

                    elif task_type == "compare" and len(mentioned_in_task) >= 2:
                        # Compare skills between employees
                        emp1, emp2 = mentioned_in_task[0], mentioned_in_task[1]
                        skills1 = set(s.strip().lower() for s in (emp1.technical_skills or "").split(",") if s.strip())
                        skills2 = set(s.strip().lower() for s in (emp2.technical_skills or "").split(",") if s.strip())

                        cloud_devops_keywords = ["aws", "azure", "gcp", "docker", "kubernetes", "k8s",
                                                  "jenkins", "ci/cd", "devops", "terraform", "ansible",
                                                  "cloud", "ec2", "s3", "lambda"]

                        devops1 = [s for s in skills1 if any(kw in s for kw in cloud_devops_keywords)]
                        devops2 = [s for s in skills2 if any(kw in s for kw in cloud_devops_keywords)]

                        common = skills1 & skills2
                        only_emp1 = skills1 - skills2
                        only_emp2 = skills2 - skills1

                        sub_response = f"Comparison between {emp1.name} and {emp2.name}:\n"
                        sub_response += f"- {emp1.name}: {len(skills1)} total skills, {len(devops1)} DevOps/Cloud\n"
                        sub_response += f"- {emp2.name}: {len(skills2)} total skills, {len(devops2)} DevOps/Cloud\n"
                        sub_response += f"- Common skills: {len(common)}\n"

                        if len(devops1) > len(devops2):
                            sub_response += f"- Conclusion: {emp1.name} has more DevOps/Cloud knowledge"
                        elif len(devops2) > len(devops1):
                            sub_response += f"- Conclusion: {emp2.name} has more DevOps/Cloud knowledge"
                        else:
                            sub_response += f"- Conclusion: Both have similar DevOps/Cloud knowledge"

                        task_context[task_id] = sub_response

                    elif mentioned_in_task:
                        # Generic search - use LLM
                        emp = mentioned_in_task[0]
                        emp_info = f"Name: {emp.name}, Skills: {emp.technical_skills or 'N/A'}, Position: {emp.position or 'N/A'}"

                        generic_prompt = f"""Based on this employee info:
{emp_info}

Answer: {task_query}

Be concise and factual."""
                        sub_response = llm.generate(generic_prompt)
                        task_context[task_id] = sub_response
                    else:
                        sub_response = f"Could not find employee mentioned in: {task_query}"
                        task_context[task_id] = sub_response

                    db.close()

                    task_results.append({
                        "task_id": task_id,
                        "query": task_query,
                        "response": sub_response
                    })

                # Step 3: Aggregate results into final response
                aggregation_prompt = create_aggregation_prompt(prompt, task_results)
                final_response = llm.generate(aggregation_prompt)

                # Add to conversation history
                conversation_store[session_id].append({"role": "user", "content": prompt})
                conversation_store[session_id].append({"role": "assistant", "content": final_response})

                logger.info(f"[CHAT] Multi-query completed with {len(task_results)} sub-tasks")

                return {
                    "reply": final_response,
                    "session_id": session_id,
                    "employee_id": None,
                    "employee_name": None,
                    "multi_query": True,
                    "sub_tasks_count": len(task_results)
                }

        except Exception as e:
            logger.warning(f"[CHAT] Multi-query processing failed, falling back to single query: {e}")
            # Fall through to normal processing

    # =====================================================
    # RESUME-BASED CREATE DETECTION
    # Pattern: "create <resume content>" where content is substantial (>100 chars)
    # This allows users to paste resume data directly and create an employee record
    # =====================================================
    prompt_lower = prompt.lower()
    is_resume_create = False
    resume_content = ""

    if prompt_lower.strip().startswith("create "):
        potential_resume = prompt[len("create "):].strip()
        # If the content after "create" is substantial (>100 chars), treat as resume data
        if len(potential_resume) > 100:
            is_resume_create = True
            # INPUT VALIDATION & SANITIZATION (Enterprise-level)
            resume_content = sanitize_input(potential_resume)
            length_result = validate_input_length(resume_content, "resume_text")
            if not length_result.is_valid:
                logger.warning(f"[CHAT] Input validation failed: {length_result.error}")
                return {
                    "reply": f"⚠️ Input validation failed: {length_result.error}",
                    "session_id": session_id,
                    "employee_id": None,
                    "employee_name": None
                }
            logger.info(f"[CHAT] → Detected RESUME CREATE command ({len(resume_content)} chars, sanitized)")

            # Validate that the content is actually a resume
            resume_validation = validate_is_resume(resume_content)
            if not resume_validation.is_valid:
                logger.warning(f"[CHAT] → Content rejected - NOT a valid resume")
                error_msg = resume_validation.errors[0] if resume_validation.errors else "Content is not a valid resume"
                rejection_reply = (
                    f"**Cannot Create Employee Record**\n\n"
                    f"❌ {error_msg}\n\n"
                    f"**What makes a valid resume?**\n"
                    f"- Contains sections like: Experience, Education, Skills\n"
                    f"- Includes contact information (email, phone)\n"
                    f"- Has professional/career-related content\n\n"
                    f"Please provide a valid resume/CV to create an employee record."
                )
                return {
                    "reply": rejection_reply,
                    "session_id": session_id,
                    "employee_id": None,
                    "employee_name": None
                }
            logger.info(f"[CHAT] ✓ Content validated as resume (confidence: {resume_validation.confidence:.2f})")

    # Handle resume-based employee creation
    if is_resume_create:
        logger.info(f"[CHAT] → Processing resume-based employee creation")

        from sqlalchemy.orm import Session
        from sqlalchemy import text as sql_text
        import json as _json
        import re

        db: Session = SessionLocal()
        try:
            # Generate employee_id in format 013449 (6 digits, zero-padded)
            try:
                result = db.execute(sql_text(
                    "SELECT COALESCE(MAX(CAST(employee_id AS INTEGER)), 0) + 1 FROM employees WHERE employee_id IS NOT NULL"
                )).scalar()
                next_id = result if result else 1
            except Exception as e:
                logger.warning(f"[CHAT] Could not get max employee_id: {e}")
                count = db.query(models.Employee).count()
                next_id = count + 1

            employee_id = str(next_id).zfill(6)
            logger.info(f"[CHAT] Generated employee_id: {employee_id}")

            # Create initial Employee record
            emp = models.Employee(
                employee_id=employee_id,
                name="Pending extraction...",
                raw_text=resume_content,
                extracted_text=resume_content
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            logger.info(f"[CHAT] Created initial employee record: ID={emp.id}, employee_id={emp.employee_id}")

            # Add to FAISS vector store
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

                chunks = chunk_text(resume_content, chunk_size=500, overlap=100)
                if chunks:
                    vectorstore.add_chunks(emp.id, chunks)
                    logger.info(f"[CHAT] Added {len(chunks)} chunks to FAISS vector store")
            except Exception as e:
                logger.warning(f"[CHAT] Failed to add to FAISS: {e}")

            # Use enterprise-level extraction prompt for consistent results
            extraction_prompt = create_extraction_prompt(resume_content, max_chars=10000)

            logger.info(f"[CHAT] → Sending extraction prompt to LLM ({len(extraction_prompt)} chars)...")
            extraction_resp = llm.generate(extraction_prompt)
            logger.info(f"[CHAT] ✓ LLM response received: {len(extraction_resp)} chars")

            # Parse JSON from response using robust parsing with fallback strategies
            # Pass resume_content for fallback extraction (email, phone, soft skills)
            parsed = parse_llm_json(extraction_resp, raw_text=resume_content)
            if parsed:
                logger.info(f"[CHAT] ✓ JSON parsed successfully")
                # Validate extraction quality
                is_valid, issues = validate_extraction(parsed)
                if not is_valid:
                    logger.warning(f"[CHAT] ⚠ Extraction validation issues: {issues}")

                # OUTPUT VERIFICATION (Enterprise-level)
                # 1. Chain-of-Verification for hallucination reduction
                parsed = quick_verify_extraction(parsed, resume_content)
                logger.info(f"[CHAT] ✓ Chain-of-Verification completed")

                # 2. Schema enforcement and field validation
                validation_result = validate_and_clean_extraction(parsed, resume_content)
                parsed = validation_result.data
                if validation_result.validation_warnings:
                    for w in validation_result.validation_warnings:
                        logger.warning(f"[CHAT] ⚠ Validation warning: {w}")
                logger.info(f"[CHAT] ✓ Schema enforcement completed")
            else:
                logger.error(f"[CHAT] ✗ JSON parsing failed with all strategies")

            # Validate using Pydantic model
            from pydantic import BaseModel as PydanticBase, ValidationError, field_validator
            from typing import List, Any

            class ComprehensiveExtractionModel(PydanticBase):
                name: str | None = None
                email: str | None = None
                phone: str | None = None
                linkedin_url: str | None = None
                department: str | None = None
                position: str | None = None
                summary: str | None = None
                work_experience: List[Any] | None = None
                education: List[Any] | None = None
                technical_skills: List[Any] | None = None
                languages: List[Any] | None = None
                hobbies: List[Any] | None = None
                cocurricular_activities: List[Any] | None = None

                @field_validator('work_experience', 'education', 'technical_skills',
                               'languages', 'hobbies',
                               'cocurricular_activities', mode='before')
                @classmethod
                def convert_dicts_to_strings(cls, v):
                    if v is None:
                        return None
                    if isinstance(v, list):
                        result = []
                        for item in v:
                            if isinstance(item, dict):
                                result.append(_json.dumps(item, ensure_ascii=False))
                            else:
                                result.append(str(item) if item is not None else None)
                        return result
                    return v

            parsed_model = None
            if isinstance(parsed, dict):
                try:
                    parsed_model = ComprehensiveExtractionModel(**parsed)
                    logger.info(f"[CHAT] ✓ Pydantic validation passed, name: '{parsed_model.name}'")
                except ValidationError as ve:
                    logger.warning(f"[CHAT] ✗ Validation error: {ve}")
                    parsed_model = None

            # Retry if name is missing
            if not parsed_model or not parsed_model.name:
                logger.warning(f"[CHAT] → Name not found, trying retry prompt...")
                try:
                    # Use the enterprise retry prompt
                    retry_prompt = create_retry_prompt(resume_content, max_chars=8000)
                    retry_resp = llm.generate(retry_prompt)

                    # Use robust JSON parsing with fallback extraction
                    parsed2 = parse_llm_json(retry_resp, raw_text=resume_content)
                    if isinstance(parsed2, dict):
                        # OUTPUT VERIFICATION for retry extraction
                        parsed2 = quick_verify_extraction(parsed2, resume_content)
                        validation_result = validate_and_clean_extraction(parsed2, resume_content)
                        parsed2 = validation_result.data
                        try:
                            parsed_model = ComprehensiveExtractionModel(**parsed2)
                            logger.info(f"[CHAT] ✓ Retry successful, name: '{parsed_model.name}'")
                        except ValidationError:
                            pass
                except Exception as e:
                    logger.error(f"[CHAT] Retry extraction failed: {e}")

            # Update employee with extracted fields
            if parsed_model:
                # =====================================================
                # DUPLICATE EMPLOYEE CHECK (Chat-based create)
                # Before saving, check if this employee already exists
                # =====================================================
                logger.info(f"[CHAT] → Checking for duplicate employees...")
                duplicate_result = check_duplicate_employee(
                    db,
                    name=parsed_model.name,
                    email=parsed_model.email,
                    phone=parsed_model.phone
                )

                if duplicate_result["is_duplicate"]:
                    logger.warning(f"[CHAT] ✗ DUPLICATE DETECTED - Rejecting create")

                    # Delete the employee record we just created
                    try:
                        db.delete(emp)
                        db.commit()
                        logger.info(f"[CHAT] → Cleaned up temporary employee record")
                    except Exception as del_err:
                        logger.warning(f"[CHAT] → Could not clean up temp record: {del_err}")
                        db.rollback()

                    # Remove from FAISS if added
                    try:
                        vectorstore.remove_employee(emp.id)
                    except Exception:
                        pass

                    # Return duplicate error to user
                    duplicate_reply = format_duplicate_error(duplicate_result, "create this employee")
                    conversation_store[session_id].append({"role": "user", "content": req.prompt})
                    conversation_store[session_id].append({"role": "assistant", "content": duplicate_reply})

                    return {
                        "reply": duplicate_reply,
                        "session_id": session_id,
                        "employee_id": None,
                        "employee_name": None
                    }

                logger.info(f"[CHAT] ✓ No duplicates found - proceeding with save")

                def safe_set(obj, attr, value):
                    if value is not None:
                        try:
                            # Convert lists to readable text format (not JSON)
                            if isinstance(value, list):
                                value = array_to_text(value)
                            if value:  # Only set if we have a value after conversion
                                setattr(obj, attr, value)
                                logger.info(f"[CHAT] → Set {attr} = '{str(value)[:50]}{'...' if len(str(value)) > 50 else ''}'")
                        except Exception as e:
                            logger.warning(f"[CHAT] ✗ Could not set {attr}: {e}")

                safe_set(emp, "name", parsed_model.name)
                safe_set(emp, "email", parsed_model.email)
                safe_set(emp, "phone", parsed_model.phone)
                safe_set(emp, "linkedin_url", parsed_model.linkedin_url)
                safe_set(emp, "department", parsed_model.department)
                safe_set(emp, "position", parsed_model.position)
                safe_set(emp, "summary", parsed_model.summary)
                safe_set(emp, "work_experience", parsed_model.work_experience)
                safe_set(emp, "education", parsed_model.education)
                safe_set(emp, "technical_skills", parsed_model.technical_skills)
                safe_set(emp, "languages", parsed_model.languages)
                safe_set(emp, "hobbies", parsed_model.hobbies)
                safe_set(emp, "cocurricular_activities", parsed_model.cocurricular_activities)

                db.add(emp)
                db.commit()
                logger.info(f"[CHAT] ✓ Updated employee with extracted data: name='{emp.name}'")

                # Save extracted JSON to MongoDB and local file
                try:
                    extracted_json = {
                        "name": parsed_model.name,
                        "email": parsed_model.email,
                        "phone": parsed_model.phone,
                        "linkedin_url": parsed_model.linkedin_url,
                        "department": parsed_model.department,
                        "position": parsed_model.position,
                        "summary": parsed_model.summary,
                        "work_experience": parsed_model.work_experience,
                        "education": parsed_model.education,
                        "technical_skills": parsed_model.technical_skills,
                        "languages": parsed_model.languages,
                        "hobbies": parsed_model.hobbies,
                        "cocurricular_activities": parsed_model.cocurricular_activities,
                        "raw_text_preview": resume_content[:1000] if resume_content else None
                    }
                    doc_id = storage.save_extracted_data(emp.employee_id, f"chat_created_{emp.employee_id}.txt", extracted_json)
                    logger.info(f"[CHAT] ✓ Saved extracted JSON: {doc_id}")
                except Exception as e:
                    logger.warning(f"[CHAT] ✗ Failed to save extracted JSON: {e}")

                # Build success response
                work_exp_count = len(parsed_model.work_experience) if parsed_model.work_experience else 0
                edu_count = len(parsed_model.education) if parsed_model.education else 0
                skills_count = len(parsed_model.technical_skills) if parsed_model.technical_skills else 0

                success_reply = (
                    f"**Employee Created Successfully!**\n\n"
                    f"- **Employee ID:** {emp.employee_id}\n"
                    f"- **Name:** {emp.name or 'N/A'}\n"
                    f"- **Email:** {emp.email or 'N/A'}\n"
                    f"- **Phone:** {emp.phone or 'N/A'}\n"
                    f"- **Position:** {emp.position or 'N/A'}\n"
                    f"- **Department:** {emp.department or 'N/A'}\n\n"
                    f"**Extracted Data:**\n"
                    f"- Work Experience: {work_exp_count} entries\n"
                    f"- Education: {edu_count} entries\n"
                    f"- Technical Skills: {skills_count} skills\n\n"
                    f"The employee record has been added to both the SQL database and vector store."
                )

                conversation_store[session_id].append({"role": "user", "content": req.prompt})
                conversation_store[session_id].append({"role": "assistant", "content": success_reply})

                return {
                    "reply": success_reply,
                    "session_id": session_id,
                    "employee_id": emp.id,
                    "employee_name": emp.name
                }
            else:
                # Extraction failed but record was created with raw text
                error_reply = (
                    f"**Employee Record Created (Partial)**\n\n"
                    f"- **Employee ID:** {emp.employee_id}\n\n"
                    f"The resume text was saved, but automatic extraction failed. "
                    f"The raw text has been stored and indexed for search.\n\n"
                    f"You can update the employee details manually using commands like:\n"
                    f"- \"Update employee {emp.employee_id} name to John Doe\"\n"
                    f"- \"Update employee {emp.employee_id} email to john@example.com\""
                )

                conversation_store[session_id].append({"role": "user", "content": req.prompt})
                conversation_store[session_id].append({"role": "assistant", "content": error_reply})

                return {
                    "reply": error_reply,
                    "session_id": session_id,
                    "employee_id": emp.id,
                    "employee_name": None
                }

        except Exception as e:
            logger.exception(f"[CHAT] ✗ Resume create failed: {e}")
            error_reply = f"Failed to create employee from resume data: {str(e)}"
            return {
                "reply": error_reply,
                "session_id": session_id,
                "employee_id": None,
                "employee_name": None
            }
        finally:
            db.close()

    # =====================================================
    # SIMPLE GREETING DETECTION
    # Detect greetings and prepare LLM context for natural response
    # =====================================================
    greeting_patterns = [
        "hi", "hello", "hey", "hii", "hiii", "howdy", "greetings",
        "good morning", "good afternoon", "good evening", "good day",
        "what's up", "whats up", "sup", "yo", "hola", "namaste"
    ]

    prompt_clean = prompt_lower.strip().rstrip("!.,?")
    is_greeting = prompt_clean in greeting_patterns or any(
        prompt_clean.startswith(g + " ") or prompt_clean.endswith(" " + g)
        for g in greeting_patterns
    )

    # Track special context for LLM processing
    special_llm_context = None

    if is_greeting and len(prompt.split()) <= 5:  # Short greeting
        logger.info(f"[CHAT] → Detected greeting, routing through LLM")
        special_llm_context = {
            "type": "greeting",
            "user_message": req.prompt
        }

    # =====================================================
    # THANK YOU / FAREWELL DETECTION
    # Detect appreciation/goodbye and prepare LLM context
    # =====================================================
    thanks_patterns = ["thank you", "thanks", "thank u", "thx", "ty", "appreciate it", "appreciated"]
    farewell_patterns = ["bye", "goodbye", "see you", "take care", "cya", "later", "good night"]

    is_thanks = any(p in prompt_clean for p in thanks_patterns)
    is_farewell = any(p in prompt_clean for p in farewell_patterns)

    if (is_thanks or is_farewell) and len(prompt.split()) <= 6 and special_llm_context is None:
        if is_thanks and is_farewell:
            context_type = "thanks_farewell"
        elif is_thanks:
            context_type = "thanks"
        else:
            context_type = "farewell"

        logger.info(f"[CHAT] → Detected {context_type}, routing through LLM")
        special_llm_context = {
            "type": context_type,
            "user_message": req.prompt
        }

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
    # Note: prompt_lower is already defined at the beginning of this function
    word_count = len(prompt_lower.split())

    # Flag to track if we've already prepared a prompt for LLM (e.g., list queries)
    # This prevents the "NO EMPLOYEE CONTEXT" handler from overwriting it
    llm_prompt_prepared = False

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
        "everyone in the system", "all staff", "all personnel",
        "list all employee records", "all employee records", "show all records",
        "display all employees", "display all records", "get all employees"
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
    # SCHEMA QUERY DETECTION - Show only field/column names
    # Pattern: "field names", "column names", "table structure", "schema"
    # =====================================================
    schema_keywords = [
        "field names", "column names", "field name", "column name",
        "table structure", "schema", "fields", "columns",
        "what fields", "what columns", "which fields", "which columns",
        "list fields", "list columns", "show fields", "show columns",
        "only field", "only column", "just field", "just column"
    ]

    table_keywords = ["employee", "employees", "table"]

    is_schema_query = (
        any(kw in prompt_lower for kw in schema_keywords) and
        any(tk in prompt_lower for tk in table_keywords)
    )

    if is_schema_query:
        logger.info(f"[CHAT] → Detected SCHEMA query - returning field names only")

        # Get field names from the Employee model
        from app.db.models import Employee
        field_names = [column.name for column in Employee.__table__.columns]

        # Build context for LLM
        special_llm_context = {
            "type": "schema_info",
            "table_name": "employees",
            "field_names": field_names,
            "field_count": len(field_names),
            "user_message": req.prompt
        }
        llm_prompt_prepared = True
        logger.info(f"[CHAT] → Schema query: {len(field_names)} fields found")

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
        # HANDLE LIST ALL EMPLOYEES QUERY - Route through LLM
        # Instead of directly returning, we prepare context and let LLM respond
        # =====================================================
        if is_list_query and len(mentioned_employees) == 0:
            logger.info(f"[CHAT] → Detected LIST ALL employees query - routing through LLM")

            if not all_employees:
                # Even empty results go through LLM for natural response
                all_employees_context = "DATABASE STATUS: No employee records found in the database."
            else:
                # Build COMPACT employee data for list view (reduced fields for faster LLM processing)
                emp_data_list = []
                for e in all_employees:
                    # Get skills as a short summary (first 100 chars if too long)
                    skills = getattr(e, 'technical_skills', None) or "N/A"
                    if isinstance(skills, str) and len(skills) > 100:
                        skills = skills[:100] + "..."
                    elif isinstance(skills, list):
                        skills = ", ".join(skills[:5]) + ("..." if len(skills) > 5 else "")

                    emp_info = {
                        "employee_id": e.employee_id or str(e.id),
                        "name": e.name or "Unknown",
                        "email": e.email or "N/A",
                        "phone": getattr(e, 'phone', None) or "N/A",
                        "department": getattr(e, 'department', None) or "N/A",
                        "position": getattr(e, 'position', None) or "N/A",
                        "skills_summary": skills,
                    }
                    emp_data_list.append(emp_info)

                import json as _json
                # Compact format - removed verbose fields (work_experience, education, certifications) for faster response
                all_employees_context = f"DATABASE RECORDS ({len(all_employees)} employees):\n{_json.dumps(emp_data_list, indent=2, default=str)}"

            # Set emp to None for list queries (no single employee context)
            emp = None

            # Build LLM prompt with employee data context
            prompt = (
                "You are an Employee Management System assistant. The user is asking about employee records.\n\n"
                "INSTRUCTIONS:\n"
                "1. Use ONLY the data provided below - do NOT make up information\n"
                "2. Display ALL employee records - do not skip or summarize any\n"
                "3. Format EACH employee record clearly with:\n"
                "   - A blank line before each employee\n"
                "   - A horizontal divider line (---) between each employee record\n"
                "   - Employee ID and Name as header\n"
                "   - Key details in a clean list format\n"
                "4. If the user asked for specific fields (email, skills, etc.), focus on those\n"
                "5. If no records exist, say so politely\n\n"
                "FORMATTING EXAMPLE:\n"
                "---\n"
                "**Employee ID: 000001 | John Smith**\n"
                "- Email: john@example.com\n"
                "- Department: Engineering\n"
                "- Position: Software Developer\n"
                "- Skills: Python, Java, SQL\n"
                "\n"
                "---\n"
                "**Employee ID: 000002 | Jane Doe**\n"
                "...\n\n"
                f"{all_employees_context}\n\n"
                f"User Query: {req.prompt}\n\n"
                "Display ALL employee records with dividers between each:"
            )
            logger.info(f"[CHAT] → Prepared LLM prompt with {len(all_employees)} employee records")
            llm_prompt_prepared = True  # Mark that prompt is ready for LLM
            # Fall through to LLM call at the end of the function

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

    if is_ambiguous_employee_query and not is_crud and special_llm_context is None:
        logger.info(f"[CHAT] → Detected AMBIGUOUS employee query - routing through LLM for clarification")

        # Get list of available employees for the clarification context
        from sqlalchemy.orm import Session as ClarifySession
        clarify_db: ClarifySession = SessionLocal()
        try:
            available_employees = clarify_db.query(models.Employee).all()
            emp_names = [e.name for e in available_employees if e.name][:10]
        finally:
            clarify_db.close()

        special_llm_context = {
            "type": "ambiguous_query",
            "user_message": req.prompt,
            "available_employees": emp_names
        }

    # =====================================================
    # ANTI-HALLUCINATION GUARD #2: VERY SHORT PROMPTS
    # Prompts with < 3 words that mention employee-related terms
    # are likely ambiguous and need clarification
    # =====================================================
    short_employee_keywords = ["employee", "record", "details", "info", "skills", "experience", "email", "phone"]
    is_short_ambiguous = word_count <= 3 and any(kw in prompt_lower for kw in short_employee_keywords)

    if is_short_ambiguous and not is_crud and len(mentioned_employees) == 0 and special_llm_context is None:
        logger.info(f"[CHAT] → Detected SHORT AMBIGUOUS prompt - routing through LLM for clarification")

        special_llm_context = {
            "type": "short_ambiguous",
            "user_message": req.prompt
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

    if potential_names and len(mentioned_employees) == 0 and has_action and special_llm_context is None:
        # User mentioned a name but no match found in DB
        from sqlalchemy.orm import Session as NameCheckSession
        name_db: NameCheckSession = SessionLocal()
        try:
            all_emp_names = [e.name.lower() for e in name_db.query(models.Employee).all() if e.name]

            # Check if any potential name is NOT in the database
            unmatched_names = [n for n in potential_names if n.lower() not in all_emp_names]

            if unmatched_names:
                logger.info(f"[CHAT] → Detected query about NON-EXISTENT employee: {unmatched_names} - routing through LLM")

                available = name_db.query(models.Employee).all()
                emp_names = [e.name for e in available if e.name][:10]

                special_llm_context = {
                    "type": "nonexistent_employee",
                    "searched_name": unmatched_names[0],
                    "available_employees": emp_names,
                    "user_message": req.prompt
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
            # Parse the command using the NL-CRUD parser (enhanced for all edge cases)
            parse_prompt = (
                "You are a JSON action parser. Convert the user's natural language command into a JSON object.\n\n"
                "OUTPUT FORMAT (return ONLY valid JSON):\n"
                "{\n"
                '  "action": "create|read|update|delete",\n'
                '  "employee_id": "string ID or integer or null",\n'
                '  "employee_name": "name string or null",\n'
                '  "search_type": "name|position|skill|department|experience|seniority|location|date_range",\n'
                '  "search_term": "the search term if applicable",\n'
                '  "min_experience": "number or null (for experience queries)",\n'
                '  "max_experience": "number or null",\n'
                '  "date_range_start": "year or null",\n'
                '  "date_range_end": "year or null",\n'
                '  "exclude_terms": ["terms to exclude"] or null,\n'
                '  "seniority_filter": "senior|junior|lead|manager or null",\n'
                '  "is_bulk": true/false,\n'
                '  "fields": {"field": "value"}\n'
                "}\n\n"
                "RULES:\n"
                "1. Extract the EXACT name mentioned (e.g., 'pizzy', 'John Paul', 'Dev Raj')\n"
                "2. For position search (e.g., 'find developers'), set search_type='position'\n"
                "3. For skill search (e.g., 'python developers'), set search_type='skill'\n"
                "4. For experience search (e.g., '5+ years'), set search_type='experience', min_experience=5\n"
                "5. For seniority search (e.g., 'senior engineers'), set search_type='seniority', seniority_filter='senior'\n"
                "6. For location search (e.g., 'in Bangalore'), set search_type='location'\n"
                "7. For date range (e.g., '2020-2022'), set search_type='date_range', date_range_start=2020, date_range_end=2022\n"
                "8. For negative search (e.g., 'except managers'), add to exclude_terms\n"
                "9. If 'all', 'every', 'everyone' is used, set is_bulk=true\n\n"
                "EXAMPLES:\n"
                "- 'Update pizzy email' -> {\"action\":\"update\", \"employee_name\":\"pizzy\", \"search_type\":\"name\", \"is_bulk\":false}\n"
                "- 'Find python developers' -> {\"action\":\"read\", \"search_type\":\"skill\", \"search_term\":\"python\"}\n"
                "- 'Find employees with 5+ years experience' -> {\"action\":\"read\", \"search_type\":\"experience\", \"min_experience\":5}\n"
                "- 'Show senior engineers' -> {\"action\":\"read\", \"search_type\":\"seniority\", \"search_term\":\"engineer\", \"seniority_filter\":\"senior\"}\n"
                "- 'Find engineers except managers' -> {\"action\":\"read\", \"search_type\":\"position\", \"search_term\":\"engineer\", \"exclude_terms\":[\"manager\"]}\n"
                "- 'Employees working 2020-2022' -> {\"action\":\"read\", \"search_type\":\"date_range\", \"date_range_start\":2020, \"date_range_end\":2022}\n"
                "- 'Engineers in Bangalore' -> {\"action\":\"read\", \"search_type\":\"location\", \"search_term\":\"bangalore\"}\n"
                "- 'Most senior developers' -> {\"action\":\"read\", \"search_type\":\"seniority\", \"search_term\":\"developer\", \"seniority_filter\":\"most_senior\"}\n\n"
                f"User command:\n{prompt}\n\nJSON:"
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
                import re as _re
                db: Session = SessionLocal()

                # =====================================================
                # COMPREHENSIVE EMPLOYEE MATCHING SYSTEM
                # Handles all edge cases: duplicates, partial matches,
                # case variations, fuzzy matching, ID vs name confusion
                # =====================================================

                def normalize_name(name: str) -> str:
                    """Normalize name for matching: lowercase, remove extra spaces/hyphens.

                    ENHANCED with:
                    - Unicode/diacritics handling (José = Jose)
                    - Honorifics stripping (Dr. John = John)
                    """
                    if not name:
                        return ""
                    # Strip honorifics first (Dr., Mr., Jr., III, etc.)
                    name = strip_honorifics(name)
                    # Normalize Unicode characters (José → jose)
                    name = normalize_unicode(name)
                    # Lowercase
                    name = name.lower().strip()
                    # Replace hyphens and multiple spaces with single space
                    name = _re.sub(r'[-_]+', ' ', name)
                    name = _re.sub(r'\s+', ' ', name)
                    return name

                def get_name_variations(name: str) -> set:
                    """Get all variations of a name for fuzzy matching.

                    ENHANCED with:
                    - Unicode variations
                    - Phonetic (Soundex) codes
                    """
                    variations = set()
                    if not name:
                        return variations

                    normalized = normalize_name(name)
                    variations.add(normalized)

                    # Add without spaces (devraj from "dev raj")
                    variations.add(normalized.replace(' ', ''))

                    # Add individual parts
                    parts = normalized.split()
                    for part in parts:
                        if len(part) > 2:
                            variations.add(part)

                    # Add reversed order (paul john from john paul)
                    if len(parts) >= 2:
                        variations.add(' '.join(reversed(parts)))

                    # Add Soundex codes for phonetic matching
                    for part in parts:
                        variations.add(f"soundex:{soundex(part)}")

                    return variations

                def calculate_match_score(search_term: str, employee, match_type: str) -> dict:
                    """Calculate how well an employee matches the search term.

                    Returns dict with: employee, score, match_type, match_reason
                    Higher score = better match
                    """
                    search_norm = normalize_name(search_term)
                    search_variations = get_name_variations(search_term)

                    result = {
                        'employee': employee,
                        'score': 0,
                        'match_type': 'none',
                        'match_reason': ''
                    }

                    # Check name field
                    if employee.name:
                        name_norm = normalize_name(employee.name)
                        name_variations = get_name_variations(employee.name)

                        # Exact match (highest priority)
                        if search_norm == name_norm:
                            result['score'] = 100
                            result['match_type'] = 'exact'
                            result['match_reason'] = 'Exact name match'
                            return result

                        # Case variation match
                        if search_term.lower() == employee.name.lower():
                            result['score'] = 95
                            result['match_type'] = 'case_variant'
                            result['match_reason'] = 'Case variation match'
                            return result

                        # Space/hyphen variation (dev raj = devraj = dev-raj)
                        if search_norm.replace(' ', '') == name_norm.replace(' ', ''):
                            result['score'] = 90
                            result['match_type'] = 'space_variant'
                            result['match_reason'] = 'Space/hyphen variation'
                            return result

                        # Reversed name match (john paul = paul john)
                        search_parts = search_norm.split()
                        name_parts = name_norm.split()
                        if len(search_parts) >= 2 and len(name_parts) >= 2:
                            if set(search_parts) == set(name_parts):
                                result['score'] = 85
                                result['match_type'] = 'reversed'
                                result['match_reason'] = 'Reversed name order'
                                return result

                        # Full name contains search term
                        if search_norm in name_norm:
                            result['score'] = 70
                            result['match_type'] = 'contains'
                            result['match_reason'] = f'Name contains "{search_term}"'
                            return result

                        # Search term contains full name
                        if name_norm in search_norm:
                            result['score'] = 65
                            result['match_type'] = 'contained'
                            result['match_reason'] = f'Search contains name'
                            return result

                        # Partial match (any part of name matches)
                        for part in search_norm.split():
                            if len(part) > 2 and part in name_norm:
                                result['score'] = 50
                                result['match_type'] = 'partial'
                                result['match_reason'] = f'Partial match on "{part}"'
                                return result

                        # Nickname/substring match (johnny contains john)
                        for name_part in name_parts:
                            if len(name_part) > 3:
                                for search_part in search_parts:
                                    if len(search_part) > 2:
                                        if search_part in name_part or name_part.startswith(search_part):
                                            result['score'] = 40
                                            result['match_type'] = 'nickname'
                                            result['match_reason'] = f'Nickname/substring match'
                                            return result

                        # EDGE CASE #17: Phonetic (Soundex) match
                        # Smith = Smyth, John = Jon, Catherine = Katherine
                        if names_sound_similar(search_term, employee.name):
                            result['score'] = 35
                            result['match_type'] = 'phonetic'
                            result['match_reason'] = f'Phonetically similar (sounds like "{employee.name}")'
                            return result

                    # Check email field (devraj in devraj@company.com)
                    if employee.email:
                        email_local = employee.email.split('@')[0].lower()
                        if search_norm.replace(' ', '') in email_local or email_local in search_norm.replace(' ', ''):
                            result['score'] = 30
                            result['match_type'] = 'email'
                            result['match_reason'] = f'Email match ({employee.email})'
                            return result

                    return result

                def find_all_matches(db, search_term: str, match_type: str = 'name') -> list:
                    """Find ALL employees matching search term with scoring.

                    Args:
                        db: Database session
                        search_term: The name/term to search for
                        match_type: 'name', 'position', 'skill'

                    Returns:
                        List of match dicts sorted by score (highest first)
                    """
                    all_employees = db.query(models.Employee).all()
                    matches = []

                    for emp in all_employees:
                        if match_type == 'name':
                            result = calculate_match_score(search_term, emp, match_type)
                        elif match_type == 'position':
                            # Position-based matching
                            result = {'employee': emp, 'score': 0, 'match_type': 'none', 'match_reason': ''}
                            if emp.position:
                                pos_norm = normalize_name(emp.position)
                                search_norm = normalize_name(search_term)
                                if search_norm in pos_norm:
                                    result['score'] = 80
                                    result['match_type'] = 'position'
                                    result['match_reason'] = f'Position: {emp.position}'
                                elif any(part in pos_norm for part in search_norm.split() if len(part) > 2):
                                    result['score'] = 60
                                    result['match_type'] = 'position_partial'
                                    result['match_reason'] = f'Position contains: {emp.position}'
                        elif match_type == 'skill':
                            # Skill-based matching
                            result = {'employee': emp, 'score': 0, 'match_type': 'none', 'match_reason': ''}
                            if emp.technical_skills:
                                skills_lower = emp.technical_skills.lower()
                                search_norm = normalize_name(search_term)
                                # Check exact skill
                                if search_norm in skills_lower:
                                    result['score'] = 80
                                    result['match_type'] = 'skill_exact'
                                    result['match_reason'] = f'Has skill: {search_term}'
                                # Check skill variants (python, python3, jpython)
                                elif any(search_norm in skill.lower() or skill.lower() in search_norm
                                        for skill in skills_lower.split(',')):
                                    result['score'] = 60
                                    result['match_type'] = 'skill_variant'
                                    result['match_reason'] = f'Has related skill'
                        else:
                            result = calculate_match_score(search_term, emp, match_type)

                        if result['score'] > 0:
                            matches.append(result)

                    # Sort by score (highest first)
                    matches.sort(key=lambda x: x['score'], reverse=True)
                    return matches

                def resolve_employee_with_duplicates(db, emp_id, emp_name):
                    """Find employee(s) matching the given ID or name.

                    COMPREHENSIVE MATCHING:
                    - Case-insensitive matching
                    - Space/hyphen variations (Dev Raj = Devraj = Dev-Raj)
                    - Partial name matching (Jonathan matches "john")
                    - Email-based matching (devraj@company.com)
                    - Reversed name matching (John Paul = Paul John)

                    Returns:
                        Tuple of (single_employee_or_None, list_of_all_matches, is_id_ambiguous)
                    """
                    is_id_ambiguous = False

                    if emp_id is not None:
                        # Check if this could be both an ID and a name (edge case #6)
                        emp_id_str = str(emp_id)

                        # Try as internal ID (integer)
                        try:
                            emp = db.query(models.Employee).filter(models.Employee.id == int(emp_id_str)).first()
                            if emp:
                                # Also check if there's an employee NAMED this number
                                name_matches = find_all_matches(db, emp_id_str, 'name')
                                if name_matches and any(m['score'] >= 70 for m in name_matches):
                                    is_id_ambiguous = True
                                return (emp, [emp], is_id_ambiguous)
                        except (ValueError, TypeError):
                            pass

                        # Try as employee_id string (6-digit format)
                        emp_id_padded = emp_id_str.zfill(6)
                        emp = db.query(models.Employee).filter(models.Employee.employee_id == emp_id_padded).first()
                        if emp:
                            return (emp, [emp], False)

                        # Try without zero-padding
                        emp = db.query(models.Employee).filter(models.Employee.employee_id == emp_id_str).first()
                        if emp:
                            return (emp, [emp], False)

                        return (None, [], False)

                    elif emp_name:
                        # Use comprehensive matching
                        matches = find_all_matches(db, emp_name, 'name')

                        if not matches:
                            return (None, [], False)

                        # If only one match with high confidence, return it
                        if len(matches) == 1 and matches[0]['score'] >= 70:
                            return (matches[0]['employee'], [matches[0]], False)

                        # If multiple matches, need clarification
                        if len(matches) > 1:
                            return (None, matches, False)

                        # Single low-confidence match - still ask for confirmation
                        return (None, matches, False)

                    return (None, [], False)

                def detect_bulk_operation(prompt_text: str, fields: dict) -> tuple:
                    """Detect if this is a bulk operation affecting multiple employees.

                    Returns: (is_bulk, bulk_type, affected_group)
                    """
                    prompt_lower = prompt_text.lower()
                    bulk_keywords = ['all', 'every', 'everyone', 'all employees', 'each', 'bulk']

                    is_bulk = any(kw in prompt_lower for kw in bulk_keywords)

                    if is_bulk:
                        # Detect what group is affected
                        if 'engineer' in prompt_lower or 'developer' in prompt_lower:
                            return (True, 'position', 'engineers/developers')
                        elif 'manager' in prompt_lower:
                            return (True, 'position', 'managers')
                        elif 'department' in prompt_lower:
                            return (True, 'department', 'department group')
                        else:
                            return (True, 'all', 'all employees')

                    return (False, None, None)

                def format_employee_summary(emp, match_info=None):
                    """Format employee details for clarification message."""
                    details = [f"**Employee ID:** {emp.employee_id}"]
                    if emp.name:
                        details.append(f"**Name:** {emp.name}")
                    if emp.email:
                        details.append(f"**Email:** {emp.email}")
                    if emp.phone:
                        details.append(f"**Phone:** {emp.phone}")
                    if emp.department:
                        details.append(f"**Department:** {emp.department}")
                    if emp.position:
                        details.append(f"**Position:** {emp.position}")

                    summary = " | ".join(details)

                    # Add match reason if available
                    if match_info and isinstance(match_info, dict):
                        match_type = match_info.get('match_type', '')
                        match_reason = match_info.get('match_reason', '')
                        if match_type and match_type != 'exact':
                            summary += f" *[{match_reason}]*"

                    return summary

                def format_clarification_message(matches: list, search_term: str, action: str) -> str:
                    """Format a clarification message for multiple matches."""
                    action_verb = {
                        'update': 'update',
                        'delete': 'delete',
                        'read': 'view'
                    }.get(action, action)

                    msg = f"⚠️ **Found {len(matches)} possible matches for '{search_term}'!**\n\n"
                    msg += f"Please specify which employee you want to {action_verb} by using their **Employee ID**.\n\n"
                    msg += "**Matching employees:**\n"

                    for i, match in enumerate(matches[:10], 1):  # Limit to 10 results
                        if isinstance(match, dict):
                            emp = match.get('employee')
                            msg += f"\n{i}. {format_employee_summary(emp, match)}\n"
                        else:
                            msg += f"\n{i}. {format_employee_summary(match)}\n"

                    if len(matches) > 10:
                        msg += f"\n*...and {len(matches) - 10} more matches*\n"

                    # Add example command
                    first_match = matches[0]
                    emp_id = first_match.get('employee').employee_id if isinstance(first_match, dict) else first_match.employee_id
                    msg += f"\n**Example:** \"{action.capitalize()} employee {emp_id}"
                    if action == 'update':
                        msg += " email to new@example.com"
                    msg += "\""

                    return msg

                try:
                    action = proposal.get("action")
                    emp_id = proposal.get("employee_id")
                    emp_name = proposal.get("employee_name")
                    fields = proposal.get("fields") or {}
                    search_type = proposal.get("search_type", "name")
                    search_term = proposal.get("search_term")
                    is_bulk_from_llm = proposal.get("is_bulk", False)

                    # =====================================================
                    # Extract additional parameters for advanced queries
                    # =====================================================
                    min_experience = proposal.get("min_experience")
                    max_experience = proposal.get("max_experience")
                    date_range_start = proposal.get("date_range_start")
                    date_range_end = proposal.get("date_range_end")
                    exclude_terms = proposal.get("exclude_terms") or []
                    seniority_filter = proposal.get("seniority_filter")

                    # =====================================================
                    # EDGE CASE #13: SKILL SYNONYM SEARCH
                    # "javascript developers" finds JS, React, Node.js, etc.
                    # =====================================================
                    if search_type == 'skill' and action == 'read':
                        term = search_term or emp_name or ''
                        expanded_skills = expand_skill_search(term)

                        all_employees = db.query(models.Employee).all()
                        matches = []

                        for emp in all_employees:
                            matched, matched_skill = skills_match(term, emp.technical_skills)
                            if matched:
                                matches.append({
                                    'employee': emp,
                                    'match_reason': f'Has skill: {matched_skill}',
                                    'score': 80
                                })

                        # Apply negative filter if specified
                        if exclude_terms:
                            filtered_emps = apply_negative_filter(
                                [m['employee'] for m in matches],
                                [], exclude_terms, 'position'
                            )
                            matches = [m for m in matches if m['employee'] in filtered_emps]

                        if not matches:
                            expanded_list = ", ".join(expanded_skills[:5])
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": term,
                                    "search_type": "skill",
                                    "employees": [],
                                    "expanded_terms": expanded_list,
                                    "no_results": True
                                }
                            }
                        else:
                            emp_data_list = []
                            for match in matches[:10]:
                                emp = match['employee']
                                emp_data_list.append({
                                    "name": emp.name,
                                    "employee_id": emp.employee_id,
                                    "department": emp.department,
                                    "position": emp.position,
                                    "match_reason": match['match_reason']
                                })
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": term,
                                    "search_type": "skill",
                                    "employees": emp_data_list,
                                    "total_count": len(matches),
                                    "expanded_terms": ', '.join(expanded_skills[:5])
                                }
                            }

                    # =====================================================
                    # EDGE CASE #1: EXPERIENCE CALCULATION
                    # "find 5+ years experience" with accurate calculation
                    # =====================================================
                    if search_type == 'experience' and action == 'read':
                        results = find_employees_by_experience(db, min_experience, max_experience)

                        exp_desc = ""
                        if min_experience:
                            exp_desc = f"{min_experience}+ years"
                        if max_experience:
                            exp_desc = f"up to {max_experience} years" if not min_experience else f"{min_experience}-{max_experience} years"

                        if not results:
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": exp_desc,
                                    "search_type": "experience",
                                    "employees": [],
                                    "no_results": True
                                }
                            }
                        else:
                            emp_data_list = []
                            for emp, years in results[:15]:
                                emp_data_list.append({
                                    "name": emp.name,
                                    "employee_id": emp.employee_id,
                                    "department": emp.department,
                                    "position": emp.position,
                                    "years_experience": years
                                })
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": exp_desc,
                                    "search_type": "experience",
                                    "employees": emp_data_list,
                                    "total_count": len(results)
                                }
                            }

                    # =====================================================
                    # EDGE CASE #2: DATE RANGE OVERLAP QUERY
                    # "employees working 2020-2022" with proper overlap logic
                    # =====================================================
                    if search_type == 'date_range' and action == 'read':
                        start_year = date_range_start or 2020
                        end_year = date_range_end or start_year

                        results = find_employees_in_date_range(db, start_year, end_year)

                        if not results:
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": f"{start_year}-{end_year}",
                                    "search_type": "date_range",
                                    "employees": [],
                                    "no_results": True
                                }
                            }
                        else:
                            emp_data_list = []
                            for emp, overlaps in results[:10]:
                                overlap_info = []
                                for overlap in overlaps[:2]:
                                    job = overlap['job']
                                    overlap_info.append(f"{job.get('company', 'Unknown')} ({job.get('duration', 'N/A')})")
                                emp_data_list.append({
                                    "name": emp.name,
                                    "employee_id": emp.employee_id,
                                    "department": emp.department,
                                    "position": emp.position,
                                    "work_history": overlap_info
                                })
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": f"{start_year}-{end_year}",
                                    "search_type": "date_range",
                                    "employees": emp_data_list,
                                    "total_count": len(results)
                                }
                            }

                    # =====================================================
                    # EDGE CASE #9: TITLE SENIORITY SEARCH
                    # "senior engineers", "most senior" with proper ranking
                    # =====================================================
                    if search_type == 'seniority' and action == 'read':
                        term = search_term or ''
                        all_employees = db.query(models.Employee).all()

                        # Filter by position term if provided
                        if term:
                            all_employees = [e for e in all_employees if e.position and term.lower() in e.position.lower()]

                        # Calculate seniority scores
                        scored = []
                        for emp in all_employees:
                            score = get_title_seniority(emp.position)
                            scored.append((emp, score))

                        # Filter by seniority level
                        if seniority_filter == 'senior':
                            scored = [(e, s) for e, s in scored if s >= 5]
                        elif seniority_filter == 'junior':
                            scored = [(e, s) for e, s in scored if s <= 3]
                        elif seniority_filter == 'lead':
                            scored = [(e, s) for e, s in scored if s >= 6]
                        elif seniority_filter == 'most_senior':
                            # Sort by score descending and take top results
                            pass

                        # Sort by seniority score descending
                        scored.sort(key=lambda x: x[1], reverse=True)

                        seniority_labels = {
                            1: "Entry", 2: "Junior", 3: "Associate", 4: "Mid",
                            5: "Senior", 6: "Lead", 7: "Staff", 8: "Principal",
                            9: "Director", 10: "Executive"
                        }

                        if not scored:
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": f"{seniority_filter or 'any'} {term}".strip(),
                                    "search_type": "seniority",
                                    "employees": [],
                                    "no_results": True
                                }
                            }
                        else:
                            emp_data_list = []
                            for emp, score in scored[:10]:
                                level = seniority_labels.get(score, "Unknown")
                                emp_data_list.append({
                                    "name": emp.name,
                                    "employee_id": emp.employee_id,
                                    "department": emp.department,
                                    "position": emp.position,
                                    "seniority_level": level,
                                    "seniority_score": score
                                })
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": f"{seniority_filter or 'any'} {term}".strip(),
                                    "search_type": "seniority",
                                    "employees": emp_data_list,
                                    "total_count": len(scored)
                                }
                            }

                    # =====================================================
                    # EDGE CASE #14: NEGATIVE SEARCH
                    # "engineers except managers" excludes correctly
                    # =====================================================
                    if search_type == 'position' and exclude_terms and action == 'read':
                        term = search_term or ''
                        all_employees = db.query(models.Employee).all()

                        # Apply positive and negative filters
                        results = apply_negative_filter(
                            all_employees,
                            [term] if term else [],
                            exclude_terms,
                            'position'
                        )

                        if not results:
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": f"{term} excluding {', '.join(exclude_terms)}",
                                    "search_type": "negative_filter",
                                    "employees": [],
                                    "no_results": True
                                }
                            }
                        else:
                            emp_data_list = []
                            for emp in results[:10]:
                                emp_data_list.append({
                                    "name": emp.name,
                                    "employee_id": emp.employee_id,
                                    "department": emp.department,
                                    "position": emp.position
                                })
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": f"{term} excluding {', '.join(exclude_terms)}",
                                    "search_type": "negative_filter",
                                    "employees": emp_data_list,
                                    "total_count": len(results)
                                }
                            }

                    # =====================================================
                    # EDGE CASE #15: LOCATION/CITY FUZZY SEARCH
                    # "engineers in Bangalore" finds Bangalore, Bengaluru, BLR
                    # =====================================================
                    if search_type == 'location' and action == 'read':
                        location_term = search_term or ''
                        position_term = emp_name or ''
                        expanded_locations = expand_city_search(location_term)

                        all_employees = db.query(models.Employee).all()
                        matches = []

                        for emp in all_employees:
                            # Check if employee has location data (in raw_text or other fields)
                            emp_location = ''
                            if emp.raw_text:
                                emp_location = emp.raw_text.lower()

                            location_match = any(loc in emp_location for loc in expanded_locations)

                            # Also filter by position if specified
                            position_match = not position_term or (emp.position and position_term.lower() in emp.position.lower())

                            if location_match and position_match:
                                matches.append(emp)

                        if not matches:
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": location_term,
                                    "search_type": "location",
                                    "employees": [],
                                    "expanded_terms": ', '.join(expanded_locations[:5]),
                                    "no_results": True
                                }
                            }
                        else:
                            emp_data_list = []
                            for emp in matches[:10]:
                                emp_data_list.append({
                                    "name": emp.name,
                                    "employee_id": emp.employee_id,
                                    "department": emp.department,
                                    "position": emp.position
                                })
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": location_term,
                                    "search_type": "location",
                                    "employees": emp_data_list,
                                    "total_count": len(matches),
                                    "expanded_terms": ', '.join(expanded_locations[:5])
                                }
                            }

                    # =====================================================
                    # EDGE CASE #21: NULL/EMPTY FIELD QUERIES
                    # "employees without email", "missing phone numbers"
                    # =====================================================
                    null_field_result = parse_null_field_query(prompt)
                    if null_field_result and action == 'read':
                        field_name, is_null = null_field_result
                        field_display = field_name.replace('_', ' ').title()

                        results = find_employees_with_null_field(db, field_name, is_null)

                        status_word = "without" if is_null else "with"
                        if not results:
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": f"employees {status_word} {field_display}",
                                    "search_type": "null_field",
                                    "employees": [],
                                    "no_results": True
                                }
                            }
                        else:
                            emp_data_list = []
                            for emp in results[:15]:
                                field_val = getattr(emp, field_name, None)
                                emp_data_list.append({
                                    "name": emp.name,
                                    "employee_id": emp.employee_id,
                                    "department": emp.department,
                                    "position": emp.position,
                                    "field_value": str(field_val)[:50] if field_val else None
                                })
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": f"employees {status_word} {field_display}",
                                    "search_type": "null_field",
                                    "employees": emp_data_list,
                                    "total_count": len(results)
                                }
                            }

                    # =====================================================
                    # EDGE CASE #22: COMPOUND QUERY (AND/OR/NOT)
                    # "Python AND AWS NOT junior"
                    # =====================================================
                    compound_keywords = [' and ', ' or ', ' not ', ' except ', ' excluding ']
                    has_compound = any(kw in prompt.lower() for kw in compound_keywords)
                    if has_compound and action == 'read' and search_type != 'skill':
                        compound = parse_compound_query(prompt)

                        # Only process if we have meaningful query parts
                        if compound['must_have'] or compound['should_have'] or compound['must_not']:
                            all_employees = db.query(models.Employee).all()
                            results = apply_compound_filter(all_employees, compound)

                            query_desc = []
                            if compound['must_have']:
                                query_desc.append(f"must have: {', '.join(compound['must_have'])}")
                            if compound['should_have']:
                                query_desc.append(f"any of: {', '.join(compound['should_have'])}")
                            if compound['must_not']:
                                query_desc.append(f"excluding: {', '.join(compound['must_not'])}")

                            if not results:
                                special_llm_context = {
                                    "type": "search_results",
                                    "data": {
                                        "query": ' | '.join(query_desc),
                                        "search_type": "compound",
                                        "employees": [],
                                        "no_results": True
                                    }
                                }
                            else:
                                emp_data_list = []
                                for emp in results[:15]:
                                    emp_data_list.append({
                                        "name": emp.name,
                                        "employee_id": emp.employee_id,
                                        "department": emp.department,
                                        "position": emp.position
                                    })
                                special_llm_context = {
                                    "type": "search_results",
                                    "data": {
                                        "query": ' | '.join(query_desc),
                                        "search_type": "compound",
                                        "employees": emp_data_list,
                                        "total_count": len(results)
                                    }
                                }

                    # =====================================================
                    # EDGE CASE #20: TEMPORAL REFERENCE QUERIES
                    # "hired last year", "joined 2 months ago", "started Q1 2023"
                    # =====================================================
                    temporal_keywords = ['last year', 'this year', 'last month', 'this month',
                                        'ago', 'recently', 'last week', 'q1', 'q2', 'q3', 'q4']
                    has_temporal = any(kw in prompt.lower() for kw in temporal_keywords)
                    if has_temporal and action == 'read':
                        date_range = parse_temporal_reference(prompt)
                        if date_range:
                            start_date, end_date = date_range
                            results = find_employees_in_date_range(db, start_date.year, end_date.year)

                            if not results:
                                special_llm_context = {
                                    "type": "search_results",
                                    "data": {
                                        "query": f"{start_date.strftime('%b %Y')} - {end_date.strftime('%b %Y')}",
                                        "search_type": "temporal",
                                        "employees": [],
                                        "no_results": True
                                    }
                                }
                            else:
                                emp_data_list = []
                                for emp, overlaps in results[:10]:
                                    work_info = []
                                    for overlap in overlaps[:1]:
                                        job = overlap['job']
                                        work_info.append(f"{job.get('company', 'Unknown')} ({job.get('duration', 'N/A')})")
                                    emp_data_list.append({
                                        "name": emp.name,
                                        "employee_id": emp.employee_id,
                                        "department": emp.department,
                                        "position": emp.position,
                                        "work_history": work_info
                                    })
                                special_llm_context = {
                                    "type": "search_results",
                                    "data": {
                                        "query": f"{start_date.strftime('%b %Y')} - {end_date.strftime('%b %Y')}",
                                        "search_type": "temporal",
                                        "employees": emp_data_list,
                                        "total_count": len(results)
                                    }
                                }

                    # =====================================================
                    # STANDARD POSITION SEARCH (without skill synonyms)
                    # =====================================================
                    if search_type == 'position' and action == 'read' and not exclude_terms:
                        term = search_term or emp_name or ''
                        matches = find_all_matches(db, term, search_type)

                        if not matches:
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": term,
                                    "search_type": "position",
                                    "employees": [],
                                    "no_results": True
                                }
                            }
                        elif len(matches) > 1:
                            emp_data_list = []
                            for match in matches[:10]:
                                emp_match = match.get('employee')
                                emp_data_list.append({
                                    "name": emp_match.name,
                                    "employee_id": emp_match.employee_id,
                                    "department": emp_match.department,
                                    "position": emp_match.position,
                                    "match_reason": match.get('match_reason', '')
                                })
                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": term,
                                    "search_type": "position",
                                    "employees": emp_data_list,
                                    "total_count": len(matches)
                                }
                            }

                        else:
                            # Single match - show employee info via LLM
                            emp = matches[0].get('employee')
                            special_llm_context = {
                                "type": "employee_info",
                                "employee": {
                                    "name": emp.name,
                                    "employee_id": emp.employee_id,
                                    "position": emp.position,
                                    "department": emp.department,
                                    "email": emp.email,
                                    "technical_skills": emp.technical_skills
                                }
                            }

                    # =====================================================
                    # EDGE CASE #10: BULK OPERATION DETECTION
                    # Detect dangerous bulk operations and require confirmation
                    # =====================================================
                    is_bulk_detected, bulk_type, affected_group = detect_bulk_operation(prompt, fields)
                    is_bulk = is_bulk_from_llm or is_bulk_detected
                    if is_bulk and action in ['update', 'delete']:
                        # Count affected employees
                        if bulk_type == 'all':
                            affected_count = db.query(models.Employee).count()
                        elif bulk_type == 'position':
                            affected_count = db.query(models.Employee).filter(
                                models.Employee.position.ilike(f"%{affected_group.split('/')[0]}%")
                            ).count()
                        else:
                            affected_count = db.query(models.Employee).count()

                        if affected_count > 1:
                            special_llm_context = {
                                "type": "bulk_warning",
                                "operation": action,
                                "affected_count": affected_count,
                                "affected_group": affected_group
                            }

                    # =====================================================
                    # EDGE CASE #6: ID VS NAME CONFUSION
                    # Detect when input could be both an ID and a name
                    # =====================================================
                    if emp_id is not None and emp_name is None:
                        emp_id_str = str(emp_id)
                        # Check if this looks like it could be a name (not purely numeric)
                        if emp_id_str.isdigit():
                            # Check if there's ALSO an employee named with this number
                            name_matches = find_all_matches(db, emp_id_str, 'name')
                            id_match = None

                            # Try to find by ID
                            try:
                                id_match = db.query(models.Employee).filter(models.Employee.id == int(emp_id_str)).first()
                            except:
                                pass
                            if not id_match:
                                id_match = db.query(models.Employee).filter(
                                    models.Employee.employee_id == emp_id_str.zfill(6)
                                ).first()

                            # If both ID match and name matches exist, ask for clarification via LLM
                            if id_match and name_matches and any(m['score'] >= 50 for m in name_matches):
                                special_llm_context = {
                                    "type": "id_name_ambiguous",
                                    "input_value": emp_id_str,
                                    "operation": action,
                                    "id_match": {
                                        "name": id_match.name,
                                        "employee_id": id_match.employee_id
                                    },
                                    "name_match_count": len(name_matches)
                                }

                    # =====================================================
                    # ACTION: UPDATE
                    # =====================================================
                    if action == "update":
                        emp, all_matches, is_id_ambiguous = resolve_employee_with_duplicates(db, emp_id, emp_name)

                        # Handle multiple matches - ask for clarification via LLM
                        if not emp and len(all_matches) > 0:
                            search_term = emp_name or str(emp_id)
                            logger.info(f"[CRUD] Multiple/ambiguous matches for '{search_term}': {len(all_matches)} matches")
                            match_data = [
                                {"name": m.name, "employee_id": m.employee_id, "department": m.department, "position": m.position}
                                for m in all_matches
                            ]
                            special_llm_context = {
                                "type": "multiple_matches",
                                "matches": match_data,
                                "search_term": search_term,
                                "operation": "update"
                            }
                        elif not emp:
                            search_term = emp_name or str(emp_id)
                            available = [e.name for e in db.query(models.Employee).limit(10).all() if e.name]
                            special_llm_context = {
                                "type": "no_match",
                                "search_term": search_term,
                                "available": available,
                                "operation": "update"
                            }
                        else:
                            # Build a confirmation message
                            changes = []
                            for k, v in fields.items():
                                if hasattr(emp, k):
                                    old_val = getattr(emp, k)
                                    setattr(emp, k, v)
                                    changes.append({"field": k, "old": str(old_val), "new": str(v)})

                            db.add(emp)
                            db.commit()

                            special_llm_context = {
                                "type": "crud_result",
                                "operation": "update",
                                "success": True,
                                "details": {
                                    "employee_name": emp.name,
                                    "employee_id": emp.employee_id,
                                    "changes": changes
                                }
                            }

                    # =====================================================
                    # ACTION: CREATE
                    # =====================================================
                    elif action == "create":
                        # =====================================================
                        # DUPLICATE EMPLOYEE CHECK (Chat CRUD create)
                        # Before creating, check if this employee already exists
                        # =====================================================
                        duplicate_result = check_duplicate_employee(
                            db,
                            name=fields.get("name"),
                            email=fields.get("email"),
                            phone=fields.get("phone")
                        )

                        if duplicate_result["is_duplicate"]:
                            # Route duplicate error through LLM
                            dup_employees = [
                                {"name": e.name, "employee_id": e.employee_id, "email": e.email, "phone": e.phone}
                                for e in duplicate_result.get("matching_employees", [])
                            ]
                            special_llm_context = {
                                "type": "crud_result",
                                "operation": "create",
                                "success": False,
                                "error": "duplicate_employee",
                                "details": {
                                    "attempted_name": fields.get("name"),
                                    "matching_employees": dup_employees,
                                    "match_reasons": duplicate_result.get("match_reasons", [])
                                }
                            }
                        else:
                            # Generate employee_id
                            from sqlalchemy import text as sql_text
                            try:
                                result = db.execute(sql_text(
                                    "SELECT COALESCE(MAX(CAST(employee_id AS INTEGER)), 0) + 1 FROM employees WHERE employee_id IS NOT NULL"
                                )).scalar()
                                next_id = result if result else 1
                            except Exception:
                                count = db.query(models.Employee).count()
                                next_id = count + 1
                            new_employee_id = str(next_id).zfill(6)

                            emp = models.Employee(
                                employee_id=new_employee_id,
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

                            special_llm_context = {
                                "type": "crud_result",
                                "operation": "create",
                                "success": True,
                                "details": {
                                    "employee_name": emp.name,
                                    "employee_id": emp.employee_id,
                                    "department": emp.department or "no department"
                                }
                            }

                    # =====================================================
                    # ACTION: DELETE
                    # EDGE CASE #25: DESTRUCTIVE OPERATION CONFIRMATION
                    # Requires explicit "confirm" keyword to actually delete
                    # =====================================================
                    elif action == "delete":
                        emp, all_matches, is_id_ambiguous = resolve_employee_with_duplicates(db, emp_id, emp_name)

                        # Handle multiple matches - ask for clarification via LLM
                        if not emp and len(all_matches) > 0:
                            search_term = emp_name or str(emp_id)
                            logger.info(f"[CRUD] Multiple/ambiguous matches for deletion '{search_term}': {len(all_matches)} matches")
                            match_data = [
                                {"name": m.name, "employee_id": m.employee_id, "department": m.department, "position": m.position}
                                for m in all_matches
                            ]
                            special_llm_context = {
                                "type": "multiple_matches",
                                "matches": match_data,
                                "search_term": search_term,
                                "operation": "delete"
                            }
                        elif not emp:
                            search_term = emp_name or str(emp_id)
                            available = [e.name for e in db.query(models.Employee).limit(10).all() if e.name]
                            special_llm_context = {
                                "type": "no_match",
                                "search_term": search_term,
                                "available": available,
                                "operation": "delete"
                            }
                        else:
                            # DESTRUCTIVE OPERATION CONFIRMATION
                            # Check if user included "confirm" or "yes" in the prompt
                            confirm_keywords = ['confirm', 'confirmed', 'yes', 'proceed', 'i am sure', 'i\'m sure']
                            has_confirmation = any(kw in prompt.lower() for kw in confirm_keywords)

                            if not has_confirmation:
                                # Show warning and ask for confirmation via LLM
                                logger.info(f"[CRUD] Delete requested without confirmation for '{emp.name}'")
                                special_llm_context = {
                                    "type": "delete_confirmation",
                                    "employee": {
                                        "name": emp.name,
                                        "employee_id": emp.employee_id,
                                        "email": emp.email,
                                        "position": emp.position,
                                        "department": emp.department
                                    }
                                }
                            else:
                                # User confirmed - proceed with deletion
                                logger.info(f"[CRUD] Delete CONFIRMED for '{emp.name}' (ID: {emp.employee_id})")

                                emp_name_copy = emp.name
                                emp_employee_id_copy = emp.employee_id
                                emp_email_copy = emp.email
                                emp_position_copy = emp.position

                                # Also remove from FAISS vector store if possible
                                try:
                                    vectorstore.remove_employee(emp.id)
                                    logger.info(f"[CRUD] Removed employee {emp.id} from FAISS vector store")
                                except Exception as e:
                                    logger.warning(f"[CRUD] Could not remove from FAISS: {e}")

                                db.delete(emp)
                                db.commit()

                                special_llm_context = {
                                    "type": "crud_result",
                                    "operation": "delete",
                                    "success": True,
                                    "details": {
                                        "employee_name": emp_name_copy,
                                        "employee_id": emp_employee_id_copy,
                                        "email": emp_email_copy,
                                        "position": emp_position_copy
                                    }
                                }

                    # =====================================================
                    # ACTION: READ
                    # =====================================================
                    elif action == "read":
                        emp, all_matches, is_id_ambiguous = resolve_employee_with_duplicates(db, emp_id, emp_name)

                        # Handle multiple matches - show all with details via LLM
                        if not emp and len(all_matches) > 0:
                            search_term = emp_name or str(emp_id)
                            logger.info(f"[CRUD] Multiple matches for read '{search_term}': {len(all_matches)} matches")

                            emp_data_list = []
                            for match in all_matches[:10]:
                                if isinstance(match, dict):
                                    emp_match = match.get('employee')
                                    match_reason = match.get('match_reason', '')
                                else:
                                    emp_match = match
                                    match_reason = ''

                                emp_data_list.append({
                                    "name": emp_match.name,
                                    "employee_id": emp_match.employee_id,
                                    "email": emp_match.email,
                                    "phone": getattr(emp_match, 'phone', None),
                                    "department": getattr(emp_match, 'department', None),
                                    "position": getattr(emp_match, 'position', None),
                                    "match_reason": match_reason
                                })

                            special_llm_context = {
                                "type": "search_results",
                                "data": {
                                    "query": search_term,
                                    "search_type": "read",
                                    "employees": emp_data_list,
                                    "total_count": len(all_matches)
                                }
                            }

                        elif not emp:
                            search_term = emp_name or str(emp_id)
                            available = [e.name for e in db.query(models.Employee).limit(10).all() if e.name]
                            special_llm_context = {
                                "type": "no_match",
                                "search_term": search_term,
                                "available": available,
                                "operation": "read"
                            }
                        else:
                            # Single employee info via LLM
                            special_llm_context = {
                                "type": "employee_info",
                                "employee": {
                                    "name": emp.name,
                                    "employee_id": emp.employee_id,
                                    "email": emp.email,
                                    "phone": getattr(emp, 'phone', None),
                                    "department": getattr(emp, 'department', None),
                                    "position": getattr(emp, 'position', None)
                                }
                            }

                finally:
                    db.close()

        except Exception as e:
            logger.exception("CRUD operation failed in chat endpoint")
            # Fall back to normal chat on error
            pass

    # Fetch employee context - either by ID, session memory, or searching for name in prompt
    # SKIP this section if we've already prepared a list query prompt (llm_prompt_prepared = True)
    # or if we have a special context ready (special_llm_context is not None)
    logger.info(f"[CHAT] → Starting employee lookup... (is_list_query={is_list_query}, llm_prompt_prepared={llm_prompt_prepared})")
    from sqlalchemy.orm import Session
    db: Session = SessionLocal()
    emp = None

    # Flag to skip employee lookup ONLY for list queries (show ALL employees)
    # For other special contexts (greetings, thanks, etc.), we still do employee lookup
    # because the user might mention an employee in their greeting
    skip_employee_lookup = is_list_query and llm_prompt_prepared

    if skip_employee_lookup:
        logger.info(f"[CHAT] → Skipping employee lookup - user requested to see ALL employees")

    try:
        # Initialize variables that might be needed later
        all_employees = []
        matching_employees = []
        prompt_lower_for_search = req.prompt.lower()

        if not skip_employee_lookup:
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

            # Step 1: Search for employee in CURRENT prompt
            # Priority: Employee ID first (unique identifier), then name matching
            logger.info(f"[CHAT] → Searching for employee in current prompt...")

            # Step 1a: Try to find by Employee ID first (unique, unambiguous)
            # Patterns: "employee 000123", "employee ID 000123", "emp 000123", "#000123"
            import re as _re_emp_id
            employee_id_patterns = [
                r'employee\s+(?:id\s+)?(\d{1,6})',  # "employee 123" or "employee id 123"
                r'emp\s+(?:id\s+)?(\d{1,6})',       # "emp 123" or "emp id 123"
                r'#(\d{1,6})',                       # "#123"
                r'id[:\s]+(\d{1,6})',               # "id: 123" or "id 123"
            ]

            found_by_id = False
            for pattern in employee_id_patterns:
                match = _re_emp_id.search(pattern, prompt_lower_for_search, _re_emp_id.IGNORECASE)
                if match:
                    potential_id = match.group(1).zfill(6)  # Pad to 6 digits
                    logger.info(f"[CHAT] → Found potential employee_id pattern: '{potential_id}'")

                    # Search for this employee_id
                    for candidate in all_employees:
                        if candidate.employee_id == potential_id:
                            matching_employees = [candidate]  # Only this one, ID is unique
                            found_by_id = True
                            logger.info(f"[CHAT] ✓ Found employee by EMPLOYEE_ID: '{candidate.name}' (employee_id: {candidate.employee_id})")
                            break

                    if found_by_id:
                        break

            # Step 1b: If not found by ID, try exact full name match
            if not found_by_id:
                for candidate in all_employees:
                    if candidate.name and candidate.name.lower() in prompt_lower_for_search:
                        matching_employees.append(candidate)
                        logger.info(f"[CHAT] ✓ Found employee by EXACT name match: '{candidate.name}' (ID: {candidate.id}, employee_id: {candidate.employee_id})")

                # If no exact match, try partial matching (first name or last name)
                if not matching_employees:
                    logger.info(f"[CHAT] → No exact match, trying partial name matching...")
                    for candidate in all_employees:
                        if candidate.name:
                            # Split name into parts and check if any part is in the prompt
                            name_parts = candidate.name.lower().split()
                            for part in name_parts:
                                if len(part) > 2 and part in prompt_lower_for_search:  # Skip very short parts
                                    if candidate not in matching_employees:
                                        matching_employees.append(candidate)
                                        logger.info(f"[CHAT] ✓ Found employee by PARTIAL name match: '{candidate.name}' (ID: {candidate.id}, employee_id: {candidate.employee_id}, matched on '{part}')")
                                    break

            # Set emp to the first match (for backward compatibility), but keep track of all matches
            if matching_employees:
                # =====================================================
                # IDENTITY VERIFICATION: Multiple Employee Match Detection
                # If multiple employees share the same/similar name, do NOT proceed.
                # Instead, list all matching individuals and ask user to specify.
                # =====================================================
                if len(matching_employees) > 1:
                    logger.info(f"[CHAT] → MULTIPLE EMPLOYEES DETECTED: {[(e.name, e.employee_id) for e in matching_employees]}")
                    logger.info(f"[CHAT] → Routing through LLM for clarification")

                    # Set special context for LLM to handle clarification
                    match_data = [
                        {"name": m.name, "employee_id": m.employee_id, "email": m.email,
                         "department": getattr(m, 'department', None), "position": getattr(m, 'position', None)}
                        for m in matching_employees[:10]
                    ]
                    special_llm_context = {
                        "type": "multiple_matches",
                        "matches": match_data,
                        "search_term": req.prompt,
                        "operation": "read"
                    }
                else:
                    # Single match - proceed normally
                    emp = matching_employees[0]
                    active_employee_store[session_id] = emp.id
                    logger.info(f"[CHAT] → Found single employee match: {emp.name} (ID: {emp.id}, employee_id: {emp.employee_id})")

            # Step 2: If no employee mentioned in prompt, ONLY fall back to session memory
            # when the user uses PRONOUNS (his, her, their, etc.)
            #
            # IMPORTANT: We should NOT assume which employee the user means!
            # - If user says "show all employees" → is_list_query = True, don't use session employee
            # - If user says "what are his skills?" → has_pronoun = True, use session employee
            # - If user says "show employee details" → ambiguous, should ask for clarification
            #
            # The pronoun detection variable 'has_pronoun' is defined earlier (around line 955)
            if not emp and not is_list_query and not llm_prompt_prepared and special_llm_context is None:
                # Only use session memory when user uses pronouns (his, her, their, etc.)
                if has_pronoun:
                    active_emp_id = active_employee_store.get(session_id)
                    if active_emp_id:
                        logger.info(f"[CHAT] → User used pronouns, using session's active employee: ID {active_emp_id}")
                        emp = db.query(models.Employee).filter(models.Employee.id == active_emp_id).first()
                        if emp:
                            logger.info(f"[CHAT] ✓ Using session's active employee for pronoun: '{emp.name}' (ID: {emp.id})")

                    # Fall back to req.employee_id only if session has no active employee
                    if not emp and req.employee_id:
                        logger.info(f"[CHAT] → No session employee, using employee_id from request: {req.employee_id}")
                        emp = db.query(models.Employee).filter(models.Employee.id == req.employee_id).first()
                        if emp:
                            logger.info(f"[CHAT] ✓ Using employee from request: '{emp.name}' (ID: {emp.id})")
                            active_employee_store[session_id] = emp.id
                else:
                    logger.info(f"[CHAT] → No employee mentioned and no pronouns - will let anti-hallucination guards handle this")

                if not emp:
                    logger.warning(f"[CHAT] ✗ No employee found - no pronouns used and no name match in prompt")

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
            # Handle duplicate names: include ALL matching employees
            def build_employee_record(e):
                return f"""
--- Employee Record (Employee ID: {e.employee_id if hasattr(e, 'employee_id') and e.employee_id else 'N/A'}) ---
Name: {e.name or 'N/A'}
Email: {e.email or 'N/A'}
Phone: {e.phone if hasattr(e, 'phone') and e.phone else 'N/A'}
Department: {e.department if hasattr(e, 'department') and e.department else 'N/A'}
Position: {e.position if hasattr(e, 'position') and e.position else 'N/A'}
LinkedIn: {e.linkedin_url if hasattr(e, 'linkedin_url') and e.linkedin_url else 'N/A'}
Summary: {e.summary[:200] if hasattr(e, 'summary') and e.summary else 'N/A'}
Technical Skills: {e.technical_skills if hasattr(e, 'technical_skills') and e.technical_skills else 'N/A'}
Education: {e.education if hasattr(e, 'education') and e.education else 'N/A'}
Work Experience: {e.work_experience[:500] if hasattr(e, 'work_experience') and e.work_experience else 'N/A'}
Languages: {e.languages if hasattr(e, 'languages') and e.languages else 'N/A'}
Hobbies: {e.hobbies if hasattr(e, 'hobbies') and e.hobbies else 'N/A'}
"""
            # If there are multiple employees with the same name (duplicates), include ALL of them
            employees_to_show = matching_employees if matching_employees and len(matching_employees) > 1 else [emp]

            if len(employees_to_show) > 1:
                structured_data = f"""
=== MULTIPLE EMPLOYEE RECORDS FOUND ({len(employees_to_show)} employees with matching name) ===
NOTE: There are {len(employees_to_show)} employees with similar names. Each record is shown with its unique Employee ID.
"""
                for e in employees_to_show:
                    structured_data += build_employee_record(e)
                structured_data += "================================\n"
            else:
                structured_data = f"""
=== EMPLOYEE DATABASE RECORD ===
Employee ID: {emp.employee_id if hasattr(emp, 'employee_id') and emp.employee_id else 'N/A'}
Name: {emp.name or 'N/A'}
Email: {emp.email or 'N/A'}
Phone: {emp.phone if hasattr(emp, 'phone') and emp.phone else 'N/A'}
Department: {emp.department if hasattr(emp, 'department') and emp.department else 'N/A'}
Position: {emp.position if hasattr(emp, 'position') and emp.position else 'N/A'}
LinkedIn: {emp.linkedin_url if hasattr(emp, 'linkedin_url') and emp.linkedin_url else 'N/A'}
Summary: {emp.summary[:200] if hasattr(emp, 'summary') and emp.summary else 'N/A'}
Technical Skills: {emp.technical_skills if hasattr(emp, 'technical_skills') and emp.technical_skills else 'N/A'}
Education: {emp.education if hasattr(emp, 'education') and emp.education else 'N/A'}
Work Experience: {emp.work_experience[:500] if hasattr(emp, 'work_experience') and emp.work_experience else 'N/A'}
Languages: {emp.languages if hasattr(emp, 'languages') and emp.languages else 'N/A'}
Hobbies: {emp.hobbies if hasattr(emp, 'hobbies') and emp.hobbies else 'N/A'}
================================
"""
            logger.info(f"[CHAT] → Built structured employee data block for {len(employees_to_show)} employee(s)")

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
            # Check if LLM prompt was already prepared (e.g., for list queries)
            # If so, skip this block and fall through to LLM call
            # =====================================================
            if llm_prompt_prepared:
                logger.info(f"[CHAT] → LLM prompt already prepared (list query), skipping no-context handler")
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

    # =====================================================
    # SPECIAL CONTEXT HANDLING FOR LLM
    # If we detected special context (greeting, thanks, farewell, search results),
    # construct an appropriate prompt for the LLM to generate natural responses
    # =====================================================
    if special_llm_context is not None:
        context_type = special_llm_context.get("type", "")
        user_msg = special_llm_context.get("user_message", req.prompt)

        if context_type == "greeting":
            prompt = (
                "You are a friendly Employee Management System assistant. "
                "The user has greeted you. Respond with a warm, brief greeting and offer to help.\n\n"
                "IMPORTANT: Keep your response short (1-2 sentences). Be friendly but professional. "
                "Don't mention technical details about the system.\n\n"
                f"User said: \"{user_msg}\"\n\n"
                "Respond naturally:"
            )
        elif context_type == "schema_info":
            # Schema/field names query - show table structure
            table_name = special_llm_context.get("table_name", "employees")
            field_names = special_llm_context.get("field_names", [])
            field_count = special_llm_context.get("field_count", 0)

            fields_list = "\n".join([f"  - {field}" for field in field_names])

            prompt = (
                "You are an Employee Management System assistant. "
                f"The user wants to know the field/column names of the {table_name} table.\n\n"
                f"TABLE: {table_name}\n"
                f"TOTAL FIELDS: {field_count}\n\n"
                f"FIELD NAMES:\n{fields_list}\n\n"
                "INSTRUCTIONS:\n"
                "- Present the field names clearly in a formatted list\n"
                "- Group related fields together if helpful (e.g., basic info, professional info, etc.)\n"
                "- Mention the total number of fields\n"
                "- Be concise but informative\n"
                "- Do NOT include any actual employee data, just the field names\n\n"
                f"User asked: \"{user_msg}\"\n\n"
                "Present the schema information:"
            )
        elif context_type == "thanks":
            prompt = (
                "You are a friendly Employee Management System assistant. "
                "The user is thanking you. Respond politely and briefly.\n\n"
                "IMPORTANT: Keep your response short (1-2 sentences). Be warm and professional. "
                "Offer to help with anything else if appropriate.\n\n"
                f"User said: \"{user_msg}\"\n\n"
                "Respond naturally:"
            )
        elif context_type == "farewell":
            prompt = (
                "You are a friendly Employee Management System assistant. "
                "The user is saying goodbye. Respond with a warm farewell.\n\n"
                "IMPORTANT: Keep your response short (1-2 sentences). Be friendly.\n\n"
                f"User said: \"{user_msg}\"\n\n"
                "Respond naturally:"
            )
        elif context_type == "thanks_farewell":
            prompt = (
                "You are a friendly Employee Management System assistant. "
                "The user is thanking you and saying goodbye. Respond warmly.\n\n"
                "IMPORTANT: Keep your response short (1-2 sentences). Acknowledge their thanks and wish them well.\n\n"
                f"User said: \"{user_msg}\"\n\n"
                "Respond naturally:"
            )
        elif context_type == "search_results":
            # Search results with employee data - let LLM format naturally
            search_data = special_llm_context.get("data", {})
            search_query = search_data.get("query", "")
            employees = search_data.get("employees", [])
            search_type = search_data.get("search_type", "")

            emp_info_list = []
            for emp_data in employees[:10]:  # Limit to 10 for prompt size
                emp_info_list.append(
                    f"- {emp_data.get('name', 'Unknown')} (ID: {emp_data.get('employee_id', 'N/A')}) - "
                    f"{emp_data.get('department', 'No dept')}, {emp_data.get('position', 'No position')}"
                )
            emp_info = "\n".join(emp_info_list) if emp_info_list else "No employees found"

            prompt = (
                "You are an Employee Management System assistant. "
                f"The user searched for: \"{search_query}\"\n\n"
                f"Search type: {search_type}\n"
                f"Results found: {len(employees)}\n\n"
                f"Employee matches:\n{emp_info}\n\n"
                "INSTRUCTIONS:\n"
                "- Present these results in a clear, helpful format\n"
                "- Include employee names and IDs\n"
                "- If no results, suggest alternative searches\n"
                "- Be concise but informative\n\n"
                "Format the response naturally:"
            )
        elif context_type == "multiple_matches":
            # Multiple employees with same name - ask for clarification
            matches = special_llm_context.get("matches", [])
            search_term = special_llm_context.get("search_term", "")

            match_info = []
            for m in matches:
                match_info.append(
                    f"- {m.get('name', 'Unknown')} (Employee ID: {m.get('employee_id', 'N/A')}) - "
                    f"{m.get('department', 'No dept')}, {m.get('position', 'No position')}"
                )
            match_list = "\n".join(match_info)

            prompt = (
                "You are an Employee Management System assistant. "
                f"The user mentioned \"{search_term}\" but multiple employees match this name.\n\n"
                f"Matching employees:\n{match_list}\n\n"
                "INSTRUCTIONS:\n"
                "- Politely inform the user that multiple employees match\n"
                "- List the matching employees with their Employee IDs\n"
                "- Ask the user to specify which employee by providing the Employee ID\n"
                "- Be helpful and clear\n\n"
                "Respond naturally:"
            )
        elif context_type == "no_match":
            search_term = special_llm_context.get("search_term", "")
            available_employees = special_llm_context.get("available", [])

            emp_names = ", ".join(available_employees[:10]) if available_employees else "No employees in database"

            prompt = (
                "You are an Employee Management System assistant. "
                f"The user asked about \"{search_term}\" but no matching employee was found.\n\n"
                f"Available employees: {emp_names}\n\n"
                "INSTRUCTIONS:\n"
                "- Politely inform the user no match was found\n"
                "- Suggest checking the spelling or using an Employee ID\n"
                "- Optionally mention some available employees\n"
                "- Be helpful\n\n"
                "Respond naturally:"
            )
        elif context_type == "crud_result":
            # CRUD operation result - let LLM format confirmation
            operation = special_llm_context.get("operation", "")
            success = special_llm_context.get("success", False)
            details = special_llm_context.get("details", {})

            if success:
                prompt = (
                    "You are an Employee Management System assistant. "
                    f"A {operation} operation was completed successfully.\n\n"
                    f"Details: {details}\n\n"
                    "INSTRUCTIONS:\n"
                    "- Confirm the operation was successful\n"
                    "- Briefly summarize what was done\n"
                    "- Be concise and professional\n\n"
                    "Respond naturally:"
                )
            else:
                error_msg = special_llm_context.get("error", "Unknown error")
                prompt = (
                    "You are an Employee Management System assistant. "
                    f"A {operation} operation failed.\n\n"
                    f"Error: {error_msg}\n"
                    f"Details: {details}\n\n"
                    "INSTRUCTIONS:\n"
                    "- Inform the user about the failure\n"
                    "- Explain the error if possible\n"
                    "- Suggest how to fix it\n\n"
                    "Respond naturally:"
                )
        elif context_type == "delete_confirmation":
            # Delete confirmation request - ask user to confirm
            employee_data = special_llm_context.get("employee", {})
            prompt = (
                "You are an Employee Management System assistant. "
                "The user wants to delete an employee but hasn't confirmed yet.\n\n"
                f"Employee to delete:\n"
                f"- Name: {employee_data.get('name', 'Unknown')}\n"
                f"- Employee ID: {employee_data.get('employee_id', 'N/A')}\n"
                f"- Email: {employee_data.get('email', 'N/A')}\n"
                f"- Position: {employee_data.get('position', 'N/A')}\n"
                f"- Department: {employee_data.get('department', 'N/A')}\n\n"
                "INSTRUCTIONS:\n"
                "- Warn the user that this is a permanent action\n"
                "- List the employee's details they're about to delete\n"
                "- Ask them to confirm by saying 'delete employee [ID] confirm'\n"
                "- Mention they can cancel\n"
                "- Be clear and professional\n\n"
                "Respond naturally:"
            )
        elif context_type == "employee_info":
            # Single employee information display
            employee_data = special_llm_context.get("employee", {})
            prompt = (
                "You are an Employee Management System assistant. "
                "Present the following employee information clearly and professionally.\n\n"
                f"Employee Details:\n"
                f"- Name: {employee_data.get('name', 'Unknown')}\n"
                f"- Employee ID: {employee_data.get('employee_id', 'N/A')}\n"
                f"- Email: {employee_data.get('email', 'N/A')}\n"
                f"- Phone: {employee_data.get('phone', 'N/A')}\n"
                f"- Department: {employee_data.get('department', 'N/A')}\n"
                f"- Position: {employee_data.get('position', 'N/A')}\n"
                f"- Technical Skills: {employee_data.get('technical_skills', 'N/A')}\n\n"
                "INSTRUCTIONS:\n"
                "- Present the employee details in a clear format\n"
                "- Only include fields that have values\n"
                "- Be concise and professional\n\n"
                "Format the response naturally:"
            )
        elif context_type == "bulk_warning":
            # Bulk operation warning
            operation = special_llm_context.get("operation", "modify")
            affected_count = special_llm_context.get("affected_count", 0)
            affected_group = special_llm_context.get("affected_group", "employees")
            prompt = (
                "You are an Employee Management System assistant. "
                "The user is attempting a bulk operation that could affect many employees.\n\n"
                f"Operation: {operation}\n"
                f"Affected employees: {affected_count}\n"
                f"Group: {affected_group}\n\n"
                "INSTRUCTIONS:\n"
                "- Warn the user about the bulk operation risk\n"
                "- Tell them this would affect multiple employees\n"
                "- Suggest they: A) Update ONE employee by specifying Employee ID, "
                "B) View the affected list first, or C) Cancel\n"
                "- Ask them to choose A, B, C, or provide a specific Employee ID\n"
                "- Be clear about the risk\n\n"
                "Respond naturally:"
            )
        elif context_type == "id_name_ambiguous":
            # ID vs Name ambiguity
            input_value = special_llm_context.get("input_value", "")
            operation = special_llm_context.get("operation", "modify")
            id_match = special_llm_context.get("id_match", {})
            name_match_count = special_llm_context.get("name_match_count", 0)
            prompt = (
                "You are an Employee Management System assistant. "
                f"The user input '{input_value}' is ambiguous - it could be an Employee ID or a name.\n\n"
                f"If it's an Employee ID: Would {operation} {id_match.get('name', 'Unknown')} "
                f"(Employee ID: {id_match.get('employee_id', 'N/A')})\n"
                f"If it's a name: Found {name_match_count} employee(s) with matching names\n\n"
                "INSTRUCTIONS:\n"
                "- Ask the user to clarify if this is an ID or a name\n"
                "- Suggest they reply with 'ID' or 'name'\n"
                "- Or they can specify more clearly\n"
                "- Be helpful and clear\n\n"
                "Respond naturally:"
            )
        elif context_type == "ambiguous_query":
            # Ambiguous employee query - need clarification
            available = special_llm_context.get("available_employees", [])
            emp_list = ", ".join(available) if available else "No employees in database"
            prompt = (
                "You are an Employee Management System assistant. "
                "The user's query is ambiguous - they mentioned employees but didn't specify which one.\n\n"
                f"Available employees: {emp_list}\n\n"
                f"User said: \"{special_llm_context.get('user_message', '')}\"\n\n"
                "INSTRUCTIONS:\n"
                "- Politely ask which employee they're interested in\n"
                "- List some available employees\n"
                "- Suggest they can say 'all employees' to see everyone\n"
                "- Be helpful and friendly\n\n"
                "Respond naturally:"
            )
        elif context_type == "short_ambiguous":
            # Very short/ambiguous prompt
            prompt = (
                "You are an Employee Management System assistant. "
                "The user's query is too brief to understand what they need.\n\n"
                f"User said: \"{special_llm_context.get('user_message', '')}\"\n\n"
                "INSTRUCTIONS:\n"
                "- Politely ask for more details\n"
                "- Give examples of what they can ask (show all employees, specific person's details, etc.)\n"
                "- Be helpful and encouraging\n\n"
                "Respond naturally:"
            )
        elif context_type == "nonexistent_employee":
            # User asked about someone not in database
            searched = special_llm_context.get("searched_name", "")
            available = special_llm_context.get("available_employees", [])
            emp_list = ", ".join(available) if available else "No employees in database"
            prompt = (
                "You are an Employee Management System assistant. "
                f"The user asked about '{searched}' but this person is not in the database.\n\n"
                f"Available employees: {emp_list}\n\n"
                f"User said: \"{special_llm_context.get('user_message', '')}\"\n\n"
                "INSTRUCTIONS:\n"
                "- Politely inform them the person wasn't found\n"
                "- Suggest available employees they might be looking for\n"
                "- Ask if they meant someone else or want to see all employees\n"
                "- Be helpful\n\n"
                "Respond naturally:"
            )
        else:
            # Generic special context - pass through
            logger.info(f"[CHAT] → Unknown special context type: {context_type}")

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
    # Returns tuple: (employee, matching_employees_list)
    # If multiple matches found, employee is None and list contains all matches
    def resolve_employee(db, emp_id, emp_name):
        if emp_id:
            emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
            return (emp, [])
        elif emp_name:
            # Case-insensitive partial name match - get ALL matches
            matches = db.query(models.Employee).filter(models.Employee.name.ilike(f"%{emp_name}%")).all()

            if len(matches) == 0:
                # Try exact match as fallback
                emp = db.query(models.Employee).filter(models.Employee.name == emp_name).first()
                return (emp, [])
            elif len(matches) == 1:
                # Single match - proceed
                return (matches[0], [])
            else:
                # Multiple matches - return all for user clarification
                return (None, matches)
        return (None, [])

    try:
        if action == "create":
            # =====================================================
            # DUPLICATE EMPLOYEE CHECK (NL-CRUD create)
            # Before creating, check if this employee already exists
            # =====================================================
            duplicate_result = check_duplicate_employee(
                db,
                name=fields.get("name"),
                email=fields.get("email"),
                phone=fields.get("phone")
            )

            if duplicate_result["is_duplicate"]:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "duplicate_employee",
                        "message": "An employee with similar details already exists in the database.",
                        "matching_employees": duplicate_result["matching_employees"],
                        "match_reasons": duplicate_result["match_reasons"]
                    }
                )

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
            emp, multiple_matches = resolve_employee(db, emp_id, emp_name)
            if multiple_matches:
                # Multiple employees share the same name - ask user to specify
                matching_list = [{"id": m.id, "employee_id": m.employee_id, "name": m.name, "email": m.email, "department": m.department, "position": m.position} for m in multiple_matches]
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "multiple_matches",
                        "message": f"Multiple employees found matching '{emp_name}'. Please specify using the Employee ID.",
                        "matching_employees": matching_list
                    }
                )
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
            emp, multiple_matches = resolve_employee(db, emp_id, emp_name)
            if multiple_matches:
                # Multiple employees share the same name - ask user to specify
                matching_list = [{"id": m.id, "employee_id": m.employee_id, "name": m.name, "email": m.email, "department": m.department, "position": m.position} for m in multiple_matches]
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "multiple_matches",
                        "message": f"Multiple employees found matching '{emp_name}'. Please specify using the Employee ID.",
                        "matching_employees": matching_list
                    }
                )
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
            emp, multiple_matches = resolve_employee(db, emp_id, emp_name)
            if multiple_matches:
                # Multiple employees share the same name - ask user to specify
                matching_list = [{"id": m.id, "employee_id": m.employee_id, "name": m.name, "email": m.email, "department": m.department, "position": m.position} for m in multiple_matches]
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "multiple_matches",
                        "message": f"Multiple employees found matching '{emp_name}'. Please specify using the Employee ID.",
                        "matching_employees": matching_list
                    }
                )
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
