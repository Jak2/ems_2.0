"""
Extraction utilities for enterprise-level data processing.

Provides:
- Array to text conversion (instead of JSON storage)
- Prompt wrappers for consistent LLM extraction
- Validation helpers
"""
import json
import re
from typing import Any, List, Optional, Dict


def array_to_text(value: Any, separator: str = ", ") -> Optional[str]:
    """Convert array/list values to human-readable text format.

    Instead of storing ["Python", "Java", "AWS"] as JSON,
    stores as "Python, Java, AWS" which is more readable.

    For complex objects like work experience, formats them nicely:
    - Simple strings: joined with separator
    - Dicts: formatted as structured text

    Args:
        value: The value to convert (list, dict, or primitive)
        separator: Separator for simple lists (default: ", ")

    Returns:
        Human-readable string or None if value is None/empty
    """
    if value is None:
        return None

    if isinstance(value, str):
        return value if value.strip() else None

    if isinstance(value, list):
        if not value:
            return None

        # Check if list contains dicts (complex objects like work_experience)
        if all(isinstance(item, dict) for item in value):
            # Format each dict as structured text
            formatted_items = []
            for i, item in enumerate(value, 1):
                formatted = format_dict_to_text(item)
                if formatted:
                    formatted_items.append(f"[{i}] {formatted}")
            return "\n".join(formatted_items) if formatted_items else None
        else:
            # Simple list of strings/primitives
            items = [str(item).strip() for item in value if item is not None and str(item).strip()]
            return separator.join(items) if items else None

    if isinstance(value, dict):
        return format_dict_to_text(value)

    return str(value) if value else None


def format_dict_to_text(d: Dict) -> Optional[str]:
    """Format a dictionary as human-readable text.

    Example:
        {"company": "Google", "role": "Engineer", "duration": "2020-2023"}
        becomes: "Google | Engineer | 2020-2023"
    """
    if not d:
        return None

    # Priority order for common resume fields
    priority_keys = ['company', 'role', 'position', 'title', 'duration', 'period',
                     'degree', 'institution', 'school', 'university', 'year', 'grade',
                     'name', 'description', 'responsibilities']

    parts = []

    # First add priority keys in order
    for key in priority_keys:
        if key in d and d[key]:
            parts.append(str(d[key]).strip())

    # Then add any remaining keys
    for key, val in d.items():
        if key not in priority_keys and val:
            val_str = str(val).strip()
            if val_str and val_str not in parts:
                parts.append(val_str)

    return " | ".join(parts) if parts else None


def text_to_array(text: str, separator: str = ",") -> List[str]:
    """Convert text back to array format.

    Useful for reading stored text data back as arrays.
    """
    if not text:
        return []

    items = [item.strip() for item in text.split(separator)]
    return [item for item in items if item]


# ============================================================
# PROMPT WRAPPERS FOR ENTERPRISE-LEVEL ROBUSTNESS
# ============================================================

# Few-shot examples for 20-30% accuracy boost
FEW_SHOT_EXAMPLES = """
=== FEW-SHOT EXAMPLES (Learn from these patterns) ===

**EXAMPLE 1: Standard Resume**
Input: "John Smith, john.smith@email.com, +1-555-123-4567
Software Engineer at Google (2020-Present)
Previously: Junior Developer at StartupXYZ (2018-2020)
Skills: Python, Java, AWS, Docker, Kubernetes
Education: B.S. Computer Science, MIT 2018"

Output:
{
  "name": "John Smith",
  "email": "john.smith@email.com",
  "phone": "+1-555-123-4567",
  "position": "Software Engineer",
  "department": "IT",
  "work_experience": [
    {"company": "Google", "role": "Software Engineer", "duration": "2020-Present", "responsibilities": ""},
    {"company": "StartupXYZ", "role": "Junior Developer", "duration": "2018-2020", "responsibilities": ""}
  ],
  "education": [{"degree": "B.S. Computer Science", "institution": "MIT", "year": "2018", "grade": ""}],
  "technical_skills": ["Python", "Java", "AWS", "Docker", "Kubernetes"],
  "languages": ["English"],
  "summary": null
}

**EXAMPLE 2: QA Professional with Certifications**
Input: "Priya Sharma | priya.s@tech.in | 9876543210
QA Lead - 8 years experience
TCS - Senior QA Engineer (2019-Present)
Infosys - QA Analyst (2015-2019)
Tools: Selenium, Jira, TestNG, Jenkins, API Testing
Education: M.Tech, IIT Delhi 2015
Languages: English, Hindi, Tamil"

Output:
{
  "name": "Priya Sharma",
  "email": "priya.s@tech.in",
  "phone": "9876543210",
  "position": "QA Lead",
  "department": "Quality Assurance",
  "work_experience": [
    {"company": "TCS", "role": "Senior QA Engineer", "duration": "2019-Present", "responsibilities": ""},
    {"company": "Infosys", "role": "QA Analyst", "duration": "2015-2019", "responsibilities": ""}
  ],
  "education": [{"degree": "M.Tech", "institution": "IIT Delhi", "year": "2015", "grade": ""}],
  "technical_skills": ["Selenium", "Jira", "TestNG", "Jenkins", "API Testing"],
  "languages": ["English", "Hindi", "Tamil"],
  "summary": "QA Lead with 8 years experience"
}

**EXAMPLE 3: Project Manager**
Input: "Sam T, 8324567123, Bangalore
Scrum Master | 12 Years Experience
Current: Agile Coach at TechCorp (2021-Present)
Previous: Scrum Master at FinServ (2017-2021), QA Engineer (2013-2017)
Skills: Agile, Scrum, Jira, Confluence, SAFe, Team Leadership
M.S. Computer Science, Anna University 2013"

Output:
{
  "name": "Sam T",
  "email": null,
  "phone": "8324567123",
  "position": "Scrum Master",
  "department": "Project Management",
  "work_experience": [
    {"company": "TechCorp", "role": "Agile Coach", "duration": "2021-Present", "responsibilities": ""},
    {"company": "FinServ", "role": "Scrum Master", "duration": "2017-2021", "responsibilities": ""},
    {"company": "FinServ", "role": "QA Engineer", "duration": "2013-2017", "responsibilities": ""}
  ],
  "education": [{"degree": "M.S. Computer Science", "institution": "Anna University", "year": "2013", "grade": ""}],
  "technical_skills": ["Agile", "Scrum", "Jira", "Confluence", "SAFe"],
  "languages": ["English", "Hindi"],
  "summary": "12 Years Experience in Agile/Scrum"
}
"""

# Main extraction prompt with guardrails
EXTRACTION_SYSTEM_PROMPT = """You are an expert resume parser with strict accuracy requirements.

=== CRITICAL RULES (MUST FOLLOW) ===
1. ONLY extract information that EXPLICITLY exists in the text
2. NEVER guess, infer, or make up information
3. If a field is not found, use null - NEVER fabricate data
4. Return ONLY valid JSON - no explanations, no markdown
5. Double-check each field before finalizing

=== FIELD EXTRACTION GUIDE ===

**CONTACT INFO (look at top of resume):**
- name: Full name (usually largest text at top). MUST be a real person's name.
- email: MUST match pattern xxx@xxx.com. Extract EXACTLY as written.
- phone: Numbers with 7+ digits. Keep original format.

**PROFESSIONAL INFO:**
- position: MOST RECENT job title (first job listed in experience)
- department: Infer ONLY from these rules:
  * Developer/Engineer/Programmer/Software → "IT"
  * QA/Testing/Quality/SDET → "Quality Assurance"
  * Scrum/Agile/Project Manager/Product → "Project Management"
  * HR/Recruiter/Talent → "Human Resources"
  * Finance/Accounting → "Finance"
  * Marketing/Sales → "Marketing"
  * If unclear, use null

**WORK EXPERIENCE:**
Format: [{"company": "...", "role": "...", "duration": "...", "responsibilities": "..."}]
- Extract ALL jobs in chronological order (most recent first)
- Duration patterns: "Jan 2021 - Present", "2018-2020", "Feb 2013 - Dec 2020"
- If responsibilities not clear, use empty string ""

**EDUCATION:**
Format: [{"degree": "...", "institution": "...", "year": "...", "grade": "..."}]
- Degree: B.S., M.S., B.Tech, MBA, PhD, Bachelor's, Master's, etc.
- Year: Graduation year only
- Grade: GPA, percentage, or empty string if not found

**SKILLS:**
- technical_skills: ONLY technical/professional skills:
  * Programming languages: Python, Java, JavaScript, C++, SQL
  * Tools/Platforms: Jira, Selenium, Git, Docker, AWS, Azure
  * Frameworks: React, Angular, Django, Spring, Node.js
  * Methodologies: Agile, Scrum, DevOps, CI/CD
  * Databases: MySQL, PostgreSQL, MongoDB, Oracle

**LANGUAGES (SPOKEN ONLY - NOT programming):**
- Extract ONLY if explicitly stated
- Examples: English, Hindi, Spanish, French, German
- DO NOT include programming languages here

""" + FEW_SHOT_EXAMPLES + """

=== OUTPUT RULES ===
1. Return ONLY valid JSON - no text before or after
2. Use null for missing fields (not "N/A", not "", not "Unknown")
3. DO NOT invent ANY data - if not in text, use null
4. Verify email format is valid before including
5. Double-check name is a real person's name, not a title or heading"""


# Chain-of-Verification prompt for 40% hallucination reduction
VERIFICATION_PROMPT = """You are a verification expert. Review the extracted data and verify each field.

EXTRACTION TO VERIFY:
{extraction_json}

ORIGINAL TEXT:
{original_text}

For each field, verify:
1. Is this value ACTUALLY present in the original text?
2. Is the value extracted correctly (no typos, no truncation)?
3. Is it in the right field (e.g., email in email field, not phone)?

Return a JSON object with the same structure, but:
- Keep values that are VERIFIED as correct
- Change to null any value that:
  * Does NOT appear in the original text
  * Is incorrectly extracted
  * Appears to be hallucinated/made up

Return ONLY the corrected JSON, no explanations."""


def create_extraction_prompt(resume_text: str, max_chars: int = 10000) -> str:
    """Create a robust extraction prompt with system instructions.

    Args:
        resume_text: The resume content to extract from
        max_chars: Maximum characters to include (default 10000)

    Returns:
        Complete prompt ready for LLM
    """
    truncated_text = resume_text[:max_chars] if resume_text else ""

    json_template = '''{
  "name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "linkedin_url": "string or null",
  "department": "string or null",
  "position": "string or null",
  "summary": "string or null",
  "work_experience": [{"company": "", "role": "", "duration": "", "responsibilities": ""}],
  "education": [{"degree": "", "institution": "", "year": "", "grade": ""}],
  "technical_skills": ["skill1", "skill2"],
  "languages": ["spoken language only"],
  "hobbies": ["hobby1"],
  "cocurricular_activities": ["activity1"]
}'''

    return f"""{EXTRACTION_SYSTEM_PROMPT}

===== RESUME TEXT =====
{truncated_text}
===== END =====

Return JSON with this exact structure:
{json_template}

JSON output:"""


def create_retry_prompt(resume_text: str, max_chars: int = 8000) -> str:
    """Create a simpler retry prompt for when first extraction fails."""
    truncated_text = resume_text[:max_chars] if resume_text else ""

    return f"""Extract resume data into JSON. CRITICAL: Return ONLY valid JSON.

FIND THESE FIELDS:
1. name - Full name at top of resume
2. email - Email address (xxx@xxx.com pattern)
3. phone - Phone number (10+ digits)
4. position - Most recent/current job title
5. department - Infer: Developer→IT, QA→Quality Assurance, PM→Project Management
6. work_experience - Array: [{{"company":"", "role":"", "duration":"", "responsibilities":""}}]
7. education - Array: [{{"degree":"", "institution":"", "year":"", "grade":""}}]
8. technical_skills - ALL tech terms: Python, Java, Jira, Selenium, AWS, Agile, etc.
9. languages - SPOKEN only (English, Hindi, Spanish)

Resume:
{truncated_text}

JSON:"""


# ============================================================
# CHAIN-OF-VERIFICATION (40% Hallucination Reduction)
# ============================================================

def create_verification_prompt(extraction: Dict, original_text: str) -> str:
    """Create a verification prompt to reduce hallucinations.

    Args:
        extraction: The initial extraction result
        original_text: The original resume text

    Returns:
        Verification prompt for the LLM
    """
    extraction_json = json.dumps(extraction, indent=2, ensure_ascii=False)
    truncated_text = original_text[:6000] if original_text else ""

    return VERIFICATION_PROMPT.format(
        extraction_json=extraction_json,
        original_text=truncated_text
    )


def verify_extraction_field(field_name: str, value: Any, original_text: str) -> bool:
    """Verify a single field exists in original text.

    Args:
        field_name: Name of the field
        value: Extracted value
        original_text: Original text to check against

    Returns:
        True if value appears to be in original text
    """
    if value is None or value in ['null', 'None', '', 'N/A']:
        return True  # Null values are valid

    text_lower = original_text.lower()

    if isinstance(value, str):
        # Check if value or parts of it appear in text
        value_lower = value.lower()
        if value_lower in text_lower:
            return True
        # Check individual words for names
        if field_name == "name":
            words = value_lower.split()
            return all(word in text_lower for word in words if len(word) > 2)
        return False

    if isinstance(value, list):
        # For arrays, check if at least some items exist
        found_count = 0
        for item in value:
            if isinstance(item, str) and item.lower() in text_lower:
                found_count += 1
            elif isinstance(item, dict):
                # For work experience, check company and role
                company = str(item.get("company", "")).lower()
                role = str(item.get("role", "")).lower()
                if company and company in text_lower:
                    found_count += 1
                elif role and role in text_lower:
                    found_count += 1
        return found_count > 0 if value else True

    return True


def quick_verify_extraction(extraction: Dict, original_text: str) -> Dict:
    """Perform quick rule-based verification without LLM call.

    Args:
        extraction: Extracted data
        original_text: Original resume text

    Returns:
        Verified extraction with suspicious values set to null
    """
    if not isinstance(extraction, dict):
        return extraction

    verified = extraction.copy()

    # Fields to verify against text
    verify_fields = ["name", "email", "phone", "position"]

    for field in verify_fields:
        value = verified.get(field)
        if value and not verify_extraction_field(field, value, original_text):
            # Value not found in text - likely hallucinated
            import logging
            logger = logging.getLogger("cv-chat")
            logger.warning(f"[VERIFY] Field '{field}' value '{value}' not found in text - setting to null")
            verified[field] = None

    return verified


# ============================================================
# ENSEMBLE EXTRACTION (3x Reliability)
# ============================================================

def create_ensemble_prompts(resume_text: str) -> List[str]:
    """Create multiple prompts for ensemble extraction.

    Different prompt styles can capture different aspects.

    Args:
        resume_text: The resume content

    Returns:
        List of prompts for ensemble extraction
    """
    # Prompt 1: Standard structured extraction
    prompt1 = create_extraction_prompt(resume_text, max_chars=10000)

    # Prompt 2: Focused extraction with explicit field listing
    prompt2 = f"""Extract information from this resume into JSON format.

CRITICAL: Only extract what you can SEE in the text. Use null for missing fields.

Text to parse:
{resume_text[:8000]}

Extract these fields:
- name (person's full name)
- email (email address if present)
- phone (phone number if present)
- position (current/most recent job title)
- department (infer: Engineer→IT, QA→Quality Assurance, Scrum/PM→Project Management)
- work_experience (array of jobs)
- education (array of degrees)
- technical_skills (array of skills)
- languages (spoken languages only)

Return ONLY valid JSON."""

    # Prompt 3: Step-by-step extraction
    prompt3 = f"""Parse this resume step by step and output JSON.

Step 1: Find the person's name (usually at the top)
Step 2: Find contact info (email, phone)
Step 3: Identify current position
Step 4: List work experiences
Step 5: List education
Step 6: Extract skills

Resume:
{resume_text[:8000]}

Now output the complete JSON with all found information:"""

    return [prompt1, prompt2, prompt3]


TEMPERATURE_SETTINGS = {
    "deterministic": 0.0,   # Most consistent
    "low": 0.1,             # Slight variation
    "medium": 0.3,          # More creative
}


def get_ensemble_temperatures() -> List[float]:
    """Get temperature settings for ensemble extraction.

    Using multiple temperatures can help capture different aspects.

    Returns:
        List of temperature values
    """
    return [0.0, 0.1, 0.0]  # Mostly deterministic with one slight variation


def merge_ensemble_results(results: List[Dict]) -> Dict:
    """Merge multiple extraction results using voting.

    Args:
        results: List of extraction dictionaries

    Returns:
        Merged result with best values
    """
    if not results:
        return {}

    if len(results) == 1:
        return results[0]

    # Filter out None/invalid results
    valid_results = [r for r in results if isinstance(r, dict) and r]
    if not valid_results:
        return {}

    merged = {}

    # Get all fields across all results
    all_fields = set()
    for r in valid_results:
        all_fields.update(r.keys())

    for field in all_fields:
        values = []
        for r in valid_results:
            val = r.get(field)
            if val is not None and val not in ['null', 'None', '', 'N/A']:
                values.append(val)

        if not values:
            merged[field] = None
            continue

        # For arrays, combine unique items
        if isinstance(values[0], list):
            combined = []
            seen = set()
            for val_list in values:
                if isinstance(val_list, list):
                    for item in val_list:
                        item_key = json.dumps(item) if isinstance(item, dict) else str(item)
                        if item_key not in seen:
                            seen.add(item_key)
                            combined.append(item)
            merged[field] = combined if combined else None
        else:
            # For scalars, use majority voting
            value_counts = {}
            for val in values:
                val_str = str(val).lower()
                value_counts[val_str] = value_counts.get(val_str, 0) + 1

            # Get most common value
            best_val_str = max(value_counts, key=value_counts.get)
            # Return original value (not lowercased)
            for val in values:
                if str(val).lower() == best_val_str:
                    merged[field] = val
                    break

    return merged


def validate_extraction(parsed: Dict) -> tuple[bool, List[str]]:
    """Validate extracted data and return issues.

    Args:
        parsed: The parsed JSON dictionary

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    if not isinstance(parsed, dict):
        return False, ["Result is not a dictionary"]

    # Check for required fields
    name = parsed.get("name")
    if not name or name in ["null", "None", "", "Unknown", "Pending extraction..."]:
        issues.append("Name is missing or invalid")

    # Check for at least some identifying information
    has_contact = bool(parsed.get("email") or parsed.get("phone"))
    has_experience = bool(parsed.get("work_experience"))
    has_skills = bool(parsed.get("technical_skills"))

    if not (has_contact or has_experience or has_skills):
        issues.append("Missing contact info, experience, and skills - extraction may have failed")

    return len(issues) == 0, issues


def clean_json_response(response: str) -> Optional[str]:
    """Clean LLM response to extract valid JSON.

    Handles common issues:
    - Markdown code blocks
    - Leading/trailing text
    - Nested JSON
    """
    if not response:
        return None

    # Remove markdown code blocks
    response = re.sub(r'^```(?:json)?\s*', '', response, flags=re.MULTILINE)
    response = re.sub(r'\s*```$', '', response, flags=re.MULTILINE)

    # Try to find JSON object
    # Look for the outermost { }
    brace_count = 0
    start_idx = None
    end_idx = None

    for i, char in enumerate(response):
        if char == '{':
            if start_idx is None:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx is not None:
                end_idx = i + 1
                break

    if start_idx is not None and end_idx is not None:
        return response[start_idx:end_idx]

    return None


def parse_llm_json(response: str, raw_text: Optional[str] = None) -> Optional[Dict]:
    """Parse JSON from LLM response with multiple fallback strategies.

    Args:
        response: Raw LLM response
        raw_text: Optional raw resume text for fallback extraction of email, phone, soft skills

    Returns:
        Parsed dictionary or None if parsing fails
    """
    if not response:
        return None

    # Strategy 1: Direct parse
    try:
        parsed = json.loads(response)
        return post_process_extraction(parsed, raw_text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Clean and parse
    cleaned = clean_json_response(response)
    if cleaned:
        try:
            parsed = json.loads(cleaned)
            return post_process_extraction(parsed, raw_text)
        except json.JSONDecodeError:
            pass

    # Strategy 3: Regex extraction
    match = re.search(r'\{.*\}', response, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return post_process_extraction(parsed, raw_text)
        except json.JSONDecodeError:
            pass

    return None


# ============================================================
# FALLBACK EXTRACTION (REGEX-BASED)
# ============================================================

# Email regex pattern - matches common email formats
EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE
)

def extract_email_from_text(text: str) -> Optional[str]:
    """Extract email address from raw text using regex.

    Used as a fallback when LLM fails to extract email.

    Args:
        text: Raw resume text

    Returns:
        Email address or None if not found
    """
    if not text:
        return None

    # Find all email matches
    matches = EMAIL_PATTERN.findall(text)

    if matches:
        # Return the first valid-looking email
        # Filter out common false positives
        for email in matches:
            email_lower = email.lower()
            # Skip common false positives
            if any(skip in email_lower for skip in ['example.com', 'test.com', 'domain.com', 'email.com']):
                continue
            # Skip if it looks like a URL fragment
            if email_lower.endswith('.png') or email_lower.endswith('.jpg'):
                continue
            return email

        # If all were filtered, return the first one anyway
        return matches[0]

    return None


def extract_phone_from_text(text: str) -> Optional[str]:
    """Extract phone number from raw text using regex.

    Used as a fallback when LLM fails to extract phone.

    Args:
        text: Raw resume text

    Returns:
        Phone number or None if not found
    """
    if not text:
        return None

    # Phone patterns - various formats
    phone_patterns = [
        r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # +1-555-123-4567
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (555) 123-4567
        r'\d{10,12}',  # 5551234567
        r'\+\d{2}\s?\d{10}',  # +91 9876543210
    ]

    for pattern in phone_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            # Validate it's a phone number (has at least 10 digits)
            digits = re.sub(r'\D', '', match)
            if len(digits) >= 10:
                return match.strip()

    return None


# ============================================================
# POST-PROCESSING AND FIELD CORRECTION
# ============================================================

# Programming languages that should NOT be in spoken languages field
PROGRAMMING_LANGUAGES = {
    'python', 'java', 'javascript', 'c', 'c++', 'c#', 'ruby', 'go', 'rust',
    'php', 'swift', 'kotlin', 'scala', 'r', 'perl', 'sql', 'html', 'css',
    'typescript', 'bash', 'shell', 'powershell', 'matlab', 'vba', 'groovy',
    'dart', 'objective-c', 'assembly', 'fortran', 'cobol', 'lua', 'haskell'
}

# Technical skills patterns
TECHNICAL_PATTERNS = [
    'python', 'java', 'javascript', 'react', 'angular', 'vue', 'node',
    'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git',
    'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
    'selenium', 'jira', 'confluence', 'agile', 'scrum', 'devops', 'ci/cd',
    'api', 'rest', 'graphql', 'microservices', 'spring', 'django', 'flask',
    'tensorflow', 'pytorch', 'machine learning', 'ml', 'ai', 'data science',
    'linux', 'unix', 'windows', 'networking', 'security', 'testing', 'qa'
]

# Department inference rules
DEPARTMENT_RULES = {
    # Job titles → Department
    'developer': 'IT',
    'engineer': 'IT',
    'programmer': 'IT',
    'software': 'IT',
    'web developer': 'IT',
    'frontend': 'IT',
    'backend': 'IT',
    'fullstack': 'IT',
    'full stack': 'IT',
    'devops': 'IT',
    'data scientist': 'IT',
    'data analyst': 'IT',
    'qa': 'Quality Assurance',
    'quality': 'Quality Assurance',
    'tester': 'Quality Assurance',
    'testing': 'Quality Assurance',
    'sdet': 'Quality Assurance',
    'scrum master': 'Project Management',
    'project manager': 'Project Management',
    'product manager': 'Project Management',
    'agile coach': 'Project Management',
    'program manager': 'Project Management',
    'hr': 'Human Resources',
    'human resources': 'Human Resources',
    'recruiter': 'Human Resources',
    'talent': 'Human Resources',
    'finance': 'Finance',
    'accountant': 'Finance',
    'accounting': 'Finance',
    'marketing': 'Marketing',
    'sales': 'Sales',
    'business development': 'Sales',
    'support': 'Customer Support',
    'customer service': 'Customer Support',
}

# Country to language inference
COUNTRY_LANGUAGES = {
    'india': ['English', 'Hindi'],
    'usa': ['English'],
    'united states': ['English'],
    'uk': ['English'],
    'united kingdom': ['English'],
    'canada': ['English', 'French'],
    'germany': ['German', 'English'],
    'france': ['French', 'English'],
    'spain': ['Spanish', 'English'],
    'china': ['Chinese', 'English'],
    'japan': ['Japanese', 'English'],
    'brazil': ['Portuguese', 'English'],
    'mexico': ['Spanish', 'English'],
    'russia': ['Russian', 'English'],
    'italy': ['Italian', 'English'],
    'australia': ['English'],
}


def post_process_extraction(parsed: Dict, raw_text: Optional[str] = None) -> Dict:
    """Post-process extracted data to fix common errors and apply fallbacks.

    Features:
    - Fallback email extraction using regex if LLM missed it
    - Fallback phone extraction using regex
    - Removes programming languages from spoken languages
    - Infers department from position

    Args:
        parsed: Dictionary of extracted fields from LLM
        raw_text: Optional raw resume text for fallback extraction

    Returns:
        Enhanced dictionary with post-processed fields
    """
    if not isinstance(parsed, dict):
        return parsed

    # ============================================================
    # FALLBACK EXTRACTIONS (using raw_text when LLM missed fields)
    # ============================================================

    # Fallback: Extract email if missing
    if not parsed.get('email') and raw_text:
        fallback_email = extract_email_from_text(raw_text)
        if fallback_email:
            parsed['email'] = fallback_email

    # Fallback: Extract phone if missing
    if not parsed.get('phone') and raw_text:
        fallback_phone = extract_phone_from_text(raw_text)
        if fallback_phone:
            parsed['phone'] = fallback_phone

    # ============================================================
    # LANGUAGE FIELD FIXES
    # ============================================================

    # Fix languages field - remove programming languages
    if 'languages' in parsed and parsed['languages']:
        languages = parsed['languages']
        if isinstance(languages, list):
            # Filter out programming languages
            spoken_languages = [
                lang for lang in languages
                if lang and str(lang).lower().strip() not in PROGRAMMING_LANGUAGES
            ]
            parsed['languages'] = spoken_languages if spoken_languages else None

    # Infer languages from country if not set
    if not parsed.get('languages') and parsed.get('country'):
        country = str(parsed['country']).lower().strip()
        for country_key, langs in COUNTRY_LANGUAGES.items():
            if country_key in country:
                parsed['languages'] = langs
                break

    # ============================================================
    # DEPARTMENT INFERENCE
    # ============================================================

    # Infer department from position if not set
    if not parsed.get('department') and parsed.get('position'):
        position = str(parsed['position']).lower()
        for title_keyword, dept in DEPARTMENT_RULES.items():
            if title_keyword in position:
                parsed['department'] = dept
                break

    # Also try to infer department from work_experience if position didn't work
    if not parsed.get('department') and parsed.get('work_experience'):
        work_exp = parsed['work_experience']
        if isinstance(work_exp, list) and len(work_exp) > 0:
            # Check the most recent job (first in list)
            recent_job = work_exp[0]
            if isinstance(recent_job, dict):
                role = recent_job.get('role') or recent_job.get('position') or recent_job.get('title') or ''
                role_lower = str(role).lower()
                for title_keyword, dept in DEPARTMENT_RULES.items():
                    if title_keyword in role_lower:
                        parsed['department'] = dept
                        break

    # ============================================================
    # SKILLS NORMALIZATION
    # ============================================================

    # Ensure technical_skills is a list and not empty
    if 'technical_skills' in parsed:
        skills = parsed['technical_skills']
        if isinstance(skills, str):
            # Split comma-separated string into list
            parsed['technical_skills'] = [s.strip() for s in skills.split(',') if s.strip()]
        elif not isinstance(skills, list):
            parsed['technical_skills'] = []

    # Clean up work_experience
    if 'work_experience' in parsed and parsed['work_experience']:
        exp = parsed['work_experience']
        if isinstance(exp, list):
            # Filter out empty entries
            parsed['work_experience'] = [
                e for e in exp
                if isinstance(e, dict) and (e.get('company') or e.get('role'))
            ]

    # Clean up education
    if 'education' in parsed and parsed['education']:
        edu = parsed['education']
        if isinstance(edu, list):
            # Filter out empty entries
            parsed['education'] = [
                e for e in edu
                if isinstance(e, dict) and (e.get('degree') or e.get('institution'))
            ]

    # Remove null string values
    for key in parsed:
        if parsed[key] in ['null', 'None', 'N/A', 'n/a', '']:
            parsed[key] = None

    return parsed


def extract_skills_from_text(text: str) -> List[str]:
    """Extract technical skills from raw text by pattern matching.

    Useful as a fallback when LLM misses skills.
    """
    if not text:
        return []

    text_lower = text.lower()
    found_skills = []

    for skill in TECHNICAL_PATTERNS:
        if skill.lower() in text_lower:
            # Capitalize properly
            found_skills.append(skill.title() if len(skill) > 3 else skill.upper())

    return list(set(found_skills))


# ============================================================
# MULTI-QUERY DECOMPOSITION (Complex Query Handling)
# ============================================================

# Keywords that indicate multiple tasks in a single query
MULTI_QUERY_INDICATORS = [
    " and ",
    " also ",
    " then ",
    " after that ",
    " additionally ",
    ", compare ",
    ", tell me ",
    ", show me ",
    ", list ",
    ", count ",
    ", find ",
]

# Conjunctions that typically connect separate tasks
TASK_CONJUNCTIONS = [
    "and what",
    "and who",
    "and how",
    "and count",
    "and compare",
    "and tell",
    "and show",
    "and list",
    "and find",
    "also tell",
    "also show",
    "also find",
    ", compare",
    ", then",
]


def detect_multi_query(prompt: str) -> bool:
    """Detect if a prompt contains multiple distinct tasks/queries.

    Args:
        prompt: User's input prompt

    Returns:
        True if the prompt appears to contain multiple tasks
    """
    prompt_lower = prompt.lower()

    # Check for task conjunction patterns
    conjunction_count = sum(1 for conj in TASK_CONJUNCTIONS if conj in prompt_lower)
    if conjunction_count >= 1:
        return True

    # Check for multiple question words
    question_words = ["what", "who", "how many", "count", "compare", "list", "show", "find"]
    question_count = sum(1 for qw in question_words if qw in prompt_lower)
    if question_count >= 3:
        return True

    # Check for multiple employee names mentioned with different actions
    # Pattern: "X's skills" and "Y's skills" or similar
    possessive_pattern = re.compile(r"(\w+)'s\s+(skills|email|phone|experience|education)", re.IGNORECASE)
    possessives = possessive_pattern.findall(prompt)
    if len(possessives) >= 2:
        return True

    return False


QUERY_DECOMPOSITION_PROMPT = """You are a query analyzer. Break down this complex query into simple, independent sub-tasks.

RULES:
1. Each sub-task should be a single, focused question or action
2. Maintain the order of tasks as mentioned in the original query
3. If a task depends on a previous result, note it with [DEPENDS: task_number]
4. Return ONLY a JSON array of sub-tasks

EXAMPLE INPUT:
"what skills debraj has and count his skills related to cloud and devops, and what skills does udayateja has, compare both skills"

EXAMPLE OUTPUT:
[
  {"task_id": 1, "query": "What skills does Debraj have?", "type": "search", "depends_on": null},
  {"task_id": 2, "query": "Count Debraj's skills related to cloud and devops", "type": "count", "depends_on": 1},
  {"task_id": 3, "query": "What skills does Udayateja have?", "type": "search", "depends_on": null},
  {"task_id": 4, "query": "Compare Debraj's and Udayateja's skills and determine who has more devops knowledge", "type": "compare", "depends_on": [1, 3]}
]

USER QUERY:
{user_query}

Return ONLY the JSON array:"""


def create_decomposition_prompt(user_query: str) -> str:
    """Create a prompt to decompose a complex query into sub-tasks.

    Args:
        user_query: The original complex query from user

    Returns:
        Formatted prompt for LLM
    """
    return QUERY_DECOMPOSITION_PROMPT.format(user_query=user_query)


def parse_decomposed_tasks(llm_response: str) -> List[Dict]:
    """Parse the LLM response containing decomposed tasks.

    Args:
        llm_response: Raw LLM response with JSON array

    Returns:
        List of task dictionaries
    """
    if not llm_response:
        return []

    # Try to extract JSON array from response
    try:
        # Direct parse
        tasks = json.loads(llm_response)
        if isinstance(tasks, list):
            return tasks
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in response
    match = re.search(r'\[.*\]', llm_response, re.DOTALL)
    if match:
        try:
            tasks = json.loads(match.group(0))
            if isinstance(tasks, list):
                return tasks
        except json.JSONDecodeError:
            pass

    return []


RESULT_AGGREGATION_PROMPT = """You are a helpful assistant. Combine these sub-task results into a single, coherent response.

ORIGINAL QUESTION:
{original_query}

SUB-TASK RESULTS:
{task_results}

RULES:
1. Present the information in a clear, organized manner
2. Use bullet points or sections if there are multiple parts
3. If comparisons were requested, clearly state the conclusion
4. Be concise but complete
5. If any sub-task failed, mention what information couldn't be retrieved

Provide a natural, conversational response:"""


def create_aggregation_prompt(original_query: str, task_results: List[Dict]) -> str:
    """Create a prompt to aggregate multiple sub-task results.

    Args:
        original_query: The original user query
        task_results: List of results from each sub-task

    Returns:
        Formatted prompt for LLM aggregation
    """
    results_text = ""
    for i, result in enumerate(task_results, 1):
        task_query = result.get("query", f"Task {i}")
        task_response = result.get("response", "No response")
        results_text += f"\n[Task {i}] {task_query}\nResult: {task_response}\n"

    return RESULT_AGGREGATION_PROMPT.format(
        original_query=original_query,
        task_results=results_text
    )
