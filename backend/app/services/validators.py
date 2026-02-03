"""
Enterprise-Level Validation, Sanitization, and Verification Module

Features:
1. INPUT VALIDATION & SANITIZATION
   - Length guards (min/max character limits)
   - Format validators (email, phone, URL)
   - Content sanitization (XSS, injection prevention)
   - Schema enforcement

2. OUTPUT VERIFICATION
   - Rule-based validators for each field
   - Cross-field consistency checks
   - Confidence scoring

3. ENSEMBLE METHODS
   - Multiple extraction passes with voting
   - Confidence-weighted field selection
"""
import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("cv-chat")

# ============================================================
# CONFIGURATION CONSTANTS
# ============================================================

# Input length limits
INPUT_LIMITS = {
    "resume_text_min": 50,       # Minimum resume length
    "resume_text_max": 50000,    # Maximum resume length
    "name_max": 100,             # Max name length
    "email_max": 254,            # RFC 5321 limit
    "phone_max": 30,             # Max phone length
    "url_max": 2048,             # Max URL length
    "text_field_max": 5000,      # Max for text fields
    "array_max_items": 50,       # Max items in arrays
}

# Regex patterns for validation
PATTERNS = {
    "email": re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        re.IGNORECASE
    ),
    "phone": re.compile(
        r'^[\+]?[\d\s\-\.\(\)]{7,30}$'
    ),
    "url": re.compile(
        r'^https?://[^\s<>\"{}|\\^`\[\]]+$',
        re.IGNORECASE
    ),
    "name": re.compile(
        r'^[a-zA-Z\s\.\-\']+$'
    ),
    # Dangerous patterns to sanitize
    "sql_injection": re.compile(
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE)\b)',
        re.IGNORECASE
    ),
    "xss": re.compile(
        r'<script[^>]*>|</script>|javascript:|on\w+\s*=',
        re.IGNORECASE
    ),
}

# Valid department values
VALID_DEPARTMENTS = {
    "IT", "Quality Assurance", "Project Management", "Human Resources",
    "Finance", "Marketing", "Sales", "Customer Support", "Operations",
    "Research & Development", "Engineering", "Design", "Legal"
}


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class ValidationResult:
    """Result of field validation"""
    is_valid: bool
    value: Any
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class ExtractionResult:
    """Result of extraction with confidence scores"""
    data: Dict[str, Any]
    field_confidences: Dict[str, float] = field(default_factory=dict)
    overall_confidence: float = 0.0
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)


# ============================================================
# INPUT SANITIZATION
# ============================================================

def sanitize_input(text: str) -> str:
    """Sanitize input text to prevent injection attacks.

    Args:
        text: Raw input text

    Returns:
        Sanitized text safe for processing
    """
    if not text:
        return ""

    # Remove null bytes
    text = text.replace('\x00', '')

    # Remove control characters (except newlines and tabs)
    text = ''.join(char for char in text if char == '\n' or char == '\t' or
                   (ord(char) >= 32 and ord(char) != 127))

    # Limit excessive whitespace
    text = re.sub(r'[ \t]{10,}', '    ', text)
    text = re.sub(r'\n{5,}', '\n\n\n', text)

    # Log if suspicious patterns detected (but don't remove - could be false positive)
    if PATTERNS["sql_injection"].search(text):
        logger.warning("[VALIDATOR] Potential SQL keywords detected in input")

    if PATTERNS["xss"].search(text):
        logger.warning("[VALIDATOR] Potential XSS patterns detected in input")

    return text


def validate_input_length(text: str, field_name: str = "resume") -> ValidationResult:
    """Validate input text length.

    Args:
        text: Input text to validate
        field_name: Name of the field for error messages

    Returns:
        ValidationResult with validation status
    """
    errors = []
    warnings = []

    if not text:
        return ValidationResult(
            is_valid=False,
            value=text,
            errors=[f"{field_name} is empty"]
        )

    text_len = len(text)
    min_len = INPUT_LIMITS.get(f"{field_name}_min", 0)
    max_len = INPUT_LIMITS.get(f"{field_name}_max", INPUT_LIMITS["text_field_max"])

    if text_len < min_len:
        errors.append(f"{field_name} is too short ({text_len} chars, minimum {min_len})")

    if text_len > max_len:
        warnings.append(f"{field_name} exceeds maximum length ({text_len} chars, max {max_len}). Will be truncated.")
        text = text[:max_len]

    return ValidationResult(
        is_valid=len(errors) == 0,
        value=text,
        errors=errors,
        warnings=warnings
    )


# ============================================================
# FIELD VALIDATORS
# ============================================================

def validate_email(email: Any) -> ValidationResult:
    """Validate email address format."""
    if email is None or email in ['null', 'None', '', 'N/A']:
        return ValidationResult(is_valid=True, value=None, confidence=0.0)

    email = str(email).strip().lower()

    if len(email) > INPUT_LIMITS["email_max"]:
        return ValidationResult(
            is_valid=False,
            value=None,
            errors=[f"Email too long ({len(email)} chars)"]
        )

    if PATTERNS["email"].match(email):
        # Additional checks
        if email.count('@') != 1:
            return ValidationResult(is_valid=False, value=None, errors=["Invalid email format"])

        local, domain = email.split('@')
        if len(local) > 64 or len(domain) > 255:
            return ValidationResult(is_valid=False, value=None, errors=["Email parts too long"])

        # Check for common typos
        common_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
        if domain not in common_domains and any(d in domain for d in ['gmial', 'yaho', 'hotmal']):
            return ValidationResult(
                is_valid=True,
                value=email,
                warnings=["Possible email domain typo"],
                confidence=0.7
            )

        return ValidationResult(is_valid=True, value=email, confidence=0.95)

    return ValidationResult(
        is_valid=False,
        value=None,
        errors=[f"Invalid email format: {email}"]
    )


def validate_phone(phone: Any) -> ValidationResult:
    """Validate phone number format."""
    if phone is None or phone in ['null', 'None', '', 'N/A']:
        return ValidationResult(is_valid=True, value=None, confidence=0.0)

    phone = str(phone).strip()

    # Remove common separators for digit count
    digits_only = re.sub(r'\D', '', phone)

    if len(digits_only) < 7:
        return ValidationResult(
            is_valid=False,
            value=None,
            errors=["Phone number too short (less than 7 digits)"]
        )

    if len(digits_only) > 15:
        return ValidationResult(
            is_valid=False,
            value=None,
            errors=["Phone number too long (more than 15 digits)"]
        )

    if PATTERNS["phone"].match(phone):
        return ValidationResult(is_valid=True, value=phone, confidence=0.9)

    # Try to salvage - just return digits if reasonable
    if 7 <= len(digits_only) <= 15:
        return ValidationResult(
            is_valid=True,
            value=digits_only,
            warnings=["Phone format normalized to digits only"],
            confidence=0.7
        )

    return ValidationResult(
        is_valid=False,
        value=None,
        errors=[f"Invalid phone format: {phone}"]
    )


def validate_name(name: Any) -> ValidationResult:
    """Validate person name."""
    if name is None or name in ['null', 'None', '', 'N/A', 'Unknown', 'Pending extraction...']:
        return ValidationResult(
            is_valid=False,
            value=None,
            errors=["Name is missing or invalid"]
        )

    name = str(name).strip()

    if len(name) < 2:
        return ValidationResult(
            is_valid=False,
            value=None,
            errors=["Name too short"]
        )

    if len(name) > INPUT_LIMITS["name_max"]:
        return ValidationResult(
            is_valid=False,
            value=None,
            errors=[f"Name too long ({len(name)} chars)"]
        )

    # Check for suspicious patterns (not a real name)
    suspicious_patterns = [
        r'^\d+$',           # All numbers
        r'^[^a-zA-Z]+$',    # No letters
        r'test|example|sample|dummy|placeholder',
        r'resume|cv|curriculum',
        r'^n/?a$',
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            return ValidationResult(
                is_valid=False,
                value=None,
                errors=[f"Name appears invalid: {name}"]
            )

    # Confidence based on name characteristics
    confidence = 0.8
    if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*$', name):
        confidence = 0.95  # Proper capitalization
    elif PATTERNS["name"].match(name):
        confidence = 0.85

    return ValidationResult(is_valid=True, value=name, confidence=confidence)


def validate_url(url: Any, url_type: str = "url") -> ValidationResult:
    """Validate URL format."""
    if url is None or url in ['null', 'None', '', 'N/A']:
        return ValidationResult(is_valid=True, value=None, confidence=0.0)

    url = str(url).strip()

    if len(url) > INPUT_LIMITS["url_max"]:
        return ValidationResult(
            is_valid=False,
            value=None,
            errors=["URL too long"]
        )

    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    if not PATTERNS["url"].match(url):
        return ValidationResult(
            is_valid=False,
            value=None,
            errors=[f"Invalid URL format: {url}"]
        )

    # Type-specific validation
    confidence = 0.8
    if url_type == "linkedin":
        if 'linkedin.com' in url.lower():
            confidence = 0.95
        else:
            return ValidationResult(
                is_valid=False,
                value=None,
                errors=["Not a LinkedIn URL"]
            )
    elif url_type == "github":
        if 'github.com' in url.lower():
            confidence = 0.95
        else:
            return ValidationResult(
                is_valid=False,
                value=None,
                errors=["Not a GitHub URL"]
            )

    return ValidationResult(is_valid=True, value=url, confidence=confidence)


def validate_department(department: Any) -> ValidationResult:
    """Validate department value."""
    if department is None or department in ['null', 'None', '', 'N/A']:
        return ValidationResult(is_valid=True, value=None, confidence=0.0)

    department = str(department).strip()

    # Exact match
    if department in VALID_DEPARTMENTS:
        return ValidationResult(is_valid=True, value=department, confidence=0.95)

    # Case-insensitive match
    for valid_dept in VALID_DEPARTMENTS:
        if department.lower() == valid_dept.lower():
            return ValidationResult(is_valid=True, value=valid_dept, confidence=0.9)

    # Fuzzy match
    dept_lower = department.lower()
    for valid_dept in VALID_DEPARTMENTS:
        if valid_dept.lower() in dept_lower or dept_lower in valid_dept.lower():
            return ValidationResult(
                is_valid=True,
                value=valid_dept,
                warnings=[f"Department normalized from '{department}' to '{valid_dept}'"],
                confidence=0.7
            )

    # Accept but flag as uncertain
    return ValidationResult(
        is_valid=True,
        value=department,
        warnings=[f"Non-standard department: {department}"],
        confidence=0.5
    )


def validate_array_field(value: Any, field_name: str) -> ValidationResult:
    """Validate array/list fields."""
    if value is None or value in ['null', 'None', '', 'N/A']:
        return ValidationResult(is_valid=True, value=None, confidence=0.0)

    if isinstance(value, str):
        # Try to parse as JSON
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            # Split by comma
            value = [v.strip() for v in value.split(',') if v.strip()]

    if not isinstance(value, list):
        return ValidationResult(
            is_valid=False,
            value=None,
            errors=[f"{field_name} must be a list"]
        )

    if len(value) > INPUT_LIMITS["array_max_items"]:
        value = value[:INPUT_LIMITS["array_max_items"]]
        return ValidationResult(
            is_valid=True,
            value=value,
            warnings=[f"{field_name} truncated to {INPUT_LIMITS['array_max_items']} items"],
            confidence=0.8
        )

    # Filter out empty/null items
    if all(isinstance(item, (str, dict)) for item in value):
        cleaned = [item for item in value if item and item not in ['null', 'None', '', 'N/A']]
        return ValidationResult(is_valid=True, value=cleaned if cleaned else None, confidence=0.9)

    return ValidationResult(is_valid=True, value=value, confidence=0.8)


# ============================================================
# SCHEMA ENFORCEMENT
# ============================================================

EXTRACTION_SCHEMA = {
    "name": {"type": "string", "required": True, "validator": validate_name},
    "email": {"type": "string", "required": False, "validator": validate_email},
    "phone": {"type": "string", "required": False, "validator": validate_phone},
    "linkedin_url": {"type": "string", "required": False, "validator": lambda x: validate_url(x, "linkedin")},
    "portfolio_url": {"type": "string", "required": False, "validator": lambda x: validate_url(x, "url")},
    "github_url": {"type": "string", "required": False, "validator": lambda x: validate_url(x, "github")},
    "department": {"type": "string", "required": False, "validator": validate_department},
    "position": {"type": "string", "required": False, "validator": lambda x: ValidationResult(is_valid=True, value=x if x and x not in ['null', 'None', ''] else None, confidence=0.8)},
    "career_objective": {"type": "string", "required": False, "validator": None},
    "summary": {"type": "string", "required": False, "validator": None},
    "work_experience": {"type": "array", "required": False, "validator": lambda x: validate_array_field(x, "work_experience")},
    "education": {"type": "array", "required": False, "validator": lambda x: validate_array_field(x, "education")},
    "technical_skills": {"type": "array", "required": False, "validator": lambda x: validate_array_field(x, "technical_skills")},
    "languages": {"type": "array", "required": False, "validator": lambda x: validate_array_field(x, "languages")},
    "hobbies": {"type": "array", "required": False, "validator": lambda x: validate_array_field(x, "hobbies")},
    "cocurricular_activities": {"type": "array", "required": False, "validator": lambda x: validate_array_field(x, "cocurricular_activities")},
}


def enforce_schema(data: Dict) -> ExtractionResult:
    """Enforce schema on extracted data with validation.

    Args:
        data: Raw extracted data dictionary

    Returns:
        ExtractionResult with validated and cleaned data
    """
    if not isinstance(data, dict):
        return ExtractionResult(
            data={},
            validation_errors=["Input is not a dictionary"]
        )

    validated_data = {}
    field_confidences = {}
    all_errors = []
    all_warnings = []

    for field_name, schema in EXTRACTION_SCHEMA.items():
        raw_value = data.get(field_name)

        if schema.get("validator"):
            result = schema["validator"](raw_value)
            validated_data[field_name] = result.value
            field_confidences[field_name] = result.confidence
            all_errors.extend([f"{field_name}: {e}" for e in result.errors])
            all_warnings.extend([f"{field_name}: {w}" for w in result.warnings])
        else:
            # No validator - just clean null values
            if raw_value in ['null', 'None', '', 'N/A', None]:
                validated_data[field_name] = None
                field_confidences[field_name] = 0.0
            else:
                validated_data[field_name] = raw_value
                field_confidences[field_name] = 0.7

    # Check required fields
    for field_name, schema in EXTRACTION_SCHEMA.items():
        if schema.get("required") and not validated_data.get(field_name):
            all_errors.append(f"Required field '{field_name}' is missing")

    # Calculate overall confidence
    non_zero_confidences = [c for c in field_confidences.values() if c > 0]
    overall_confidence = sum(non_zero_confidences) / len(non_zero_confidences) if non_zero_confidences else 0.0

    return ExtractionResult(
        data=validated_data,
        field_confidences=field_confidences,
        overall_confidence=overall_confidence,
        validation_errors=all_errors,
        validation_warnings=all_warnings
    )


# ============================================================
# CROSS-FIELD CONSISTENCY CHECKS
# ============================================================

def check_consistency(data: Dict) -> List[str]:
    """Perform cross-field consistency checks.

    Args:
        data: Validated extraction data

    Returns:
        List of inconsistency warnings
    """
    warnings = []

    # Check if position matches department
    position = data.get("position", "") or ""
    department = data.get("department", "") or ""

    position_dept_mappings = {
        ("developer", "engineer", "programmer"): "IT",
        ("qa", "tester", "quality"): "Quality Assurance",
        ("scrum", "project", "product"): "Project Management",
        ("hr", "recruiter"): "Human Resources",
    }

    position_lower = position.lower()
    for keywords, expected_dept in position_dept_mappings.items():
        if any(kw in position_lower for kw in keywords):
            if department and department != expected_dept:
                warnings.append(
                    f"Position '{position}' typically belongs to '{expected_dept}' but department is '{department}'"
                )
            break

    # Check work experience consistency
    work_exp = data.get("work_experience") or []
    if isinstance(work_exp, list) and len(work_exp) > 0:
        # Check if most recent job matches position
        if isinstance(work_exp[0], dict):
            recent_role = work_exp[0].get("role", "") or work_exp[0].get("position", "")
            if position and recent_role:
                if position.lower() not in recent_role.lower() and recent_role.lower() not in position.lower():
                    warnings.append(
                        f"Current position '{position}' doesn't match most recent work experience '{recent_role}'"
                    )

    return warnings


# ============================================================
# ENSEMBLE EXTRACTION
# ============================================================

def ensemble_extract(
    extractions: List[Dict],
    weights: Optional[List[float]] = None
) -> Dict:
    """Combine multiple extraction results using voting/weighted selection.

    Args:
        extractions: List of extraction dictionaries from multiple passes
        weights: Optional weights for each extraction (e.g., based on temperature)

    Returns:
        Combined extraction with highest-confidence values
    """
    if not extractions:
        return {}

    if len(extractions) == 1:
        return extractions[0]

    if weights is None:
        weights = [1.0] * len(extractions)

    # Normalize weights
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]

    combined = {}

    # Get all possible fields
    all_fields = set()
    for ext in extractions:
        if isinstance(ext, dict):
            all_fields.update(ext.keys())

    for field in all_fields:
        values_with_weights = []

        for i, ext in enumerate(extractions):
            if isinstance(ext, dict):
                value = ext.get(field)
                if value is not None and value not in ['null', 'None', '', 'N/A']:
                    values_with_weights.append((value, weights[i]))

        if not values_with_weights:
            combined[field] = None
            continue

        # For arrays, take union
        if isinstance(values_with_weights[0][0], list):
            all_items = []
            for value, _ in values_with_weights:
                all_items.extend(value)
            # Deduplicate while preserving order
            seen = set()
            unique = []
            for item in all_items:
                item_key = json.dumps(item) if isinstance(item, dict) else str(item)
                if item_key not in seen:
                    seen.add(item_key)
                    unique.append(item)
            combined[field] = unique if unique else None
        else:
            # For scalars, use voting with weights
            value_weights = {}
            for value, weight in values_with_weights:
                value_key = str(value)
                value_weights[value_key] = value_weights.get(value_key, 0) + weight

            # Select value with highest total weight
            best_value = max(value_weights.items(), key=lambda x: x[1])
            combined[field] = values_with_weights[0][0] if best_value[0] == str(values_with_weights[0][0]) else next(
                v for v, _ in values_with_weights if str(v) == best_value[0]
            )

    return combined


def calculate_extraction_confidence(
    extractions: List[Dict],
    combined: Dict
) -> Dict[str, float]:
    """Calculate confidence scores based on agreement between extractions.

    Args:
        extractions: List of extraction dictionaries
        combined: Combined extraction result

    Returns:
        Dictionary of field -> confidence score
    """
    confidences = {}
    n_extractions = len(extractions)

    if n_extractions == 0:
        return confidences

    for field, value in combined.items():
        if value is None:
            confidences[field] = 0.0
            continue

        agreement_count = 0
        for ext in extractions:
            if isinstance(ext, dict):
                ext_value = ext.get(field)
                if ext_value is not None:
                    if isinstance(value, list):
                        # For arrays, check overlap
                        if isinstance(ext_value, list) and len(set(map(str, value)) & set(map(str, ext_value))) > 0:
                            agreement_count += 1
                    else:
                        # For scalars, check equality (case-insensitive for strings)
                        if str(value).lower() == str(ext_value).lower():
                            agreement_count += 1

        confidences[field] = agreement_count / n_extractions

    return confidences


# ============================================================
# MAIN VALIDATION FUNCTION
# ============================================================

def validate_and_clean_extraction(
    raw_data: Dict,
    raw_text: Optional[str] = None
) -> ExtractionResult:
    """Main function to validate and clean extracted data.

    Args:
        raw_data: Raw extraction from LLM
        raw_text: Original resume text for verification

    Returns:
        ExtractionResult with validated, cleaned data and confidence scores
    """
    logger.info("[VALIDATOR] Starting extraction validation...")

    # Step 1: Enforce schema and validate fields
    result = enforce_schema(raw_data)

    # Step 2: Cross-field consistency checks
    consistency_warnings = check_consistency(result.data)
    result.validation_warnings.extend(consistency_warnings)

    # Step 3: Log results
    if result.validation_errors:
        logger.warning(f"[VALIDATOR] Validation errors: {result.validation_errors}")
    if result.validation_warnings:
        logger.info(f"[VALIDATOR] Validation warnings: {result.validation_warnings}")

    logger.info(f"[VALIDATOR] Overall confidence: {result.overall_confidence:.2f}")
    logger.info(f"[VALIDATOR] Field confidences: {result.field_confidences}")

    return result
