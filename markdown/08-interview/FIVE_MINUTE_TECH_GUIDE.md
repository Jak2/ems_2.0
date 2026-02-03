# 5-Minute Senior Developer Technology Guide

Master PostgreSQL, MongoDB, Python, FastAPI, and LLM Integration with industry-standard techniques.

**Reading time: 5 minutes | Depth: Senior-level patterns**

---

## Quick Navigation

| Section | Jump To | Time |
|---------|---------|------|
| 1 | [PostgreSQL](#1-postgresql) | 45 sec |
| 2 | [MongoDB](#2-mongodb) | 45 sec |
| 3 | [Python (Senior Patterns)](#3-python-senior-patterns) | 45 sec |
| 4 | [FastAPI](#4-fastapi) | 45 sec |
| 5 | [LLM Fundamentals](#5-llm-fundamentals) | 45 sec |
| 6 | [LLM Integration Patterns](#6-llm-integration-patterns) | 45 sec |
| 7 | [MongoDB + FastAPI](#7-mongodb--fastapi-integration) | 30 sec |
| 8 | [PostgreSQL + FastAPI](#8-postgresql--fastapi-integration) | 30 sec |

---

## 1. PostgreSQL

### Core Concepts (What Interviewers Ask)

| Concept | One-Line Explanation |
|---------|---------------------|
| **ACID** | Atomicity, Consistency, Isolation, Durability - transactions are reliable |
| **Index** | B-tree structure for O(log n) lookups instead of O(n) table scans |
| **Primary Key** | Unique identifier, auto-creates clustered index |
| **Foreign Key** | Referential integrity - links tables, prevents orphan records |
| **Transaction** | Group of operations that succeed or fail together |
| **Isolation Levels** | READ UNCOMMITTED → READ COMMITTED → REPEATABLE READ → SERIALIZABLE |

### Essential Commands

```sql
-- Create table with constraints
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    employee_id VARCHAR(6) UNIQUE NOT NULL,
    name VARCHAR(256) NOT NULL,
    email VARCHAR(256),
    skills TEXT[],  -- Array type
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@')
);

-- Index for frequent queries (CRITICAL for performance)
CREATE INDEX idx_employees_name ON employees(name);
CREATE INDEX idx_employees_skills ON employees USING GIN(skills);  -- Array index

-- Upsert (Insert or Update) - Senior pattern
INSERT INTO employees (employee_id, name, email)
VALUES ('000001', 'John', 'john@test.com')
ON CONFLICT (employee_id)
DO UPDATE SET name = EXCLUDED.name, email = EXCLUDED.email;

-- Window functions (Senior SQL)
SELECT name, department, salary,
       RANK() OVER (PARTITION BY department ORDER BY salary DESC) as dept_rank
FROM employees;
```

### Senior Principles

```
1. ALWAYS index columns used in WHERE, JOIN, ORDER BY
2. Use EXPLAIN ANALYZE before optimizing
3. Prefer specific columns over SELECT *
4. Use connection pooling (PgBouncer) in production
5. Set statement_timeout to prevent long-running queries
```

---

## 2. MongoDB

### Core Concepts

| Concept | One-Line Explanation |
|---------|---------------------|
| **Document** | JSON-like object (BSON internally) - the basic unit |
| **Collection** | Group of documents (like a table) |
| **_id** | Auto-generated unique identifier (ObjectId) |
| **Embedding** | Nested documents - use when data is accessed together |
| **Referencing** | Store ID reference - use when data is accessed separately |
| **GridFS** | Store files >16MB by chunking into 255KB pieces |

### Essential Operations

```python
from pymongo import MongoClient
from bson.objectid import ObjectId

# Connect
client = MongoClient("mongodb://localhost:27017")
db = client["mydb"]
collection = db["employees"]

# Insert
doc_id = collection.insert_one({"name": "John", "skills": ["Python"]}).inserted_id

# Find with projection (return only needed fields)
employee = collection.find_one(
    {"name": "John"},           # Filter
    {"name": 1, "email": 1}     # Projection (1=include, 0=exclude)
)

# Update with operators
collection.update_one(
    {"_id": ObjectId("...")},
    {"$set": {"email": "new@test.com"}, "$push": {"skills": "FastAPI"}}
)

# Aggregation pipeline (Senior pattern)
pipeline = [
    {"$match": {"department": "Engineering"}},
    {"$group": {"_id": "$position", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]
results = collection.aggregate(pipeline)

# GridFS for large files
from gridfs import GridFS
fs = GridFS(db)
file_id = fs.put(pdf_bytes, filename="resume.pdf")
data = fs.get(file_id).read()
```

### Senior Principles

```
1. Embed for 1:1 and 1:few relationships (data accessed together)
2. Reference for 1:many and many:many (data accessed separately)
3. Create indexes for query patterns: db.collection.createIndex({"field": 1})
4. Use projection to limit returned fields
5. Aggregation > multiple queries for complex operations
```

---

## 3. Python (Senior Patterns)

### Must-Know Patterns

```python
# 1. Context Managers - automatic resource cleanup
class DatabaseConnection:
    def __enter__(self):
        self.conn = create_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
        return False  # Don't suppress exceptions

with DatabaseConnection() as conn:
    conn.execute(query)  # Auto-closes even on exception

# 2. Generators - memory efficient iteration
def read_large_file(path):
    with open(path) as f:
        for line in f:
            yield line.strip()  # Yields one line at a time, not entire file

# 3. Decorators - cross-cutting concerns
import functools
import time

def retry(max_attempts=3, delay=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay * (2 ** attempt))  # Exponential backoff
        return wrapper
    return decorator

@retry(max_attempts=3)
def call_external_api():
    ...

# 4. Type Hints - documentation + IDE support + runtime validation
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

def process_employee(
    name: str,
    skills: List[str],
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    ...

# 5. Dataclasses / Pydantic - structured data
from pydantic import BaseModel, Field, field_validator

class Employee(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    email: Optional[str] = None
    skills: List[str] = []

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email')
        return v
```

### Senior Principles

```
1. Explicit is better than implicit (Zen of Python)
2. Use type hints everywhere - catches bugs before runtime
3. Prefer composition over inheritance
4. Use context managers for resource management
5. Never catch bare `except:` - always specify exception type
6. Use logging, not print() - configurable, leveled, structured
```

---

## 4. FastAPI

### Core Concepts

| Concept | One-Line Explanation |
|---------|---------------------|
| **Path Parameters** | `/users/{user_id}` - part of the URL path |
| **Query Parameters** | `/users?skip=0&limit=10` - optional filters |
| **Request Body** | JSON payload validated by Pydantic model |
| **Dependency Injection** | Reusable components injected into endpoints |
| **Background Tasks** | Run after response is sent |
| **Middleware** | Process request/response globally |

### Essential Patterns

```python
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="EMS API", version="1.0.0")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models (Request/Response)
class EmployeeCreate(BaseModel):
    name: str
    email: Optional[str] = None

class EmployeeResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]

    class Config:
        from_attributes = True  # Enable ORM mode

# Dependency Injection (Senior Pattern)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme)):
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

# Endpoints
@app.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    employee: EmployeeCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_employee = Employee(**employee.dict())
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)

    # Run after response
    background_tasks.add_task(send_welcome_email, db_employee.email)

    return db_employee

@app.get("/employees/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

# Exception Handler (Global)
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(status_code=400, content={"error": str(exc)})
```

### Senior Principles

```
1. Use Dependency Injection for DB sessions, auth, config
2. Always define response_model for auto-documentation + validation
3. Use status codes correctly (201 for create, 204 for delete)
4. Handle errors with HTTPException, not bare exceptions
5. Use BackgroundTasks for non-blocking operations
6. Async endpoints for I/O-bound operations (external APIs, DB)
```

---

## 5. LLM Fundamentals

### Core Concepts

| Concept | One-Line Explanation |
|---------|---------------------|
| **Token** | Smallest unit of text (~4 chars in English) - basis for pricing/limits |
| **Context Window** | Maximum tokens model can process (input + output) |
| **Temperature** | Randomness: 0 = deterministic, 1 = creative |
| **Prompt** | Input text that instructs the model what to do |
| **Completion** | Model's generated response |
| **Hallucination** | Model confidently generating false information |
| **Grounding** | Anchoring responses to provided facts/data |

### Prompt Engineering Patterns

```python
# 1. STRUCTURED OUTPUT - Force JSON response
extraction_prompt = """
Extract information from the text below into JSON format.

CRITICAL RULES:
1. Return ONLY valid JSON - no explanations, no markdown
2. Use null for missing fields
3. Do NOT invent information

Required JSON structure:
{
  "name": "string",
  "email": "string or null",
  "skills": ["array", "of", "strings"]
}

Text to extract from:
{text}

JSON:
"""

# 2. FEW-SHOT PROMPTING - Teach by example
classification_prompt = """
Classify the intent of the user message.

Examples:
User: "Show me John's email" -> Intent: READ
User: "Update Sarah's department to HR" -> Intent: UPDATE
User: "Delete employee Mike" -> Intent: DELETE
User: "Create new employee named Alex" -> Intent: CREATE

User: "{user_message}" -> Intent:
"""

# 3. CHAIN OF THOUGHT - Better reasoning
reasoning_prompt = """
Answer the question step by step.

Question: {question}

Let's think through this:
1. First, identify...
2. Then, consider...
3. Finally, conclude...

Answer:
"""

# 4. SYSTEM + USER SEPARATION (Chat models)
messages = [
    {"role": "system", "content": "You are a helpful HR assistant. Never invent employee data."},
    {"role": "user", "content": "What is John's email?"}
]
```

### Senior Principles

```
1. Lower temperature (0.1-0.3) for factual/extraction tasks
2. Higher temperature (0.7-0.9) for creative tasks
3. Always validate LLM output - never trust blindly
4. Use structured output formats (JSON) for parsing
5. Implement retry logic - LLMs are non-deterministic
6. Ground responses in provided context to prevent hallucination
```

---

## 6. LLM Integration Patterns

### Production-Ready Integration

```python
import httpx
import json
import re
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential

class LLMAdapter:
    """Senior-level LLM integration with error handling and retries."""

    def __init__(self, base_url: str, model: str, timeout: int = 120):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> str:
        """Generate completion with automatic retries."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False
                }
            )
            response.raise_for_status()
            return response.json()["response"]

    def extract_json(self, text: str) -> Optional[dict]:
        """Robust JSON extraction from LLM output."""
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in text
        patterns = [
            r'```json\s*(.*?)\s*```',  # Markdown code block
            r'```\s*(.*?)\s*```',       # Generic code block
            r'\{.*\}',                   # Raw JSON object
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1) if '```' in pattern else match.group(0))
                except json.JSONDecodeError:
                    continue

        return None

    async def extract_structured(
        self,
        text: str,
        schema: dict,
        validate_fn: callable = None
    ) -> dict:
        """Extract structured data with validation."""
        prompt = f"""
Extract information into this exact JSON structure:
{json.dumps(schema, indent=2)}

Text:
{text}

Return ONLY valid JSON:
"""
        response = await self.generate(prompt, temperature=0.1)
        data = self.extract_json(response)

        if data is None:
            raise ValueError("Failed to extract valid JSON from LLM response")

        if validate_fn and not validate_fn(data):
            raise ValueError("Extracted data failed validation")

        return data


# Usage
llm = LLMAdapter(
    base_url="http://localhost:11434",
    model="qwen2.5:7b-instruct"
)

# With Pydantic validation
from pydantic import BaseModel, ValidationError

class ExtractedResume(BaseModel):
    name: str
    email: Optional[str]
    skills: List[str]

async def extract_resume(text: str) -> ExtractedResume:
    data = await llm.extract_structured(text, ExtractedResume.model_json_schema())
    return ExtractedResume(**data)  # Pydantic validates
```

### Anti-Hallucination Pattern

```python
def build_grounded_prompt(
    user_query: str,
    context_data: dict,
    conversation_history: list = None
) -> str:
    """Build prompt that grounds LLM in provided data."""

    history_text = ""
    if conversation_history:
        history_text = "Previous conversation:\n"
        for msg in conversation_history[-5:]:
            history_text += f"{msg['role']}: {msg['content']}\n"

    return f"""
You are answering questions about an employee record.

=== CRITICAL RULES ===
1. ONLY use information from the DATA section below
2. If information is NOT in the data, say "That information is not available"
3. NEVER guess, infer, or make up information
4. Preface answers with "Based on the records..."

=== DATA ===
{json.dumps(context_data, indent=2)}

{history_text}

User Question: {user_query}

Answer:
"""
```

### Senior Principles

```
1. Always implement retries with exponential backoff
2. Set reasonable timeouts (LLMs can be slow)
3. Validate ALL LLM output before using
4. Use lower temperature for extraction/factual tasks
5. Implement fallback strategies (regex extraction if JSON fails)
6. Log prompts and responses for debugging
7. Ground responses in provided context to prevent hallucination
```

---

## 7. MongoDB + FastAPI Integration

### Production Setup

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "myapp"

    class Config:
        env_file = ".env"

settings = Settings()

# database.py
from pymongo import MongoClient
from gridfs import GridFS

class MongoDB:
    client: MongoClient = None
    db = None
    fs: GridFS = None

mongo = MongoDB()

def connect_mongo():
    mongo.client = MongoClient(settings.mongo_uri)
    mongo.db = mongo.client[settings.mongo_db]
    mongo.fs = GridFS(mongo.db)

def close_mongo():
    if mongo.client:
        mongo.client.close()

def get_mongo():
    return mongo.db

# main.py
from fastapi import FastAPI, Depends, UploadFile, File
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    connect_mongo()
    yield
    # Shutdown
    close_mongo()

app = FastAPI(lifespan=lifespan)

# Dependency
def get_db():
    return mongo.db

# Endpoints
@app.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    db = Depends(get_db)
):
    contents = await file.read()

    # Store in GridFS
    file_id = mongo.fs.put(contents, filename=file.filename)

    # Store metadata
    db["documents"].insert_one({
        "file_id": file_id,
        "filename": file.filename,
        "content_type": file.content_type
    })

    return {"file_id": str(file_id)}

@app.get("/documents/{file_id}")
async def get_document(file_id: str):
    from bson.objectid import ObjectId

    grid_out = mongo.fs.get(ObjectId(file_id))

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        iter([grid_out.read()]),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={grid_out.filename}"}
    )
```

---

## 8. PostgreSQL + FastAPI Integration

### Production Setup with SQLAlchemy

```python
# models.py
from sqlalchemy import Column, Integer, String, Text, ARRAY, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(6), unique=True, index=True)
    name = Column(String(256), nullable=False, index=True)
    email = Column(String(256))
    skills = Column(Text)  # JSON string for array
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

engine = create_engine(
    DATABASE_URL,
    pool_size=10,           # Connection pool
    max_overflow=20,        # Extra connections when pool exhausted
    pool_pre_ping=True,     # Verify connections before use
    pool_recycle=3600       # Recycle connections after 1 hour
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# schemas.py (Pydantic)
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class EmployeeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    email: Optional[str] = None
    skills: Optional[List[str]] = []

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    skills: Optional[List[str]] = None

class EmployeeResponse(BaseModel):
    id: int
    employee_id: str
    name: str
    email: Optional[str]
    skills: Optional[List[str]]
    created_at: datetime

    class Config:
        from_attributes = True

# crud.py (Repository Pattern - Senior)
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

class EmployeeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, employee_id: str) -> Optional[Employee]:
        return self.db.query(Employee).filter(
            Employee.employee_id == employee_id
        ).first()

    def get_by_name(self, name: str) -> List[Employee]:
        return self.db.query(Employee).filter(
            Employee.name.ilike(f"%{name}%")
        ).all()

    def create(self, data: EmployeeCreate) -> Employee:
        # Generate next employee_id
        max_id = self.db.query(func.max(Employee.employee_id)).scalar()
        next_id = f"{(int(max_id or 0) + 1):06d}"

        employee = Employee(
            employee_id=next_id,
            name=data.name,
            email=data.email,
            skills=json.dumps(data.skills) if data.skills else None
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return employee

    def update(self, employee_id: str, data: EmployeeUpdate) -> Optional[Employee]:
        employee = self.get_by_id(employee_id)
        if not employee:
            return None

        update_data = data.dict(exclude_unset=True)
        if 'skills' in update_data:
            update_data['skills'] = json.dumps(update_data['skills'])

        for field, value in update_data.items():
            setattr(employee, field, value)

        self.db.commit()
        self.db.refresh(employee)
        return employee

    def delete(self, employee_id: str) -> bool:
        employee = self.get_by_id(employee_id)
        if not employee:
            return False
        self.db.delete(employee)
        self.db.commit()
        return True

# main.py
from fastapi import FastAPI, Depends, HTTPException, status

app = FastAPI()

@app.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db)):
    repo = EmployeeRepository(db)
    return repo.create(data)

@app.get("/employees/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: str, db: Session = Depends(get_db)):
    repo = EmployeeRepository(db)
    employee = repo.get_by_id(employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@app.patch("/employees/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: str, data: EmployeeUpdate, db: Session = Depends(get_db)):
    repo = EmployeeRepository(db)
    employee = repo.update(employee_id, data)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee

@app.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: str, db: Session = Depends(get_db)):
    repo = EmployeeRepository(db)
    if not repo.delete(employee_id):
        raise HTTPException(status_code=404, detail="Employee not found")
```

---

## Quick Reference Card

### Interview Cheat Sheet

```
PostgreSQL:
├── ACID transactions, SERIALIZABLE for money
├── Index everything in WHERE/JOIN/ORDER BY
├── Use EXPLAIN ANALYZE for optimization
└── Connection pooling in production

MongoDB:
├── Embed for 1:1, Reference for 1:many
├── GridFS for files >16MB
├── Aggregation pipeline for complex queries
└── Index your query patterns

Python:
├── Type hints everywhere
├── Context managers for resources
├── Decorators for cross-cutting concerns
└── Pydantic for validation

FastAPI:
├── Dependency Injection for DB/Auth
├── response_model for auto-validation
├── HTTPException for errors
└── BackgroundTasks for async work

LLM:
├── Low temperature for factual tasks
├── Always validate output
├── Retry with exponential backoff
└── Ground in context to prevent hallucination

Integration:
├── Repository pattern for data access
├── Pydantic schemas separate from ORM models
├── Lifespan events for startup/shutdown
└── Connection pooling for databases
```

---

## One-Line Summaries for Each Technology

| Tech | Senior One-Liner |
|------|------------------|
| **PostgreSQL** | "ACID-compliant relational DB; index your queries, use connection pooling, EXPLAIN ANALYZE before optimizing" |
| **MongoDB** | "Document store; embed related data, reference separate data, use aggregation pipelines, GridFS for large files" |
| **Python** | "Type hints + Pydantic for safety, context managers for resources, decorators for cross-cutting concerns" |
| **FastAPI** | "Async framework with Pydantic validation; use Depends for DI, HTTPException for errors, BackgroundTasks for async" |
| **LLM** | "Probabilistic text generation; low temperature for facts, validate all output, ground in context to prevent hallucination" |
| **LLM Integration** | "Retry with backoff, extract JSON robustly, validate with Pydantic, log everything for debugging" |

---

*Last updated: February 3, 2026*
