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
