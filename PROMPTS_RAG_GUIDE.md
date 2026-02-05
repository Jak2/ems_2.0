# Prompts & RAG Integration Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PROMPT LAYER                                   │
│                    extraction_utils.py (Lines 105-338)                   │
├─────────────────────────────────────────────────────────────────────────┤
│  • FEW_SHOT_EXAMPLES (Line 110-188)     → 3 example resumes for learning│
│  • EXTRACTION_SYSTEM_PROMPT (Line 191)  → Rules for extraction          │
│  • VERIFICATION_PROMPT (Line 254)       → Anti-hallucination check      │
│  • create_extraction_prompt() (Line 277)→ Builds full prompt            │
│  • create_retry_prompt() (Line 317)     → Simpler retry when fails      │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           LLM LAYER                                      │
│                      llm_adapter.py (Line 9-147)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  • OllamaAdapter class                                                   │
│  • llm.generate(prompt) → Sends to Ollama HTTP API (localhost:11434)    │
│  • Returns raw text response                                             │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           RAG LAYER                                      │
│           embeddings.py + vectorstore_faiss.py                           │
├─────────────────────────────────────────────────────────────────────────┤
│  embeddings.py:                                                          │
│  • Embeddings class (Line 16) → Uses sentence-transformers              │
│  • Model: "all-MiniLM-L6-v2"                                            │
│  • embed_texts() → Converts text to 384-dim vectors                     │
│                                                                          │
│  vectorstore_faiss.py:                                                   │
│  • FaissVectorStore class (Line 23)                                     │
│  • add_chunks() (Line 66) → Stores employee resume chunks               │
│  • search() (Line 92) → Retrieves similar text chunks                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## File-by-File Breakdown

### 1. extraction_utils.py - PROMPTS

**Location:** `backend/app/services/extraction_utils.py`

| Component | Lines | Purpose |
|-----------|-------|---------|
| `FEW_SHOT_EXAMPLES` | 110-188 | 3 example resumes teaching the LLM extraction patterns |
| `EXTRACTION_SYSTEM_PROMPT` | 191-250 | Rules: field guides, department inference, output format |
| `VERIFICATION_PROMPT` | 254-274 | Chain-of-Verification to catch hallucinations |
| `create_extraction_prompt()` | 277-314 | Combines system prompt + resume text + JSON template |
| `create_retry_prompt()` | 317-337 | Simpler prompt when first extraction fails |
| `quick_verify_extraction()` | 409-436 | Rule-based verification (checks if values exist in source) |

#### Few-Shot Examples Structure
```python
FEW_SHOT_EXAMPLES = """
**EXAMPLE 1: Standard Resume**
Input: "John Smith, john.smith@email.com..."
Output: {"name": "John Smith", "email": "...", ...}

**EXAMPLE 2: QA Professional**
Input: "Priya Sharma | priya.s@tech.in..."
Output: {"name": "Priya Sharma", ...}

**EXAMPLE 3: Project Manager**
Input: "Sam T, 8324567123..."
Output: {"name": "Sam T", ...}
"""
```

#### Extraction System Prompt Structure
```python
EXTRACTION_SYSTEM_PROMPT = """You are an expert resume parser...

=== CRITICAL RULES ===
1. ONLY extract information that EXPLICITLY exists in the text
2. NEVER guess, infer, or make up information
3. If a field is not found, use null
4. Return ONLY valid JSON
5. Double-check each field before finalizing

=== FIELD EXTRACTION GUIDE ===
**CONTACT INFO:** name, email, phone
**PROFESSIONAL INFO:** position, department
**WORK EXPERIENCE:** [{company, role, duration, responsibilities}]
**EDUCATION:** [{degree, institution, year, grade}]
**SKILLS:** technical_skills array
**LANGUAGES:** spoken languages only
"""
```

---

### 2. llm_adapter.py - LLM COMMUNICATION

**Location:** `backend/app/services/llm_adapter.py`

| Component | Lines | Purpose |
|-----------|-------|---------|
| `OllamaAdapter` | 9-147 | Wrapper class for Ollama |
| `generate()` | 29-147 | Sends prompt to Ollama, returns response |
| HTTP API | 46-74 | Primary: `POST localhost:11434/api/generate` |
| CLI Fallback | 76-147 | Backup: `ollama run <model> <prompt>` |

#### LLM Configuration
```python
payload = {
    "model": self.model,           # qwen2.5:3b-instruct
    "prompt": prompt,
    "stream": False,
    "options": {
        "temperature": 0,          # Deterministic outputs
        "num_predict": 2048,       # Token limit
        "num_ctx": 4096,           # Context window
        "seed": 42,                # Reproducibility
    }
}
```

---

### 3. embeddings.py - VECTOR EMBEDDINGS

**Location:** `backend/app/services/embeddings.py`

| Component | Lines | Purpose |
|-----------|-------|---------|
| `Embeddings` | 16-32 | Wrapper for sentence-transformers |
| `embed_texts()` | 22-32 | Converts text → 384-dimensional vectors |
| L2 normalization | 29-31 | Normalizes for cosine similarity search |

#### Embedding Process
```python
class Embeddings:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts):
        emb = self.model.encode(texts)
        # L2 normalize for cosine similarity
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        return (emb / norms).astype("float32")
```

---

### 4. vectorstore_faiss.py - RAG STORAGE

**Location:** `backend/app/services/vectorstore_faiss.py`

| Component | Lines | Purpose |
|-----------|-------|---------|
| `FaissVectorStore` | 23-108 | FAISS index + metadata storage |
| `add_chunks()` | 66-90 | Embeds + stores resume chunks |
| `search()` | 92-108 | Retrieves similar chunks by query |

#### Vector Store Operations
```python
class FaissVectorStore:
    def add_chunks(self, employee_id, chunks):
        """Store resume text chunks with embeddings"""
        vecs = self.emb.embed_texts(chunks)
        self.index.add(vecs)
        # Save metadata mapping vector ID → employee_id + text

    def search(self, query, top_k=5, employee_id=None):
        """Search for similar text chunks"""
        qvec = self.emb.embed_texts([query])
        D, I = self.index.search(qvec, top_k)
        # Return matching chunks with scores
```

---

### 5. main.py - ORCHESTRATION

**Location:** `backend/app/main.py`

| Location | Lines | What Happens |
|----------|-------|--------------|
| Initialization | 157, 165 | `llm = OllamaAdapter()`, `vectorstore = FaissVectorStore()` |
| Resume extraction | 620-630 | `create_extraction_prompt()` → `llm.generate()` |
| Retry extraction | 750 | `create_retry_prompt()` → `llm.generate()` |
| Index chunks | 598, 1108 | `vectorstore.add_chunks(emp.id, chunks)` |
| RAG search | 3261 | `vectorstore.search(query, top_k=5, employee_id=emp.id)` |
| Chat response | 3748 | `llm.generate(prompt)` with retrieved context |
| `special_llm_context` | 1392+ | Routes all queries through LLM with structured data |

---

## Data Flow Diagrams

### Resume Upload Flow

```
1. User uploads resume.pdf
         │
         ▼
2. extractor.py extracts text from PDF
         │
         ▼
3. extraction_utils.create_extraction_prompt(pdf_text)
   → Builds: SYSTEM_PROMPT + FEW_SHOT_EXAMPLES + resume text + JSON template
         │
         ▼
4. llm_adapter.generate(prompt)
   → Sends to Ollama (qwen2.5:3b-instruct)
   → Returns JSON with extracted fields
         │
         ▼
5. extraction_utils.quick_verify_extraction(result, pdf_text)
   → Checks each field exists in source text
   → Sets hallucinated values to null
         │
         ▼
6. Text is chunked (500 chars each)
         │
         ▼
7. embeddings.embed_texts(chunks)
   → Converts to 384-dim vectors
         │
         ▼
8. vectorstore.add_chunks(employee_id, chunks)
   → Stores in FAISS index + meta.json
```

### Chat Query Flow

```
1. User asks: "Find employees with Python skills"
         │
         ▼
2. main.py detects search intent
         │
         ▼
3. vectorstore.search("Python skills", top_k=5)
   → Embeds query → FAISS similarity search
   → Returns matching resume chunks
         │
         ▼
4. Retrieved chunks added to prompt as context (RAG)
         │
         ▼
5. special_llm_context = {
       "type": "search_results",
       "data": {...matching employees...}
   }
         │
         ▼
6. llm.generate(prompt_with_context)
   → LLM formats response using retrieved data
         │
         ▼
7. Response returned to user
```

---

## Multi-Query Handling (New Feature)

**Location:** `backend/app/services/extraction_utils.py` (Lines 997-1175)

### Components

| Component | Lines | Purpose |
|-----------|-------|---------|
| `MULTI_QUERY_INDICATORS` | 1002-1014 | Keywords indicating multiple tasks |
| `TASK_CONJUNCTIONS` | 1017-1032 | Patterns connecting separate tasks |
| `detect_multi_query()` | 1035-1064 | Detects complex multi-part queries |
| `QUERY_DECOMPOSITION_PROMPT` | 1067-1089 | LLM prompt to break down queries |
| `parse_decomposed_tasks()` | 1104-1135 | Parses LLM response into task list |
| `RESULT_AGGREGATION_PROMPT` | 1138-1153 | Combines sub-task results |

### Multi-Query Flow

```
User: "what skills debraj has and count cloud skills,
       what skills does udayateja have, compare both"
                    │
                    ▼
         detect_multi_query() → TRUE
                    │
                    ▼
         LLM decomposes into sub-tasks:
         [
           {task_id: 1, query: "Get Debraj's skills", type: "search"},
           {task_id: 2, query: "Count cloud skills", type: "count", depends_on: 1},
           {task_id: 3, query: "Get Udayateja's skills", type: "search"},
           {task_id: 4, query: "Compare both", type: "compare", depends_on: [1,3]}
         ]
                    │
                    ▼
         Execute each sub-task sequentially
         (with context passing for dependent tasks)
                    │
                    ▼
         Aggregate results via LLM
                    │
                    ▼
         Return unified response
```

---

## Key Integration Points Summary

| File | Line | Integration |
|------|------|-------------|
| main.py | 620 | `extraction_prompt = create_extraction_prompt(pdf_text)` |
| main.py | 630 | `extraction_resp = llm.generate(extraction_prompt)` |
| main.py | 598 | `vectorstore.add_chunks(emp.id, chunks)` |
| main.py | 3261 | `retrieved = vectorstore.search(req.prompt, top_k=5)` |
| main.py | 3447-3723 | `special_llm_context` routes data through LLM |
| main.py | 3748 | `resp = llm.generate(prompt)` - final chat response |
| main.py | 1014-1170 | Multi-query detection and handling |

---

## Anti-Hallucination Measures

1. **Few-Shot Examples** - Teaching correct extraction patterns
2. **Explicit Rules** - "NEVER guess, infer, or make up information"
3. **Chain-of-Verification** - `quick_verify_extraction()` checks values against source
4. **Temperature=0** - Deterministic outputs for consistency
5. **Retry Prompts** - Simpler prompt when first extraction fails
6. **Field Validation** - Schema enforcement via `validators.py`

---

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | LLM model name |
| `OLLAMA_API_URL` | `http://localhost:11434/api/generate` | Ollama endpoint |
| `OLLAMA_TEMPERATURE` | `0` | Response randomness |

### Model Parameters

```python
{
    "temperature": 0,      # Deterministic
    "num_predict": 2048,   # Max tokens
    "num_ctx": 4096,       # Context window
    "seed": 42             # Reproducibility
}
```
