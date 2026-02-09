# EMS 2.0 - Architecture Flow & Validation Checks

## Overview
This document outlines all validation checks and guards in the Employee Management System, organized by the data flow architecture.

---

## Architecture Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INPUT                                      │
│                    (PDF Upload / Chat Message / API)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAYER 1: INPUT VALIDATION                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ File Type Check │  │ Resume Validator│  │ Text Length     │              │
│  │ (PDF only)      │  │ (Score >= 40)   │  │ Check           │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAYER 2: DUPLICATE DETECTION                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Email Match     │  │ Phone Match     │  │ Name Match      │              │
│  │ (exact)         │  │ (last 10 digits)│  │ (exact/subset)  │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                        [Currently DISABLED]                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAYER 3: INTENT CLASSIFICATION                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ CRUD Detection  │  │ Search Detection│  │ Greeting/Thanks │              │
│  │ (create/update/ │  │ (skill/exp/date)│  │ Detection       │              │
│  │  delete/read)   │  │                 │  │                 │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAYER 4: IDENTITY VERIFICATION                       │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │ Employee Resolution                                              │        │
│  │  • Single match → Proceed                                        │        │
│  │  • Multiple matches → Ask for Employee ID                        │        │
│  │  • No match → Trigger anti-hallucination guard                   │        │
│  └─────────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAYER 5: ANTI-HALLUCINATION GUARDS                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ Guard #1        │  │ Guard #2        │  │ Guard #3        │              │
│  │ Ambiguous Query │  │ Short Prompt    │  │ Non-existent    │              │
│  │ → Clarify       │  │ → Ask for more  │  │ Employee        │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│  ┌─────────────────┐  ┌─────────────────┐                                   │
│  │ Guard #4        │  │ Guard #5        │                                   │
│  │ Leading Question│  │ Pressure/Urgency│                                   │
│  │ Trap            │  │ Prompts         │                                   │
│  └─────────────────┘  └─────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAYER 6: LLM PROCESSING                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ JSON Extraction │  │ Pydantic        │  │ Field           │              │
│  │ & Validation    │  │ Validation      │  │ Sanitization    │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                                                              │
│  ALL responses route through LLM via special_llm_context                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAYER 7: DATABASE OPERATIONS                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ PostgreSQL      │  │ FAISS Vector    │  │ MongoDB GridFS  │              │
│  │ (Structured)    │  │ (Embeddings)    │  │ (File Storage)  │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Input Validation

### 1.1 File Type Check
**Location**: `/upload` endpoint
**File**: `backend/app/main.py`

| Check | Condition | Action |
|-------|-----------|--------|
| File extension | Must be `.pdf` | Reject with error message |
| File size | Must be < 10MB | Reject with error message |
| Content type | Must be `application/pdf` | Reject with error message |

### 1.2 Resume Validation
**Location**: `validate_is_resume()` function
**File**: `backend/app/services/validators.py` (Lines 178-345)

| Component | Points | Criteria |
|-----------|--------|----------|
| Section Headers | 35 | experience, education, skills, objective, summary, etc. |
| Professional Keywords | 25 | managed, developed, implemented, led, etc. |
| Contact Information | 25 | Email pattern, phone pattern |
| Date Patterns | 15 | Year formats (19xx, 20xx), month names |
| **THRESHOLD** | **40** | Minimum score to accept as valid resume |

```
Score < 40  → REJECT: "This doesn't appear to be a resume"
Score >= 40 → ACCEPT: Proceed to extraction
```

### 1.3 Text Length Check
**Location**: Chat endpoint, resume text creation
**File**: `backend/app/main.py`

| Check | Condition | Action |
|-------|-----------|--------|
| Create command | `create ` prefix + length > 100 chars | Treat as resume text |
| Short prompt | Length < 10 chars | Trigger Guard #2 |

---

## Layer 2: Duplicate Detection

**Status**: 🔴 DISABLED (Lines 288-290)

**Location**: `check_duplicate_employee()` function
**File**: `backend/app/main.py` (Lines 209-291)

### Detection Methods (When Enabled)

| Method | Logic | Weight |
|--------|-------|--------|
| Email Match | Case-insensitive exact match | Primary |
| Phone Match | Last 10 digits comparison | Primary |
| Name Match | Exact match OR subset match | Secondary |

### Trigger Points

| Location | Line | When Triggered |
|----------|------|----------------|
| PDF Upload | ~747 | After text extraction, before DB insert |
| Resume Text Create | ~1194 | After LLM extraction, before DB insert |
| CRUD Create | ~2816 | Before creating new employee |
| NL Confirm | ~4062 | During confirmation flow |

### Current State
```python
return {
    "is_duplicate": False,        # Always returns no duplicate
    "matching_employees": [],
    "match_reasons": []
}
```

---

## Layer 3: Intent Classification

**Location**: Chat endpoint
**File**: `backend/app/main.py`

### 3.1 CRUD Detection

| Intent | Keywords/Patterns |
|--------|-------------------|
| CREATE | `create`, `add`, `new`, `insert`, `register` |
| READ | `show`, `get`, `display`, `view`, `info`, `details` |
| UPDATE | `update`, `change`, `modify`, `edit`, `set` |
| DELETE | `delete`, `remove`, `fire`, `terminate` |

### 3.2 Search Detection

| Search Type | Pattern Examples |
|-------------|------------------|
| Skill Search | "who knows Python", "employees with Java" |
| Experience Search | "5+ years experience", "senior developers" |
| Date Range | "joined in 2023", "hired between Jan-March" |
| Location | "employees in Bangalore", "from India" |
| Department | "engineering team", "QA department" |
| Compound | "Python AND 5 years", "Java OR JavaScript" |

### 3.3 List All Employees Detection

**Keywords** (Lines ~1469-1478):
```
all employees, all employee, everyone, all records, all people,
all candidates, employee records, employee details, employees,
all the employees, all the records, every employee, each employee,
list of employees, employee list, people in the system,
everyone in the system, all staff, all personnel,
list all employee records, all employee records, show all records,
display all employees, display all records, get all employees
```

### 3.4 Greeting/Thanks Detection

| Type | Keywords |
|------|----------|
| Greeting | hello, hi, hey, good morning/afternoon/evening |
| Thanks | thank you, thanks, appreciate |
| Farewell | bye, goodbye, see you, take care |

---

## Layer 4: Identity Verification

**Location**: `resolve_employee()` function
**File**: `backend/app/main.py` (Lines ~3286-3307)

### Resolution Logic

```
┌─────────────────────────┐
│ User mentions employee  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│ Employee ID provided?   │─YES─▶│ Query by ID             │
└───────────┬─────────────┘     │ Return single employee  │
            │ NO                └─────────────────────────┘
            ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│ Search by name          │─────▶│ How many matches?       │
└─────────────────────────┘     └───────────┬─────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
            ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
            │ 0 matches     │       │ 1 match       │       │ 2+ matches    │
            │ → Guard #3    │       │ → Proceed     │       │ → Ask for ID  │
            └───────────────┘       └───────────────┘       └───────────────┘
```

### Multiple Match Response
When multiple employees match, system displays:
```
Multiple employees found with similar names:
• [ID: 000001] John Smith - Engineering
• [ID: 000002] John Smith - Marketing

Please specify the Employee ID to proceed.
```

---

## Layer 5: Anti-Hallucination Guards

**Location**: Chat endpoint
**File**: `backend/app/main.py`

### Guard #1: Ambiguous Employee Queries
**Trigger**: Query mentions employee but context is unclear
**Action**: Ask for clarification via LLM

```python
special_llm_context = {
    "type": "ambiguous_query",
    "user_message": req.prompt,
    "available_employees": [...list of employees...]
}
```

### Guard #2: Very Short Prompts
**Trigger**: Prompt length < 10 characters (non-greeting)
**Action**: Ask for more context via LLM

```python
special_llm_context = {
    "type": "short_ambiguous",
    "user_message": req.prompt
}
```

### Guard #3: Non-Existent Employee Queries
**Trigger**: User asks about employee not in database
**Action**: Show available employees, suggest alternatives via LLM

```python
special_llm_context = {
    "type": "nonexistent_employee",
    "searched_name": "...",
    "available_employees": [...list of employees...]
}
```

### Guard #4: Leading Question Traps
**Trigger**: User tries to confirm false information
**Example**: "Confirm that John has 20 years experience" (when he has 5)
**Action**: LLM responds based on actual data, not user's claim

### Guard #5: Pressure/Urgency Prompts
**Trigger**: User uses urgency language ("URGENT", "immediately", "right now")
**Action**: Process normally, don't skip validations

---

## Layer 6: LLM Processing

### 6.1 All Queries Route Through LLM

**Principle**: No hardcoded responses. All user inputs processed by LLM.

**Special Context Types**:

| Context Type | Purpose |
|--------------|---------|
| `greeting` | Natural greeting responses |
| `thanks` | Polite acknowledgment |
| `farewell` | Warm goodbye |
| `thanks_farewell` | Combined response |
| `search_results` | Formatted search output |
| `multiple_matches` | Disambiguation request |
| `no_match` | Helpful "not found" message |
| `crud_result` | Operation confirmations |
| `delete_confirmation` | Deletion warnings |
| `employee_info` | Single employee details |
| `bulk_warning` | Bulk operation warnings |
| `id_name_ambiguous` | ID vs name clarification |
| `ambiguous_query` | Guard #1 response |
| `short_ambiguous` | Guard #2 response |
| `nonexistent_employee` | Guard #3 response |

### 6.2 JSON Extraction Validation

**For Resume Processing**:
1. LLM extracts structured JSON from resume text
2. JSON parsed and validated
3. Invalid JSON → Retry with cleaned response
4. Pydantic model validates all fields

### 6.3 Field Sanitization

| Field | Sanitization |
|-------|--------------|
| Email | Lowercase, trim whitespace |
| Phone | Extract digits, normalize format |
| Name | Trim whitespace, title case |
| URLs | Validate format, add https:// if missing |

---

## Layer 7: Database Operations

### 7.1 PostgreSQL (Structured Data)

**Employee Fields**: 22+ fields including:
- Basic: name, email, phone
- Professional: department, position
- URLs: linkedin_url, portfolio_url, github_url
- Career: career_objective, summary
- Experience: work_experience (JSON)
- Education: education (JSON)
- Skills: technical_skills, soft_skills, languages (JSON)
- Additional: certifications, achievements, hobbies (JSON)
- Location: address, city, country

**Constraints**:
- Unique Employee ID (6-digit zero-padded)
- Email format validation
- Required fields: name

### 7.2 FAISS Vector Store

**Purpose**: Semantic search via embeddings
**Model**: `all-MiniLM-L6-v2`
**Configuration**:
- Chunk size: 500
- Chunk overlap: 100
- Top K results: 5

### 7.3 MongoDB GridFS

**Purpose**: Raw file and JSON storage
**Stored Items**:
- Original PDF files
- Extracted JSON data
- Processing metadata

---

## Session Memory

### Pronoun Resolution

**Location**: Lines ~3154-3180
**Store**: `active_employee_store` (in-memory dict)

**Logic**:
```
User uses pronoun (his/her/their/he/she)?
    YES → Look up last discussed employee from session
    NO  → Follow user's explicit query (no assumptions)
```

**Pronoun Keywords**:
```
his, her, their, he, she, him, them, employee's, person's
```

---

## Check Status Summary

| Layer | Check | Status |
|-------|-------|--------|
| 1 | File Type Validation | ✅ Active |
| 1 | Resume Validation (Score) | ✅ Active |
| 1 | Text Length Check | ✅ Active |
| 2 | Email Duplicate | 🔴 Disabled |
| 2 | Phone Duplicate | 🔴 Disabled |
| 2 | Name Duplicate | 🔴 Disabled |
| 3 | CRUD Intent Detection | ✅ Active |
| 3 | Search Intent Detection | ✅ Active |
| 3 | Greeting/Thanks Detection | ✅ Active |
| 4 | Single Employee Resolution | ✅ Active |
| 4 | Multiple Match → Ask ID | ✅ Active |
| 5 | Guard #1 (Ambiguous) | ✅ Active |
| 5 | Guard #2 (Short Prompt) | ✅ Active |
| 5 | Guard #3 (Non-existent) | ✅ Active |
| 5 | Guard #4 (Leading Questions) | ✅ Active |
| 5 | Guard #5 (Pressure Prompts) | ✅ Active |
| 6 | All Queries → LLM | ✅ Active |
| 6 | JSON Validation | ✅ Active |
| 6 | Pydantic Validation | ✅ Active |
| 7 | SQL Constraints | ✅ Active |
| 7 | FAISS Indexing | ✅ Active |

---

---

## Changelog: Bug Fixes & Errors Resolved

### BUG-001: CRUD Operations Not Working (Create, Update, Delete)
**Date**: February 2026
**Severity**: Critical
**Symptoms**: Create, update, and delete commands via chatbot were not executing database operations.

**Root Causes Found (3 issues)**:

| # | Root Cause | Location | Impact |
|---|-----------|----------|--------|
| 1 | Multi-query detection intercepting CRUD commands | `main.py:1017-1018` | Resume text in "create" commands and "and" in update commands triggered multi-query handler, preventing CRUD routing |
| 2 | Name-based employee context check only ran for delete/remove | `main.py:1604-1622` | Commands like "update john's email" failed because employee name lookup only ran for delete/remove, not update/create/modify |
| 3 | `has_employee_context` too restrictive for create/add | `main.py:1601` | "create" commands don't reference existing employees, so context check failed |

**Fixes Applied**:

**Fix 1** - Skip multi-query detection for ALL CRUD commands (Line 1017-1021):
```python
# BEFORE (broken):
is_create_command = prompt.lower().strip().startswith("create ")
if detect_multi_query(prompt) and len(prompt) > 50 and not is_create_command:

# AFTER (fixed):
_crud_starters = ["create ", "update ", "delete ", "remove ", "add ", "change ", "modify ", "set "]
is_crud_command = any(_prompt_lower_mq.startswith(s) for s in _crud_starters)
if detect_multi_query(prompt) and len(prompt) > 50 and not is_crud_command:
```

**Fix 2** - Extend name-based lookup to ALL CRUD operations (Line 1606-1634):
```python
# BEFORE (broken - only delete/remove):
if not has_employee_context and any(kw in prompt.lower() for kw in ["delete", "remove"]):

# AFTER (fixed - all CRUD):
if not has_employee_context and is_crud:
```

**Fix 3** - Auto-set employee context for create/add commands (Line 1627-1631):
```python
# NEW: Create/add don't need existing employee names
if not has_employee_context and any(kw in prompt_lower_check_crud for kw in ["create", "add"]):
    has_employee_context = True
```

### BUG-002: Resume Validation Rejecting Valid Resumes
**Date**: February 2026
**Severity**: High
**Symptoms**: `create` command with pasted resume text returned "not_a_resume" error.

**Root Cause**: Email/phone regex patterns used `^...$` anchors, which only match entire strings, not patterns within text.

**Fix** (validators.py Lines 250-251):
```python
# BEFORE (broken):
email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# AFTER (fixed):
email_search_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
```

### BUG-003: Image Uploads Failing with "not_a_resume"
**Date**: February 2026
**Severity**: Medium
**Symptoms**: OCR-extracted text from images didn't meet resume validation threshold.

**Fix** (main.py): Added lenient validation for images since OCR text is imperfect:
```python
if is_image and not resume_validation.is_valid:
    if len(pdf_text.strip()) > 100 and resume_validation.confidence >= 0.15:
        resume_validation = ValidationResult(is_valid=True, ...)
```

### BUG-004: AttributeError 'ExtractionResult' has no attribute 'warnings'
**Date**: February 2026
**Severity**: Medium
**Symptoms**: Server crash on resume upload.

**Fix**: Changed `validation_result.warnings` to `validation_result.validation_warnings`.

### BUG-005: "Show All Employees" Only Showing 5 Records
**Date**: February 2026
**Severity**: Low
**Symptoms**: Character limit `[:8000]` truncated employee list data.

**Fix**: Removed the character limit for list queries.

---

*Document created: February 2026*
*Last updated: February 2026*
*System: EMS 2.0 - Employee Management System*
