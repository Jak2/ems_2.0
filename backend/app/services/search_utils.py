"""
Search and matching utilities for Employee Management System.

Handles:
- Skill synonym mapping (JavaScript = JS, React, Node.js, etc.)
- Experience calculation from work history
- Date parsing and normalization
- Negative search handling
- City/location fuzzy matching
- Title seniority mapping
- Date range overlap detection
"""

import re
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger("cv-chat")

# ============================================================
# SKILL SYNONYM MAPPING (Edge Case #13)
# "javascript developers" should find JS, React, Node.js, TypeScript
# ============================================================

SKILL_SYNONYMS = {
    # JavaScript ecosystem
    "javascript": ["js", "javascript", "ecmascript", "es6", "es2015", "vanilla js"],
    "react": ["reactjs", "react.js", "react js", "react native"],
    "node": ["nodejs", "node.js", "node js"],
    "typescript": ["ts", "typescript"],
    "angular": ["angularjs", "angular.js", "angular 2+"],
    "vue": ["vuejs", "vue.js", "vue js"],

    # Python ecosystem
    "python": ["python", "python3", "python2", "py", "cpython", "pypy"],
    "django": ["django", "django rest framework", "drf"],
    "flask": ["flask", "flask-restful"],
    "pandas": ["pandas", "numpy", "scipy"],

    # Java ecosystem
    "java": ["java", "java8", "java11", "java17", "j2ee", "jee"],
    "spring": ["spring", "spring boot", "springboot", "spring mvc", "spring framework"],
    "kotlin": ["kotlin", "kt"],

    # Cloud & DevOps
    "aws": ["aws", "amazon web services", "ec2", "s3", "lambda", "cloudformation"],
    "azure": ["azure", "microsoft azure", "azure devops"],
    "gcp": ["gcp", "google cloud", "google cloud platform", "bigquery"],
    "docker": ["docker", "dockerfile", "docker-compose", "containerization"],
    "kubernetes": ["kubernetes", "k8s", "kubectl", "helm"],
    "devops": ["devops", "ci/cd", "cicd", "jenkins", "gitlab ci", "github actions"],

    # Databases
    "sql": ["sql", "mysql", "postgresql", "postgres", "mssql", "sql server", "oracle", "sqlite"],
    "nosql": ["nosql", "mongodb", "mongo", "cassandra", "dynamodb", "couchdb", "redis"],
    "mongodb": ["mongodb", "mongo", "mongoose"],

    # Testing
    "testing": ["testing", "qa", "quality assurance", "test automation"],
    "selenium": ["selenium", "selenium webdriver", "selenide"],
    "junit": ["junit", "testng", "mockito"],
    "pytest": ["pytest", "unittest", "nose"],

    # Agile/PM
    "agile": ["agile", "scrum", "kanban", "safe", "lean"],
    "scrum": ["scrum", "scrum master", "sprint"],
    "jira": ["jira", "atlassian", "confluence"],

    # Data Science/ML
    "machine learning": ["machine learning", "ml", "deep learning", "dl", "ai", "artificial intelligence"],
    "tensorflow": ["tensorflow", "tf", "keras"],
    "pytorch": ["pytorch", "torch"],

    # Mobile
    "android": ["android", "kotlin", "android studio"],
    "ios": ["ios", "swift", "objective-c", "xcode"],
    "mobile": ["mobile", "react native", "flutter", "xamarin"],
}

# Reverse mapping for quick lookup
SKILL_TO_CANONICAL = {}
for canonical, variants in SKILL_SYNONYMS.items():
    for variant in variants:
        SKILL_TO_CANONICAL[variant.lower()] = canonical


def expand_skill_search(skill: str) -> List[str]:
    """Expand a skill search term to include all synonyms.

    Args:
        skill: The skill to search for (e.g., "javascript")

    Returns:
        List of all related skill terms to search for
    """
    skill_lower = skill.lower().strip()

    # Check if this skill has synonyms
    if skill_lower in SKILL_SYNONYMS:
        return SKILL_SYNONYMS[skill_lower]

    # Check if this is a variant of a canonical skill
    if skill_lower in SKILL_TO_CANONICAL:
        canonical = SKILL_TO_CANONICAL[skill_lower]
        return SKILL_SYNONYMS.get(canonical, [skill_lower])

    # No synonyms found, return original
    return [skill_lower]


def skills_match(search_skill: str, employee_skills: str) -> Tuple[bool, str]:
    """Check if an employee has a skill, considering synonyms.

    Args:
        search_skill: The skill being searched for
        employee_skills: The employee's skills (comma-separated string)

    Returns:
        Tuple of (matches: bool, matched_skill: str)
    """
    if not employee_skills:
        return (False, "")

    skills_lower = employee_skills.lower()
    expanded = expand_skill_search(search_skill)

    for variant in expanded:
        if variant in skills_lower:
            return (True, variant)

    return (False, "")


# ============================================================
# EXPERIENCE CALCULATION (Edge Case #1, #2)
# Server-side calculation for years of experience
# ============================================================

def parse_date_flexible(date_str: str) -> Optional[date]:
    """Parse a date string in various formats.

    Handles:
    - ISO 8601: "2020-01-15"
    - US format: "01/15/2020", "Jan 15, 2020"
    - EU format: "15/01/2020", "15 Jan 2020"
    - Year only: "2020"
    - Month-Year: "Jan 2020", "2020-01"
    - Present/Current: Returns today's date

    Args:
        date_str: Date string to parse

    Returns:
        date object or None if parsing fails
    """
    if not date_str:
        return None

    date_str = str(date_str).strip().lower()

    # Handle "present", "current", "now"
    if date_str in ["present", "current", "now", "today", "ongoing", "till date"]:
        return date.today()

    # Handle year only
    if re.match(r'^\d{4}$', date_str):
        return date(int(date_str), 1, 1)

    # Handle month-year formats
    month_year_match = re.match(r'^(\w+)\s*[-/]?\s*(\d{4})$', date_str)
    if month_year_match:
        try:
            parsed = date_parser.parse(date_str)
            return parsed.date()
        except:
            pass

    # Try dateutil parser
    try:
        parsed = date_parser.parse(date_str, dayfirst=True)  # Prefer EU format
        return parsed.date()
    except:
        pass

    # Try with US format
    try:
        parsed = date_parser.parse(date_str, dayfirst=False)
        return parsed.date()
    except:
        pass

    logger.warning(f"[DATE] Could not parse date: '{date_str}'")
    return None


def calculate_experience_years(work_experience: List[Dict]) -> float:
    """Calculate total years of experience from work history.

    Args:
        work_experience: List of work experience dicts with 'duration' field

    Returns:
        Total years of experience (float)
    """
    if not work_experience or not isinstance(work_experience, list):
        return 0.0

    total_months = 0

    for job in work_experience:
        if not isinstance(job, dict):
            continue

        duration = job.get('duration', '')
        if not duration:
            continue

        # Parse duration string (e.g., "Jan 2020 - Present", "2018-2020")
        months = parse_duration_to_months(str(duration))
        total_months += months

    return round(total_months / 12, 1)


def parse_duration_to_months(duration: str) -> int:
    """Parse a duration string to months.

    Args:
        duration: Duration string like "Jan 2020 - Present" or "2018-2020"

    Returns:
        Number of months
    """
    if not duration:
        return 0

    duration = duration.strip()

    # Try to split by common separators
    separators = [' - ', ' to ', ' – ', '-', '–', '→']
    start_str = None
    end_str = None

    for sep in separators:
        if sep in duration:
            parts = duration.split(sep)
            if len(parts) >= 2:
                start_str = parts[0].strip()
                end_str = parts[-1].strip()
                break

    if not start_str:
        # Try to extract years from format like "2018-2020"
        years = re.findall(r'\d{4}', duration)
        if len(years) >= 2:
            start_str = years[0]
            end_str = years[-1]
        elif len(years) == 1:
            start_str = years[0]
            end_str = "present"

    start_date = parse_date_flexible(start_str)
    end_date = parse_date_flexible(end_str)

    if not start_date:
        return 0

    if not end_date:
        end_date = date.today()

    # Calculate months between dates
    delta = relativedelta(end_date, start_date)
    months = delta.years * 12 + delta.months

    return max(0, months)


def check_date_range_overlap(emp_start: date, emp_end: date,
                             search_start: date, search_end: date) -> bool:
    """Check if two date ranges overlap.

    Args:
        emp_start, emp_end: Employee's employment period
        search_start, search_end: Search period

    Returns:
        True if ranges overlap
    """
    # Two ranges overlap if one starts before the other ends
    return emp_start <= search_end and emp_end >= search_start


def find_employees_by_experience(db, min_years: float = None, max_years: float = None):
    """Find employees by years of experience.

    Args:
        db: Database session
        min_years: Minimum years of experience
        max_years: Maximum years of experience

    Returns:
        List of (employee, experience_years) tuples
    """
    from app.db import models
    import json

    all_employees = db.query(models.Employee).all()
    results = []

    for emp in all_employees:
        # Parse work experience JSON
        work_exp = []
        if emp.work_experience:
            try:
                work_exp = json.loads(emp.work_experience) if isinstance(emp.work_experience, str) else emp.work_experience
            except:
                pass

        years = calculate_experience_years(work_exp)

        # Apply filters
        if min_years is not None and years < min_years:
            continue
        if max_years is not None and years > max_years:
            continue

        results.append((emp, years))

    # Sort by experience descending
    results.sort(key=lambda x: x[1], reverse=True)
    return results


# ============================================================
# CITY/LOCATION FUZZY MATCHING (Edge Case #15)
# "engineers near Bangalore" should find Bangalore, Bengaluru, BLR
# ============================================================

CITY_SYNONYMS = {
    "bangalore": ["bangalore", "bengaluru", "blr", "bangalore urban", "bangalore rural"],
    "mumbai": ["mumbai", "bombay", "bom"],
    "delhi": ["delhi", "new delhi", "ncr", "del", "noida", "gurgaon", "gurugram"],
    "chennai": ["chennai", "madras", "maa"],
    "hyderabad": ["hyderabad", "hyd", "secunderabad", "cyberabad"],
    "kolkata": ["kolkata", "calcutta", "cal"],
    "pune": ["pune", "poona"],
    "ahmedabad": ["ahmedabad", "amdavad"],

    # US Cities
    "new york": ["new york", "nyc", "ny", "manhattan", "brooklyn"],
    "san francisco": ["san francisco", "sf", "bay area", "silicon valley"],
    "los angeles": ["los angeles", "la", "hollywood"],
    "seattle": ["seattle", "sea"],
    "austin": ["austin", "atx"],
    "boston": ["boston", "bos"],
    "chicago": ["chicago", "chi"],

    # UK Cities
    "london": ["london", "ldn"],
    "manchester": ["manchester", "man"],

    # Remote
    "remote": ["remote", "work from home", "wfh", "anywhere", "distributed"],
}

CITY_TO_CANONICAL = {}
for canonical, variants in CITY_SYNONYMS.items():
    for variant in variants:
        CITY_TO_CANONICAL[variant.lower()] = canonical


def expand_city_search(city: str) -> List[str]:
    """Expand a city search term to include all variations."""
    city_lower = city.lower().strip()

    if city_lower in CITY_SYNONYMS:
        return CITY_SYNONYMS[city_lower]

    if city_lower in CITY_TO_CANONICAL:
        canonical = CITY_TO_CANONICAL[city_lower]
        return CITY_SYNONYMS.get(canonical, [city_lower])

    return [city_lower]


# ============================================================
# TITLE SENIORITY MAPPING (Edge Case #9)
# Rank titles by seniority level
# ============================================================

TITLE_SENIORITY = {
    # Engineering ladder (1-10 scale)
    "intern": 1,
    "trainee": 1,
    "junior": 2,
    "associate": 3,
    "mid": 4,
    "senior": 5,
    "lead": 6,
    "staff": 7,
    "principal": 8,
    "distinguished": 9,
    "fellow": 10,

    # Management ladder
    "team lead": 6,
    "manager": 6,
    "senior manager": 7,
    "director": 8,
    "senior director": 9,
    "vp": 9,
    "vice president": 9,
    "svp": 10,
    "evp": 10,
    "c-level": 10,
    "cto": 10,
    "ceo": 10,
    "cfo": 10,
    "coo": 10,

    # QA specific
    "qa analyst": 3,
    "qa engineer": 4,
    "senior qa": 5,
    "qa lead": 6,
    "qa manager": 7,

    # PM specific
    "product analyst": 3,
    "product manager": 5,
    "senior product manager": 6,
    "director of product": 8,
    "vp of product": 9,
}


def get_title_seniority(title: str) -> int:
    """Get seniority level for a job title (1-10 scale).

    Args:
        title: Job title string

    Returns:
        Seniority level (1=entry, 10=executive)
    """
    if not title:
        return 0

    title_lower = title.lower().strip()

    # Direct match
    if title_lower in TITLE_SENIORITY:
        return TITLE_SENIORITY[title_lower]

    # Check for keywords
    best_score = 0
    for keyword, score in TITLE_SENIORITY.items():
        if keyword in title_lower:
            best_score = max(best_score, score)

    # Default based on common patterns
    if best_score == 0:
        if "engineer" in title_lower or "developer" in title_lower:
            best_score = 4  # Mid-level default
        elif "manager" in title_lower:
            best_score = 6
        elif "analyst" in title_lower:
            best_score = 3

    return best_score


def compare_titles(title1: str, title2: str) -> int:
    """Compare two titles by seniority.

    Returns:
        -1 if title1 < title2, 0 if equal, 1 if title1 > title2
    """
    s1 = get_title_seniority(title1)
    s2 = get_title_seniority(title2)

    if s1 < s2:
        return -1
    elif s1 > s2:
        return 1
    return 0


# ============================================================
# NEGATIVE SEARCH HANDLING (Edge Case #14)
# "engineers except managers" should exclude manager-engineers
# ============================================================

def parse_negative_search(query: str) -> Tuple[List[str], List[str]]:
    """Parse a search query for include and exclude terms.

    Args:
        query: Search query like "engineers except managers"

    Returns:
        Tuple of (include_terms, exclude_terms)
    """
    query_lower = query.lower()

    # Keywords that indicate exclusion
    exclude_keywords = ["except", "but not", "excluding", "without", "not including", "minus", "-"]

    include_terms = []
    exclude_terms = []

    for keyword in exclude_keywords:
        if keyword in query_lower:
            parts = query_lower.split(keyword)
            if len(parts) >= 2:
                include_terms = [p.strip() for p in parts[0].split() if p.strip()]
                exclude_terms = [p.strip() for p in parts[1].split() if p.strip()]
                break

    if not include_terms:
        include_terms = [t.strip() for t in query_lower.split() if t.strip()]

    return (include_terms, exclude_terms)


def apply_negative_filter(employees: List, include_terms: List[str],
                          exclude_terms: List[str], field: str = 'position') -> List:
    """Filter employees by include/exclude terms.

    Args:
        employees: List of employee objects
        include_terms: Terms to include
        exclude_terms: Terms to exclude
        field: Field to check (position, department, etc.)

    Returns:
        Filtered list of employees
    """
    results = []

    for emp in employees:
        field_value = getattr(emp, field, '') or ''
        field_lower = field_value.lower()

        # Check include terms (any match)
        include_match = not include_terms or any(
            term in field_lower for term in include_terms
        )

        # Check exclude terms (none should match)
        exclude_match = any(
            term in field_lower for term in exclude_terms
        )

        if include_match and not exclude_match:
            results.append(emp)

    return results


# ============================================================
# DATE RANGE QUERY HELPERS (Edge Case #2)
# Find employees working during a specific period
# ============================================================

def find_employees_in_date_range(db, start_year: int, end_year: int = None):
    """Find employees who worked during a specific date range.

    Args:
        db: Database session
        start_year: Start year of the range
        end_year: End year of the range (defaults to start_year)

    Returns:
        List of (employee, overlap_info) tuples
    """
    from app.db import models
    import json

    if end_year is None:
        end_year = start_year

    search_start = date(start_year, 1, 1)
    search_end = date(end_year, 12, 31)

    all_employees = db.query(models.Employee).all()
    results = []

    for emp in all_employees:
        # Parse work experience
        work_exp = []
        if emp.work_experience:
            try:
                work_exp = json.loads(emp.work_experience) if isinstance(emp.work_experience, str) else emp.work_experience
            except:
                pass

        overlap_jobs = []
        for job in work_exp:
            if not isinstance(job, dict):
                continue

            duration = job.get('duration', '')
            if not duration:
                continue

            # Parse duration to get start and end dates
            parts = str(duration).split('-')
            if len(parts) < 2:
                parts = str(duration).split(' to ')

            if len(parts) >= 2:
                job_start = parse_date_flexible(parts[0].strip())
                job_end = parse_date_flexible(parts[-1].strip())

                if job_start and job_end:
                    if check_date_range_overlap(job_start, job_end, search_start, search_end):
                        overlap_type = "overlaps"
                        if job_start >= search_start and job_end <= search_end:
                            overlap_type = "contained"
                        elif job_start <= search_start and job_end >= search_end:
                            overlap_type = "contains"

                        overlap_jobs.append({
                            'job': job,
                            'overlap_type': overlap_type,
                            'job_start': job_start,
                            'job_end': job_end
                        })

        if overlap_jobs:
            results.append((emp, overlap_jobs))

    return results


# ============================================================
# EDGE CASE #16: UNICODE/DIACRITICS HANDLING
# José = Jose, Müller = Mueller, Björk = Bjork
# ============================================================

# Unicode to ASCII mapping for common diacritics
UNICODE_TO_ASCII = {
    'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a', 'å': 'a', 'ā': 'a',
    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e', 'ē': 'e',
    'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i', 'ī': 'i',
    'ó': 'o', 'ò': 'o', 'ô': 'o', 'ö': 'o', 'õ': 'o', 'ō': 'o', 'ø': 'o',
    'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u', 'ū': 'u',
    'ñ': 'n', 'ń': 'n',
    'ç': 'c', 'ć': 'c',
    'ß': 'ss',
    'æ': 'ae', 'œ': 'oe',
    'ý': 'y', 'ÿ': 'y',
    'ž': 'z', 'ź': 'z',
    'š': 's', 'ś': 's',
    'ł': 'l',
    'đ': 'd',
}


def normalize_unicode(text: str) -> str:
    """Normalize Unicode characters to ASCII equivalents.

    Handles accented characters common in international names.

    Args:
        text: Text possibly containing Unicode characters

    Returns:
        ASCII-normalized text
    """
    if not text:
        return ""

    result = text.lower()
    for unicode_char, ascii_char in UNICODE_TO_ASCII.items():
        result = result.replace(unicode_char, ascii_char)

    # Also try unicodedata normalization as fallback
    try:
        import unicodedata
        # NFD decomposition + remove combining characters
        normalized = unicodedata.normalize('NFD', result)
        result = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    except Exception:
        pass

    return result


# ============================================================
# EDGE CASE #17: PHONETIC/SOUNDEX MATCHING
# Smith = Smyth, John = Jon, Catherine = Katherine
# ============================================================

def soundex(name: str) -> str:
    """Generate Soundex code for phonetic matching.

    Soundex encodes similar-sounding names to the same code.
    Example: Smith and Smyth both encode to S530

    Args:
        name: Name to encode

    Returns:
        4-character Soundex code
    """
    if not name:
        return ""

    name = normalize_unicode(name.upper().strip())
    if not name:
        return ""

    # Soundex mapping
    soundex_map = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6'
    }

    # Keep first letter
    first_letter = name[0]

    # Encode remaining letters
    encoded = first_letter
    prev_code = soundex_map.get(first_letter, '0')

    for char in name[1:]:
        code = soundex_map.get(char, '0')
        if code != '0' and code != prev_code:
            encoded += code
        prev_code = code

        if len(encoded) >= 4:
            break

    # Pad with zeros to make 4 characters
    encoded = (encoded + '000')[:4]

    return encoded


def names_sound_similar(name1: str, name2: str) -> bool:
    """Check if two names sound similar using Soundex.

    Args:
        name1, name2: Names to compare

    Returns:
        True if names have same Soundex code
    """
    if not name1 or not name2:
        return False

    # Compare each word in multi-word names
    words1 = name1.split()
    words2 = name2.split()

    # If different word count, check if first/last names match
    if len(words1) != len(words2):
        # At least first or last name should match
        if soundex(words1[0]) == soundex(words2[0]):
            return True
        if soundex(words1[-1]) == soundex(words2[-1]):
            return True
        return False

    # Same word count - check if all words match
    matches = sum(1 for w1, w2 in zip(words1, words2) if soundex(w1) == soundex(w2))
    return matches >= len(words1) * 0.5  # At least 50% match


# ============================================================
# EDGE CASE #18: HONORIFICS/TITLE STRIPPING
# Dr. John Smith = John Smith, Mr. = '', Jr. = '', III = ''
# ============================================================

HONORIFICS = {
    # Prefixes
    'mr', 'mr.', 'mrs', 'mrs.', 'ms', 'ms.', 'miss', 'dr', 'dr.',
    'prof', 'prof.', 'professor', 'rev', 'rev.', 'sir', 'madam',
    'hon', 'hon.', 'honorable', 'judge', 'capt', 'capt.', 'captain',
    'col', 'col.', 'colonel', 'gen', 'gen.', 'general', 'lt', 'lt.',
    'sgt', 'sgt.', 'major',

    # Suffixes
    'jr', 'jr.', 'junior', 'sr', 'sr.', 'senior',
    'i', 'ii', 'iii', 'iv', 'v',  # Roman numerals
    'phd', 'ph.d', 'ph.d.', 'md', 'm.d', 'm.d.',
    'esq', 'esq.', 'esquire',
    'mba', 'm.b.a', 'cpa', 'c.p.a',
}


def strip_honorifics(name: str) -> str:
    """Remove honorifics and titles from a name.

    Args:
        name: Full name possibly with honorifics

    Returns:
        Name without honorifics
    """
    if not name:
        return ""

    words = name.split()
    cleaned = []

    for word in words:
        word_lower = word.lower().strip('.,')
        if word_lower not in HONORIFICS:
            cleaned.append(word)

    return ' '.join(cleaned)


# ============================================================
# EDGE CASE #19: ABBREVIATION EXPANSION
# Sr. Engineer = Senior Engineer, Mgr = Manager, Dev = Developer
# ============================================================

TITLE_ABBREVIATIONS = {
    # Seniority
    'sr': 'senior', 'sr.': 'senior',
    'jr': 'junior', 'jr.': 'junior',

    # Roles
    'mgr': 'manager', 'mgr.': 'manager',
    'dir': 'director', 'dir.': 'director',
    'eng': 'engineer', 'eng.': 'engineer',
    'dev': 'developer', 'dev.': 'developer',
    'admin': 'administrator',
    'exec': 'executive', 'exec.': 'executive',
    'vp': 'vice president',
    'svp': 'senior vice president',
    'evp': 'executive vice president',
    'cto': 'chief technology officer',
    'ceo': 'chief executive officer',
    'cfo': 'chief financial officer',
    'coo': 'chief operating officer',
    'cio': 'chief information officer',

    # Technical
    'sw': 'software',
    'hw': 'hardware',
    'qa': 'quality assurance',
    'qe': 'quality engineer',
    'swe': 'software engineer',
    'sde': 'software development engineer',
    'mts': 'member of technical staff',
    'pm': 'product manager',
    'tpm': 'technical program manager',
    'em': 'engineering manager',

    # Departments
    'hr': 'human resources',
    'it': 'information technology',
    'r&d': 'research and development',
    'ops': 'operations',
    'mktg': 'marketing',
    'fin': 'finance',
}


def expand_abbreviations(text: str) -> str:
    """Expand common abbreviations in titles/positions.

    Args:
        text: Text possibly containing abbreviations

    Returns:
        Text with abbreviations expanded
    """
    if not text:
        return ""

    words = text.lower().split()
    expanded = []

    for word in words:
        word_clean = word.strip('.,')
        if word_clean in TITLE_ABBREVIATIONS:
            expanded.append(TITLE_ABBREVIATIONS[word_clean])
        else:
            expanded.append(word)

    return ' '.join(expanded)


def titles_match(search_title: str, db_title: str) -> Tuple[bool, int]:
    """Check if two job titles match, considering abbreviations.

    Args:
        search_title: Title being searched for
        db_title: Title from database

    Returns:
        Tuple of (matches: bool, confidence: 0-100)
    """
    if not search_title or not db_title:
        return (False, 0)

    # Normalize both
    search_norm = expand_abbreviations(search_title.lower())
    db_norm = expand_abbreviations(db_title.lower())

    # Exact match
    if search_norm == db_norm:
        return (True, 100)

    # Contains match
    if search_norm in db_norm or db_norm in search_norm:
        return (True, 80)

    # Word overlap
    search_words = set(search_norm.split())
    db_words = set(db_norm.split())
    overlap = search_words & db_words

    if overlap:
        confidence = int(len(overlap) / max(len(search_words), len(db_words)) * 100)
        return (True, confidence) if confidence >= 40 else (False, confidence)

    return (False, 0)


# ============================================================
# EDGE CASE #20: TEMPORAL REFERENCE HANDLING
# "joined last year", "hired 2 months ago", "started in Q1 2023"
# ============================================================

def parse_temporal_reference(text: str) -> Optional[Tuple[date, date]]:
    """Parse temporal references like 'last year', '2 months ago'.

    Args:
        text: Text containing temporal reference

    Returns:
        Tuple of (start_date, end_date) or None
    """
    text_lower = text.lower()
    today = date.today()

    # Patterns and their date calculations
    if 'last year' in text_lower:
        last_year = today.year - 1
        return (date(last_year, 1, 1), date(last_year, 12, 31))

    if 'this year' in text_lower:
        return (date(today.year, 1, 1), today)

    if 'last month' in text_lower:
        first_of_month = today.replace(day=1)
        last_month_end = first_of_month - relativedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return (last_month_start, last_month_end)

    if 'this month' in text_lower:
        return (today.replace(day=1), today)

    # "X months ago", "X years ago"
    months_ago_match = re.search(r'(\d+)\s*months?\s*ago', text_lower)
    if months_ago_match:
        months = int(months_ago_match.group(1))
        start_date = today - relativedelta(months=months)
        return (start_date, today)

    years_ago_match = re.search(r'(\d+)\s*years?\s*ago', text_lower)
    if years_ago_match:
        years = int(years_ago_match.group(1))
        start_date = today - relativedelta(years=years)
        return (start_date, today)

    # "in Q1/Q2/Q3/Q4 2023"
    quarter_match = re.search(r'q([1-4])\s*(\d{4})', text_lower)
    if quarter_match:
        quarter = int(quarter_match.group(1))
        year = int(quarter_match.group(2))
        quarter_starts = {1: 1, 2: 4, 3: 7, 4: 10}
        quarter_ends = {1: 3, 2: 6, 3: 9, 4: 12}
        start_month = quarter_starts[quarter]
        end_month = quarter_ends[quarter]
        return (date(year, start_month, 1), date(year, end_month, 28))

    # "last week"
    if 'last week' in text_lower:
        start_date = today - relativedelta(weeks=1)
        return (start_date, today)

    # "recently" = last 3 months
    if 'recently' in text_lower or 'recent' in text_lower:
        start_date = today - relativedelta(months=3)
        return (start_date, today)

    return None


# ============================================================
# EDGE CASE #21: NULL/EMPTY FIELD QUERIES
# "employees without email", "missing phone number"
# ============================================================

def parse_null_field_query(query: str) -> Optional[Tuple[str, bool]]:
    """Parse queries about missing/empty fields.

    Args:
        query: Query string like "employees without email"

    Returns:
        Tuple of (field_name, is_null_search) or None
    """
    query_lower = query.lower()

    # Patterns indicating null search
    null_patterns = ['without', 'missing', 'no ', 'empty', 'blank', "don't have", "doesn't have"]
    has_null_pattern = any(p in query_lower for p in null_patterns)

    # Patterns indicating non-null search
    has_patterns = ['with ', 'have ', 'has ']
    has_value_pattern = any(p in query_lower for p in has_patterns)

    # Field mappings
    field_keywords = {
        'email': 'email',
        'phone': 'phone',
        'department': 'department',
        'position': 'position',
        'skills': 'technical_skills',
        'experience': 'work_experience',
        'education': 'education',
        'linkedin': 'linkedin_url',
    }

    # Find which field is being queried
    for keyword, field in field_keywords.items():
        if keyword in query_lower:
            if has_null_pattern:
                return (field, True)  # Looking for NULL
            elif has_value_pattern:
                return (field, False)  # Looking for NOT NULL

    return None


def find_employees_with_null_field(db, field_name: str, is_null: bool = True):
    """Find employees with null or non-null field values.

    Args:
        db: Database session
        field_name: Field to check
        is_null: True to find null values, False to find non-null

    Returns:
        List of matching employees
    """
    from app.db import models

    all_employees = db.query(models.Employee).all()
    results = []

    for emp in all_employees:
        field_value = getattr(emp, field_name, None)

        # Check if field is effectively empty
        is_empty = (
            field_value is None or
            field_value == '' or
            field_value == 'N/A' or
            field_value == 'null' or
            (isinstance(field_value, str) and field_value.strip() == '')
        )

        if is_null and is_empty:
            results.append(emp)
        elif not is_null and not is_empty:
            results.append(emp)

    return results


# ============================================================
# EDGE CASE #22: COMPOUND QUERY PARSING
# "Python AND AWS NOT junior", "senior OR lead engineers"
# ============================================================

def parse_compound_query(query: str) -> Dict[str, Any]:
    """Parse compound queries with AND, OR, NOT operators.

    Args:
        query: Query string like "Python AND AWS NOT junior"

    Returns:
        Dict with 'must_have', 'should_have', 'must_not' lists
    """
    result = {
        'must_have': [],      # AND conditions
        'should_have': [],    # OR conditions
        'must_not': [],       # NOT conditions
    }

    query_lower = query.lower()

    # Extract NOT conditions first
    not_patterns = [
        r'\bnot\s+(\w+)',
        r'\bexcept\s+(\w+)',
        r'\bexcluding\s+(\w+)',
        r'\bwithout\s+(\w+)',
    ]

    for pattern in not_patterns:
        matches = re.findall(pattern, query_lower)
        result['must_not'].extend(matches)
        # Remove from query for further processing
        query_lower = re.sub(pattern, '', query_lower)

    # Check for explicit AND
    if ' and ' in query_lower:
        parts = query_lower.split(' and ')
        for part in parts:
            terms = [t.strip() for t in part.split() if len(t.strip()) > 2]
            result['must_have'].extend(terms)

    # Check for explicit OR
    elif ' or ' in query_lower:
        parts = query_lower.split(' or ')
        for part in parts:
            terms = [t.strip() for t in part.split() if len(t.strip()) > 2]
            result['should_have'].extend(terms)

    # Default: treat space-separated as AND
    else:
        terms = [t.strip() for t in query_lower.split() if len(t.strip()) > 2]
        # Filter out common words
        stopwords = {'the', 'and', 'for', 'with', 'find', 'show', 'list', 'get', 'employees', 'employee'}
        terms = [t for t in terms if t not in stopwords]
        result['must_have'].extend(terms)

    # Deduplicate
    result['must_have'] = list(set(result['must_have']))
    result['should_have'] = list(set(result['should_have']))
    result['must_not'] = list(set(result['must_not']))

    return result


def apply_compound_filter(employees: List, compound_query: Dict[str, Any],
                          search_fields: List[str] = None) -> List:
    """Apply compound query filters to employee list.

    Args:
        employees: List of employee objects
        compound_query: Result from parse_compound_query()
        search_fields: Fields to search in (default: name, position, technical_skills)

    Returns:
        Filtered list of employees
    """
    if not search_fields:
        search_fields = ['name', 'position', 'technical_skills', 'department']

    results = []

    for emp in employees:
        # Combine all searchable text
        search_text = ''
        for field in search_fields:
            value = getattr(emp, field, '') or ''
            search_text += ' ' + value.lower()

        # Check must_have (AND) - all must be present
        if compound_query['must_have']:
            if not all(term in search_text for term in compound_query['must_have']):
                continue

        # Check should_have (OR) - at least one must be present
        if compound_query['should_have']:
            if not any(term in search_text for term in compound_query['should_have']):
                continue

        # Check must_not (NOT) - none should be present
        if compound_query['must_not']:
            if any(term in search_text for term in compound_query['must_not']):
                continue

        results.append(emp)

    return results


# ============================================================
# EDGE CASE #23: NUMERIC RANGE PARSING
# "3-5 years experience", "salary 50k-80k", "age 25-35"
# ============================================================

def parse_numeric_range(text: str) -> Optional[Tuple[float, float, str]]:
    """Parse numeric ranges from text.

    Args:
        text: Text like "3-5 years" or "50k-80k salary"

    Returns:
        Tuple of (min_value, max_value, unit) or None
    """
    text_lower = text.lower()

    # Patterns for ranges
    patterns = [
        # "3-5 years"
        (r'(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*(years?|months?|weeks?)', 'experience'),
        # "5+ years"
        (r'(\d+(?:\.\d+)?)\+\s*(years?|months?)', 'experience_min'),
        # "under 5 years"
        (r'(?:under|less than|below)\s*(\d+(?:\.\d+)?)\s*(years?|months?)', 'experience_max'),
        # "50k-80k"
        (r'(\d+)k\s*[-–to]+\s*(\d+)k', 'salary'),
        # "$50,000-$80,000"
        (r'\$?([\d,]+)\s*[-–to]+\s*\$?([\d,]+)', 'salary'),
    ]

    for pattern, range_type in patterns:
        match = re.search(pattern, text_lower)
        if match:
            groups = match.groups()
            if range_type == 'experience':
                min_val = float(groups[0])
                max_val = float(groups[1])
                unit = groups[2]
                return (min_val, max_val, unit)
            elif range_type == 'experience_min':
                min_val = float(groups[0])
                return (min_val, 100, groups[1])  # 100 as max
            elif range_type == 'experience_max':
                max_val = float(groups[0])
                return (0, max_val, groups[1])
            elif range_type == 'salary':
                min_val = float(groups[0].replace(',', ''))
                max_val = float(groups[1].replace(',', ''))
                if 'k' in text_lower:
                    min_val *= 1000
                    max_val *= 1000
                return (min_val, max_val, 'salary')

    return None
