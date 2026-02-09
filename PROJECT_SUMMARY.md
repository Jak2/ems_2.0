# EMS 2.0 - Employee Management System

## Interview Summary

### What is this project?
An AI-powered Employee Management System that uses **Natural Language Processing** to manage employee records. Instead of traditional forms, users interact through a **chatbot interface** - uploading resumes (PDF/images) and querying data using plain English.

---

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React + Vite |
| **Backend** | FastAPI (Python) |
| **Database** | PostgreSQL (SQLAlchemy ORM) |
| **LLM** | Ollama (Qwen 2.5 - runs locally) |
| **Vector Store** | FAISS (semantic search) |
| **File Storage** | MongoDB GridFS / Local filesystem |
| **OCR** | Tesseract (for image-based resumes) |

---

### Key Features

1. **Resume Upload & Auto-Extraction**
   - Upload PDF or image files (JPG, PNG)
   - LLM extracts structured data: name, email, phone, skills, experience, education
   - Validates document is actually a resume (scoring system)

2. **Natural Language CRUD**
   - `"Show all employees"` → Lists all records
   - `"Find employees with Python skills"` → Semantic search
   - `"Update John's email to john@new.com"` → Updates database
   - `"Delete employee EMP001"` → Removes record

3. **RAG (Retrieval-Augmented Generation)**
   - Resume text is chunked and embedded using sentence-transformers
   - FAISS index enables semantic similarity search
   - Context retrieved and passed to LLM for accurate responses

4. **Identity Verification**
   - Handles duplicate names intelligently
   - Asks for clarification: "Did you mean John Smith (EMP001) or John Smith (EMP002)?"

5. **Anti-Hallucination Guards**
   - Validates LLM extractions against source text
   - Retry prompts for missing critical fields
   - Confidence scoring per extraction

---

### Architecture Flow

```
User Input (Chat/Upload)
        │
        ▼
   ┌─────────────────┐
   │  FastAPI Backend │
   └────────┬────────┘
            │
   ┌────────┴────────┐
   │                 │
   ▼                 ▼
PDF/Image        NL Query
Extraction       Processing
   │                 │
   ▼                 ▼
Ollama LLM ◄───► FAISS Search
   │                 │
   ▼                 ▼
PostgreSQL      Return Results
   │
   ▼
Response to User
```

---

### Challenges Solved

| Challenge | Solution |
|-----------|----------|
| LLM hallucinations | Verification against source text + retry prompts |
| Slow response time | Optimized num_predict, num_ctx parameters |
| Image-based resumes | Tesseract OCR with multiple PSM modes |
| Ambiguous queries | Context-aware pronoun resolution |
| Duplicate employees | Identity verification with user disambiguation |
| CRUD routing failures | Multi-query bypass + expanded employee context detection |

---

### Sample Interactions

```
User: "Upload resume.pdf"
Bot:  "Successfully extracted: John Doe, Software Engineer, 5 years experience..."

User: "Find employees skilled in AWS"
Bot:  "Found 3 employees: John Doe (EMP001), Jane Smith (EMP002)..."

User: "What is John's email?"
Bot:  "John Doe's email is john.doe@email.com"

User: "Update his phone to 555-1234"
Bot:  "Updated John Doe's phone number to 555-1234"
```

---

### Why This Approach?

- **No forms needed** - Natural conversation reduces friction
- **Local LLM** - Data stays on-premise (privacy/compliance)
- **Semantic search** - Finds relevant employees even with different wording
- **Extensible** - Easy to add new fields or query types

---

### Potential Improvements

- Add user authentication (JWT)
- Implement proper rate limiting
- Use Redis for session management
- Add comprehensive test coverage
- Optimize FAISS with IVF indexing for scale
