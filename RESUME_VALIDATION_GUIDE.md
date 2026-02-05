# Resume Validation System

## Overview

The Resume Validation System determines whether an uploaded document is actually a resume/CV before processing. This prevents non-resume documents (invoices, contracts, cover letters) from being processed and stored in the database.

**Location:** `backend/app/services/validators.py` - `validate_is_resume()` function (Lines 179-349)

---

## Scoring System

The system uses a **point-based scoring system** (0-100 points) to determine if a document is a resume.

```
┌─────────────────────────────────────────────────────────────────┐
│                    RESUME SCORING SYSTEM                         │
│                                                                  │
│  THRESHOLD TO PASS: 40 points (Line 309)                        │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  POSITIVE INDICATORS (Add Points)                        │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  Section Keywords (max +35 pts)                          │    │
│  │  • "experience", "education", "skills", "objective"      │    │
│  │  • 3+ matches = +35 pts                                  │    │
│  │  • 2 matches = +25 pts                                   │    │
│  │  • 1 match = +15 pts                                     │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  Professional Keywords (max +25 pts)                     │    │
│  │  • "resume", "cv", "position", "responsibilities"        │    │
│  │  • "manager", "engineer", "developer", "analyst"         │    │
│  │  • 4+ matches = +25 pts                                  │    │
│  │  • 2+ matches = +15 pts                                  │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  Contact Information (max +25 pts)                       │    │
│  │  • Email found = +15 pts                                 │    │
│  │  • Phone found = +10 pts                                 │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  Date Patterns (max +15 pts)                             │    │
│  │  • "2018-2020", "Jan 2020 - Present"                     │    │
│  │  • 2+ matches = +15 pts                                  │    │
│  │  • 1 match = +8 pts                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  NEGATIVE INDICATORS (Subtract Points)                   │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  Non-Resume Document Types (-20 pts each)                │    │
│  │  • "invoice", "receipt", "contract"                      │    │
│  │  • "agreement", "bill", "statement"                      │    │
│  │  • "report", "memo", "policy", "manual"                  │    │
│  │  • "cover letter" (not a resume)                         │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Validation Steps

### Step 1: Initial Length Check (Lines 194-200)

```python
if not text or len(text.strip()) < 50:
    return ValidationResult(
        is_valid=False,
        errors=["Document is too short or empty to be a valid resume"],
        confidence=0.0
    )
```

Documents with less than 50 characters are immediately rejected.

---

### Step 2: Section Keywords Detection (Lines 213-228)

```python
section_keywords = [
    "experience", "work experience", "employment history", "professional experience",
    "education", "academic background", "qualifications",
    "skills", "technical skills", "core competencies", "expertise",
    "objective", "career objective", "professional summary", "summary",
    "certifications", "certificates", "licenses",
    "projects", "achievements", "accomplishments",
    "references", "awards", "publications"
]

section_matches = sum(1 for kw in section_keywords if kw in text_lower)

if section_matches >= 3:
    score += 35  # Strong resume indicator
elif section_matches >= 2:
    score += 25
elif section_matches >= 1:
    score += 15
```

---

### Step 3: Professional Terms Detection (Lines 231-245)

```python
professional_keywords = [
    "resume", "cv", "curriculum vitae",
    "job", "position", "role", "responsibilities",
    "employer", "company", "organization",
    "manager", "engineer", "developer", "analyst", "consultant",
    "worked", "managed", "developed", "led", "implemented",
    "years of experience", "years experience"
]

professional_matches = sum(1 for kw in professional_keywords if kw in text_lower)

if professional_matches >= 4:
    score += 25
elif professional_matches >= 2:
    score += 15
elif professional_matches >= 1:
    score += 8
```

---

### Step 4: Contact Information Detection (Lines 250-258)

```python
# Email pattern (without anchors for text searching)
email_search_pattern = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
)

# Phone pattern
phone_search_pattern = re.compile(
    r'[\+]?[\d\s\-\.\(\)]{10,20}'
)

has_email = bool(email_search_pattern.search(text))  # +15 pts
has_phone = bool(phone_search_pattern.search(text))  # +10 pts

if has_email:
    score += 15
if has_phone:
    score += 10
```

---

### Step 5: Date Pattern Detection (Lines 261-270)

```python
date_patterns = [
    r'\b(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}\b',           # 2018-2020
    r'\b(19|20)\d{2}\s*[-–]\s*(present|current|now)\b',  # 2020-Present
    r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(19|20)\d{2}\b',  # Jan 2020
]

date_matches = sum(1 for pattern in date_patterns if re.search(pattern, text_lower))

if date_matches >= 2:
    score += 15
elif date_matches >= 1:
    score += 8
```

---

### Step 6: Non-Resume Detection (Lines 277-299)

```python
non_resume_indicators = [
    ("invoice", "invoice"),
    ("receipt", "receipt"),
    ("contract", "legal contract"),
    ("agreement", "agreement document"),
    ("bill", "billing document"),
    ("statement", "bank/financial statement"),
    ("report", "report document"),
    ("meeting minutes", "meeting minutes"),
    ("memo", "memorandum"),
    ("policy", "policy document"),
    ("manual", "user manual"),
    ("instructions", "instruction document"),
    ("letter of recommendation", "recommendation letter"),
    ("cover letter", "cover letter (not a resume)")
]

for indicator, doc_type in non_resume_indicators:
    indicator_count = text_lower.count(indicator)
    # Flag if appears 3+ times OR in title (first 200 chars) with few resume sections
    if indicator_count >= 3 or (indicator in text_lower[:200] and section_matches < 2):
        score -= 20
        warnings.append(f"Document may be a {doc_type} rather than a resume")
```

---

### Step 7: Final Decision (Lines 309-338)

```python
RESUME_THRESHOLD = 40  # Minimum score required

if score < RESUME_THRESHOLD:
    # Build helpful error message
    missing = []
    if section_matches < 2:
        missing.append("resume sections (experience, education, skills)")
    if not has_email and not has_phone:
        missing.append("contact information (email or phone)")
    if professional_matches < 2:
        missing.append("professional/career-related content")

    error_msg = "The uploaded document does not appear to be a resume/CV. "
    if missing:
        error_msg += f"Missing: {', '.join(missing)}. "
    error_msg += "Please upload a valid resume document."

    return ValidationResult(
        is_valid=False,
        errors=[error_msg],
        confidence=confidence
    )

# Document accepted as resume
return ValidationResult(
    is_valid=True,
    value=text,
    confidence=confidence
)
```

---

## Example Scenarios

| Document Type | Score Calculation | Result |
|--------------|-------------------|--------|
| **Valid Resume** | Sections(35) + Professional(25) + Email(15) + Phone(10) + Dates(15) = **100** | ✅ PASS |
| **Invoice** | Phone(10) + Dates(8) - Invoice(-20) = **-2** | ❌ REJECT |
| **Cover Letter** | Professional(15) + Email(15) - CoverLetter(-20) = **10** | ❌ REJECT |
| **Random PDF** | No matches = **0** | ❌ REJECT |
| **Minimal Resume** | Sections(15) + Email(15) + Professional(15) = **45** | ✅ PASS (barely) |

---

## Integration in main.py

### Where Validation is Called

```python
# Line ~1050-1070 in main.py
resume_validation = validate_is_resume(pdf_text)

if not resume_validation.is_valid:
    return {
        "status": "error",
        "error": "not_a_resume",
        "message": resume_validation.errors[0]
    }
```

### Validation Flow

```
Upload PDF/Image
       │
       ▼
Extract Text (extractor.py)
       │
       ▼
validate_is_resume(text)
       │
       ├── Score < 40 ──→ REJECT with error message
       │
       └── Score >= 40 ──→ CONTINUE to LLM extraction
```

---

## ValidationResult Data Class

```python
@dataclass
class ValidationResult:
    is_valid: bool              # True if document passes validation
    value: Any                  # The validated/cleaned value
    errors: List[str]           # List of error messages
    warnings: List[str]         # List of warning messages
    confidence: float           # Confidence score (0.0 - 1.0)
```

---

## Lenient Validation for Images

For OCR-extracted text from images, validation is more lenient since OCR can miss text:

```python
# In main.py - special handling for images
if is_image and not resume_validation.is_valid:
    # If OCR extracted substantial text with some confidence
    if len(pdf_text.strip()) > 100 and resume_validation.confidence >= 0.15:
        resume_validation = ValidationResult(
            is_valid=True,
            value=pdf_text,
            confidence=resume_validation.confidence
        )
    elif len(pdf_text.strip()) > 50:
        # Accept with low confidence
        resume_validation = ValidationResult(
            is_valid=True,
            value=pdf_text,
            confidence=0.1
        )
```

---

## Logging

The system logs validation results for debugging:

```python
# Rejection logging
logger.warning(f"[VALIDATOR] Document rejected as non-resume. Score: {score}/{max_score}, "
              f"Sections: {section_matches}, Professional: {professional_matches}, "
              f"Email: {has_email}, Phone: {has_phone}")

# Acceptance logging
logger.info(f"[VALIDATOR] Document accepted as resume. Score: {score}/{max_score}, "
            f"Confidence: {confidence:.2f}")
```

---

## Configuration

The threshold and scoring weights are defined at the top of the function and can be adjusted:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `RESUME_THRESHOLD` | 40 | Minimum score to accept document |
| Section matches (3+) | +35 | Strong resume indicator |
| Professional matches (4+) | +25 | Career-related content |
| Email found | +15 | Contact information |
| Phone found | +10 | Contact information |
| Date patterns (2+) | +15 | Work history dates |
| Non-resume indicator | -20 | Penalty per indicator |

---

## Benefits

1. **Prevents garbage data** - Only valid resumes enter the database
2. **Saves processing time** - No LLM calls for non-resumes
3. **User feedback** - Clear error messages explaining why document was rejected
4. **Configurable** - Threshold and weights can be adjusted
5. **Confidence scoring** - Allows downstream decisions based on confidence
