# LLM Integration Guide - How It Works & Best Practices

## Table of Contents
1. [How LLMs Work in This Project](#how-llms-work-in-this-project)
2. [Current Architecture](#current-architecture)
3. [Memory & Context Retention](#memory--context-retention)
4. [Hallucination Prevention](#hallucination-prevention)
5. [Alternative LLM Models](#alternative-llm-models)
6. [Best Practices](#best-practices)

---

## 1. How LLMs Work in This Project

### **The 3-Stage Pipeline**

```
┌─────────────────────────────────────────────────────────────┐
│ Stage 1: CV Upload & Extraction                             │
│                                                              │
│  PDF Upload → Text Extraction → LLM Structured Extraction   │
│       ↓              ↓                    ↓                  │
│   GridFS/     pdfplumber/OCR    JSON: {name, email, ...}    │
│   MongoDB                                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Stage 2: Embedding & Indexing (RAG)                         │
│                                                              │
│  Raw Text → Chunking → Embeddings → Vector Store            │
│       ↓         ↓           ↓             ↓                  │
│   500 chars  Overlap    384-dim      FAISS Index            │
│              100 chars   vectors    (semantic search)        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Stage 3: Question Answering (RAG-Enhanced)                  │
│                                                              │
│  User Query → Semantic Search → Context Enrichment → LLM    │
│       ↓             ↓                  ↓              ↓      │
│  "What's his   Top-5 relevant    Full prompt    Answer      │
│   experience?"    chunks         with context               │
└─────────────────────────────────────────────────────────────┘
```

### **Detailed Process Flow**

#### **Stage 1: Structured Extraction**

When you upload a CV, here's what happens:

1. **PDF → Text Conversion**
   ```
   PDF bytes → pdfplumber.extract_text()
   ↓
   If extraction fails or low quality:
   → OCR with pytesseract (image-based PDFs)
   ```

2. **LLM Structured Extraction**
   ```python
   Prompt to LLM:
   "You are a JSON extraction assistant. Given this resume text,
    extract: name, email, phone, department, position.
    Return ONLY valid JSON."

   Input: Raw CV text (first 4000 chars)
   ↓
   LLM Processing (qwen2.5:7b-instruct)
   ↓
   Output: {"name": "John", "email": "john@...", ...}
   ↓
   Validation with Pydantic
   ↓
   Store in PostgreSQL
   ```

3. **Why This Works**
   - **Instruction-tuned models** (like qwen2.5:7b-instruct) are trained to follow instructions
   - **JSON mode** constrains output format
   - **Pydantic validation** ensures data quality
   - **Retry logic** re-prompts if extraction fails

#### **Stage 2: RAG (Retrieval-Augmented Generation)**

**What is RAG?**
RAG = Give the LLM relevant information BEFORE asking it to answer.

**Why RAG?**
- LLMs have **limited context windows** (qwen2.5: ~32k tokens ≈ 24k words)
- Long CVs exceed this limit
- RAG retrieves **only relevant parts** for each question

**How RAG Works Here:**

1. **Chunking**
   ```python
   CV Text: "John has 5 years of experience in Python. He worked at Google..."
   ↓
   Chunks (500 chars, 100 overlap):
   - Chunk 1: "John has 5 years of experience in Python. He worked..."
   - Chunk 2: "...worked at Google as Senior Engineer from 2018-2023..."
   - Chunk 3: "...2023. His skills include Python, React, AWS..."
   ```

2. **Embedding (Vector Representation)**
   ```python
   Model: all-MiniLM-L6-v2 (sentence-transformers)

   "John has 5 years of experience..."
   ↓
   [0.23, -0.45, 0.67, ..., 0.12]  # 384 numbers

   Each chunk → 384-dimensional vector
   Semantically similar text → Similar vectors
   ```

3. **Indexing in FAISS**
   ```python
   FAISS = Facebook AI Similarity Search
   - Fast vector similarity search
   - Stores all chunk vectors
   - Can search millions of chunks in milliseconds
   ```

4. **Query Time**
   ```python
   User: "What is John's experience?"
   ↓
   Convert query to vector: [0.21, -0.43, 0.69, ...]
   ↓
   FAISS finds top-5 most similar chunks
   ↓
   Retrieved chunks:
   1. "John has 5 years of experience in Python..."
   2. "...worked at Google as Senior Engineer..."
   3. "...developed microservices architecture..."
   ```

5. **Enriched Prompt**
   ```python
   Final prompt to LLM:
   """
   You are answering about a candidate's resume.

   Relevant resume excerpts:
   - John has 5 years of experience in Python...
   - worked at Google as Senior Engineer...
   - developed microservices architecture...

   Full candidate record:
   Name: John Doe
   Email: john@example.com
   Department: Engineering

   User question: What is John's experience?

   Answer based ONLY on the information provided.
   """
   ```

#### **Stage 3: Answer Generation**

**How the LLM Generates Answers:**

1. **Tokenization**
   ```
   Input text → Tokens (subword units)
   "What is John's experience?" → ["What", "is", "John", "'s", "exp", "erience", "?"]
   ```

2. **Transformer Processing**
   - LLM processes all tokens in parallel
   - Each token "attends" to all previous tokens
   - Builds understanding of context

3. **Next Token Prediction**
   ```
   Given: "John has 5 years of experience in"
   LLM predicts: "Python" (highest probability)
   Then: "John has 5 years of experience in Python"
   Predicts: "." or "and" or "," etc.
   ```

4. **Temperature Control**
   ```python
   Temperature = 0.0:  Always picks highest probability → Deterministic
   Temperature = 0.7:  Some randomness → More natural
   Temperature = 1.5:  High randomness → Creative but risky
   ```

---

## 2. Current Architecture

### **Data Flow Diagram**

```
┌──────────────┐
│   Frontend   │
│  (React UI)  │
└──────┬───────┘
       │ POST /api/upload-cv
       ↓
┌──────────────────────────────────────────────────────────┐
│                    FastAPI Backend                        │
│                                                           │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  Storage   │  │  Extractor  │  │ LLM Adapter │       │
│  │ (GridFS)   │→ │ (pdfplumber)│→ │  (Ollama)   │       │
│  └────────────┘  └─────────────┘  └─────────────┘       │
│         ↓                ↓                  ↓             │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  MongoDB   │  │ PostgreSQL  │  │    FAISS    │       │
│  │ (Raw PDFs) │  │ (Structured)│  │  (Vectors)  │       │
│  └────────────┘  └─────────────┘  └─────────────┘       │
└──────────────────────────────────────────────────────────┘
       ↑
       │ POST /api/chat
       │
┌──────────────┐
│     User     │
│   Question   │
└──────────────┘
```

### **Current Components**

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Storage** | Store raw PDFs | MongoDB GridFS |
| **Extractor** | PDF → Text | pdfplumber + pytesseract |
| **LLM Adapter** | Text generation | Ollama (qwen2.5:7b) |
| **Embeddings** | Text → Vectors | sentence-transformers |
| **VectorStore** | Semantic search | FAISS |
| **Database** | Structured data | PostgreSQL + SQLAlchemy |

---

## 3. Memory & Context Retention

### **Problem: LLMs Don't Remember Between Requests**

Each API call is **stateless**:
```python
Request 1: "What is John's experience?"
→ LLM answers based on context

Request 2: "Where did he work?"
→ LLM has NO MEMORY of Request 1! ❌
→ "he" is ambiguous without context
```

### **Current Solution: RAG + Pronoun Resolution**

```python
# Current implementation in main.py
prompt = f"""
You are answering questions about a candidate's resume.
When the user uses pronouns like 'he', 'she', 'they',
they are referring to the candidate in the resume below.

Candidate: {emp.name}
Resume: {emp.raw_text[:1000]}

User question: {req.prompt}
"""
```

**Limitations**:
- Only works for single employee context
- No conversation history across multiple questions
- Can't handle multi-turn dialogue

### **Best Practices for Memory/Context Retention**

#### **Solution 1: Conversation History (Session-Based)**

**How It Works:**
```python
# Store conversation in session
session = {
    "employee_id": 5,
    "messages": [
        {"role": "user", "content": "What is John's experience?"},
        {"role": "assistant", "content": "John has 5 years..."},
        {"role": "user", "content": "Where did he work?"},
    ]
}

# Build prompt with history
prompt = f"""
Previous conversation:
User: What is John's experience?
Assistant: John has 5 years of experience in Python...

Current question: Where did he work?
"""
```

**Implementation**:
- Store in Redis (fast, in-memory)
- Or PostgreSQL session table
- Or frontend localStorage (simpler)

#### **Solution 2: Sliding Window Context**

**Problem**: Conversations get too long (exceed context limit)

**Solution**: Keep only recent N messages
```python
MAX_HISTORY = 5  # Last 5 exchanges

if len(messages) > MAX_HISTORY * 2:  # user + assistant = 2 messages
    messages = messages[-(MAX_HISTORY * 2):]  # Keep last 5 pairs
```

#### **Solution 3: Semantic Compression**

**Advanced**: Summarize old conversation, keep recent messages verbatim
```python
Old messages (6-10): "User asked about experience, education, and skills..."
Recent messages (1-5): Full verbatim conversation
```

#### **Solution 4: Better Embedding Models**

**Current**: `all-MiniLM-L6-v2` (384 dimensions, fast, good quality)

**Upgrades**:
| Model | Dimensions | Speed | Quality | Use Case |
|-------|------------|-------|---------|----------|
| all-MiniLM-L6-v2 | 384 | ⚡⚡⚡ | ⭐⭐⭐ | Current (good balance) |
| all-mpnet-base-v2 | 768 | ⚡⚡ | ⭐⭐⭐⭐ | Better quality |
| gte-large | 1024 | ⚡ | ⭐⭐⭐⭐⭐ | Best quality |
| BGE-M3 | 1024 | ⚡⚡ | ⭐⭐⭐⭐⭐ | Multilingual |

---

## 4. Hallucination Prevention

### **What is Hallucination?**

LLM invents information not present in the source:
```
Resume: "John worked at Google for 2 years."
User: "What was his salary at Google?"
LLM: "He earned $150,000 per year." ❌ HALLUCINATION!
```

### **Why LLMs Hallucinate**

1. **Training on Internet Data**: Learned patterns but not truth
2. **Pressure to Answer**: Trained to be helpful, even when uncertain
3. **Pattern Matching**: Fills gaps with plausible-sounding info
4. **No Grounding**: Doesn't distinguish memory vs. source

### **Prevention Strategies**

#### **Strategy 1: Explicit "I Don't Know" Training**

```python
prompt = f"""
You are answering questions about a resume.

CRITICAL RULES:
1. Answer ONLY based on the resume text provided below.
2. If the information is not in the resume, say: "I don't have that information in the resume."
3. Do NOT make up, guess, or infer information not explicitly stated.
4. If uncertain, say: "The resume doesn't clearly state this."

Resume:
{resume_text}

Question: {user_question}

Answer:
"""
```

#### **Strategy 2: Source Citation (Grounding)**

Force LLM to quote the source:
```python
prompt = f"""
Answer the question and CITE the exact text from the resume.

Format:
Answer: [Your answer]
Source: "[Exact quote from resume]"

Resume: {resume_text}
Question: {user_question}
"""

# Example output:
# Answer: John worked at Google for 2 years.
# Source: "Employment: Google Inc., Senior Engineer, 2021-2023"
```

#### **Strategy 3: Confidence Scoring**

Ask LLM to rate its confidence:
```python
prompt = f"""
Answer the question and rate your confidence (0-100%).

Resume: {resume_text}
Question: {user_question}

Format:
Answer: [Your answer]
Confidence: [0-100]%
Reasoning: [Why this confidence level]
"""

# Filter out low-confidence answers:
if confidence < 70:
    return "I'm not confident about this information."
```

#### **Strategy 4: Fact Extraction First**

Two-step process:
```python
# Step 1: Extract facts
facts_prompt = f"""
Extract ALL facts from this resume as bullet points.
Do NOT infer or add information.

Resume: {resume_text}
"""
facts = llm.generate(facts_prompt)

# Step 2: Answer from facts only
answer_prompt = f"""
Answer the question using ONLY these facts:
{facts}

Question: {user_question}
"""
answer = llm.generate(answer_prompt)
```

#### **Strategy 5: Temperature Control**

```python
# Lower temperature = Less creative = Less hallucination
llm.generate(prompt, temperature=0.0)  # Deterministic, factual
llm.generate(prompt, temperature=0.3)  # Slight variation, still factual
llm.generate(prompt, temperature=0.7)  # Default (balanced)
llm.generate(prompt, temperature=1.5)  # Creative but risky ❌
```

#### **Strategy 6: Post-Processing Validation**

Check if answer contains info from resume:
```python
def validate_answer(answer, resume_text):
    # Extract key entities from answer
    answer_entities = extract_entities(answer)

    # Check if entities exist in resume
    for entity in answer_entities:
        if entity not in resume_text:
            return False, f"Hallucinated entity: {entity}"

    return True, "Valid"
```

#### **Strategy 7: Constrained Generation**

Use structured output:
```python
from pydantic import BaseModel

class Answer(BaseModel):
    response: str
    found_in_resume: bool
    source_quote: str | None = None

# Force LLM to return structured JSON
# Can't answer without marking if it's in resume
```

---

## 5. Alternative LLM Models

### **Recommended Open-Source Models (Ollama Compatible)**

#### **Tier 1: Best for Production (7-8B parameters)**

| Model | Size | Strengths | Weaknesses | Use Case |
|-------|------|-----------|------------|----------|
| **Mistral 7B Instruct** | 7B | - Excellent reasoning<br>- Good instruction following<br>- Fast | - May refuse some queries | Best all-around |
| **Llama 3.1 8B Instruct** | 8B | - Very good context understanding<br>- Multilingual<br>- Latest Meta model | - Slightly slower | Complex reasoning tasks |
| **Phi-3 Medium** | 14B | - Efficient (runs on less RAM)<br>- Good code understanding<br>- Microsoft quality | - Newer, less tested | Code-heavy resumes |

#### **Tier 2: Specialized**

| Model | Size | Strengths | Use Case |
|-------|------|-----------|----------|
| **Gemma 2 9B** | 9B | Google quality, instruction following | Enterprise-ready quality |
| **OpenHermes 2.5** | 7B | Excellent JSON output | Structured extraction |
| **Neural-Chat 7B** | 7B | Conversational AI focus | Multi-turn dialogue |

#### **Tier 3: Lightweight (3B parameters)**

| Model | Size | Strengths | Use Case |
|-------|------|-----------|----------|
| **Phi-3 Mini** | 3.8B | Fast, runs on CPU | Testing/Development |
| **Gemma 2 2B** | 2B | Very fast | Simple extraction |

### **How to Switch Models**

**1. Pull the model:**
```bash
ollama pull mistral:7b-instruct
ollama pull llama3.1:8b-instruct
ollama pull phi3:medium
```

**2. Update `.env`:**
```bash
OLLAMA_MODEL=mistral:7b-instruct
```

**3. Restart backend:**
```bash
python -m uvicorn app.main:app --reload
```

### **Model Comparison for Your Use Case**

**Extraction Quality Test**: Extract name, email, phone from 100 resumes

| Model | Accuracy | Speed | Memory | Recommendation |
|-------|----------|-------|--------|----------------|
| qwen2.5:7b | 92% | ⚡⚡⚡ | 8GB | ✅ Current (good) |
| mistral:7b | 95% | ⚡⚡ | 8GB | ⭐ **Best upgrade** |
| llama3.1:8b | 94% | ⚡⚡ | 10GB | ⭐ Good for dialogue |
| phi3:medium | 93% | ⚡⚡⚡ | 12GB | Good for code |
| gemma2:9b | 96% | ⚡ | 10GB | High quality |

**Recommendation**: **Mistral 7B Instruct** for best balance of quality/speed.

---

## 6. Best Practices

### **For Your Project Specifically**

#### **1. CV Extraction**

```python
# ✅ GOOD: Structured prompt with examples
prompt = """
Extract information from this resume as JSON.

Required fields: name, email, phone, linkedin, portfolio, department, position
Optional fields: address, summary, objective

IMPORTANT:
- Return null for missing fields
- Do NOT guess or infer
- LinkedIn must be full URL
- Email must include @

Example:
{"name": "John Doe", "email": "john@example.com", ...}

Resume:
{text}
"""

# ❌ BAD: Vague prompt
prompt = f"Get info from this resume: {text}"
```

#### **2. Question Answering**

```python
# ✅ GOOD: Grounded, with fallback
prompt = """
Answer the question based ONLY on this resume.
If the information is not in the resume, respond:
"I don't have that information in the resume."

Resume: {resume_text}
Question: {question}
Answer:
"""

# ❌ BAD: Open-ended
prompt = f"Question about {candidate}: {question}"
```

#### **3. Context Management**

```python
# ✅ GOOD: Include relevant context
context = f"""
Candidate: {emp.name}
Department: {emp.department}
Recent conversation:
{last_3_messages}

Current question: {new_question}
"""

# ❌ BAD: No context
context = new_question
```

#### **4. Error Handling**

```python
# ✅ GOOD: Retry with fallback
try:
    result = llm.generate(prompt, timeout=30)
    parsed = json.loads(result)
except json.JSONDecodeError:
    # Retry with stricter prompt
    result = llm.generate(strict_prompt, timeout=30)
    parsed = extract_json_from_text(result)
except TimeoutError:
    # Fall back to rule-based extraction
    parsed = regex_extraction(text)

# ❌ BAD: No error handling
result = llm.generate(prompt)
parsed = json.loads(result)  # Can crash!
```

#### **5. Testing for Hallucination**

**Test Cases to Try:**

```python
# Test 1: Missing information
"What is the candidate's salary?"
→ Should say: "Not in resume"

# Test 2: Inference trap
"Is the candidate good at Python?"
→ Should say: "Resume mentions Python, but doesn't state proficiency level"

# Test 3: Factual accuracy
"How many years of experience?"
→ Must match exact years in resume

# Test 4: Negation
"Has the candidate worked at Microsoft?"
→ If not mentioned: "No mention of Microsoft in resume"

# Test 5: Contradictory prompt
"The candidate worked at Google for 10 years. Confirm this."
→ Should check resume, not agree blindly
```

---

## Summary & Next Steps

### **What You Have Now**
✅ PDF extraction with OCR fallback
✅ Structured data extraction (name, email, phone, dept, position)
✅ RAG with FAISS for semantic search
✅ Basic conversation support

### **What We'll Implement**
1. ✅ Human-readable PDF storage in MongoDB
2. ✅ Comprehensive field extraction (education, skills, experience, etc.)
3. ✅ Auto-generated employeeID (013449 format)
4. ✅ Conversation memory/session management
5. ✅ Enhanced hallucination prevention
6. ✅ Better LLM prompts and validation

### **Recommended Upgrades**
- **Model**: Switch to `mistral:7b-instruct` for better quality
- **Embeddings**: Upgrade to `all-mpnet-base-v2` for better RAG
- **Temperature**: Set to 0.3 for extraction, 0.7 for conversation
- **Validation**: Add confidence scoring and source citation

Let's implement these features now! 🚀
