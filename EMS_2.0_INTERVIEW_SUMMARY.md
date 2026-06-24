# EMS 2.0 — Interview Summary

> **Role target:** Backend Python SWE / AI Engineer  
> **Use this doc as:** rehearsal script — 30-sec pitch for openers, 2-min pitch for "tell me about a project", deep-dive sections for technical follow-ups.

---

## 30-Second Elevator Pitch

I built an AI-powered Employee Management System where every interaction — creating, searching, updating, and deleting employee records — happens through a natural language chat interface. Users upload a PDF or image resume, a locally-running LLM extracts all structured data automatically, and from that point on they can just ask the system things like "Find me a DevOps engineer with Kubernetes experience" or "Update John's email to this new address." The whole stack runs on-premise: FastAPI backend, PostgreSQL plus MongoDB plus a FAISS vector store, and an Ollama-hosted LLM — so no resume data ever leaves the machine.

---

## 2-Minute Structured Pitch

**The problem:** Traditional HR tools make you fill out 20-plus fields manually per employee and give you no way to search by intent — you can't just ask "who's our most senior Python developer?" I wanted to remove all of that friction.

**What I built:** A full-stack system where the LLM does all the heavy lifting. Drop a PDF resume on the frontend, the backend extracts the text, sends it to a locally-running `qwen2.5:7b-instruct` model via Ollama with a structured extraction prompt, validates the JSON output with Pydantic, writes the record to PostgreSQL, and simultaneously indexes the employee's text chunks in a FAISS vector store for semantic search. All of that happens in a background thread so the frontend never blocks — it polls for job completion.

**The core technical challenge:** LLM output is unreliable. In roughly 10–20% of extraction attempts the model returns malformed JSON, wraps the output in markdown code fences, or drops required fields. I built a four-strategy parsing chain — direct JSON parse, regex extraction, regex cleanup, key-value fallback — with a Pydantic validation layer on top, and the system retries with a stricter prompt if the employee name is missing. That brought extraction reliability to a usable level on consumer hardware.

**The outcome:** A fully working NLP-driven CRUD interface backed by RAG search, with five anti-hallucination guards, session memory with pronoun resolution ("What are his skills?" after asking about John), and multi-query decomposition for compound questions. The whole system runs locally on a 6GB GPU.

---

## Architecture in Plain English

### Why three databases?

Each database does exactly one thing it's best at — I deliberately avoided the trap of forcing a single database to handle all three concerns:

| Store | What it holds | Why this one |
|---|---|---|
| **PostgreSQL** | Structured employee records (22+ fields) | Relational queries, `UPDATE`/`DELETE`, transactional writes |
| **MongoDB GridFS** | Raw PDF and image files | Binary chunked storage; files don't belong in a relational DB |
| **FAISS** | Dense vector embeddings of employee text | Sub-millisecond approximate nearest-neighbour search — SQL `LIKE` doesn't understand semantic similarity |

A query like "experienced DevOps engineer" has no keyword overlap with a resume that says "managed Kubernetes clusters for five years." FAISS finds that match; PostgreSQL cannot.

### LLM pipeline end-to-end

```
PDF upload
  → pdfplumber extracts text (pytesseract OCR fallback for images)
  → Resume scoring (threshold 40/100) — reject garbage before touching the LLM
  → Ollama HTTP API: structured extraction prompt → JSON
  → 4-strategy JSON parsing chain
  → Pydantic v2 validation → Employee object
  → PostgreSQL write + FAISS indexing (background thread)
  → Job status file written → frontend polling picks it up
```

**Key parameter choices:** `temperature=0` for deterministic extraction (reproducible output across runs), `seed=42`, `num_ctx=4096` context window, `num_predict=2048` (reduced from 4096 — faster with no quality loss for structured extraction).

### RAG implementation

Every employee's combined text (name, role, skills, experience descriptions) is chunked at 500 characters with a 100-character overlap, embedded with `sentence-transformers/all-MiniLM-L6-v2`, and stored in FAISS. On a query without a named employee, the system:

1. Tries to find the employee by name-matching in the prompt
2. Falls back to FAISS top-5 similarity search
3. Passes the retrieved employee context to Ollama so the response is grounded in real data, not hallucinated

This is the standard RAG pattern — retrieval gates the generation so the model can only answer from what actually exists.

### Async processing pattern

FastAPI's `BackgroundTasks` was replaced with explicit `threading.Thread(daemon=True)`. The reason: `BackgroundTasks` with blocking calls (Ollama HTTP requests, subprocess invocations) caused subtle timing issues. Explicit threads are more predictable. Job status is written to flat JSON files (`data/jobs/{job_id}.json`) rather than a DB table — avoids connection overhead during polling and is trivially debuggable.

---

## Key Technical Decisions

### Local LLM over cloud API

I chose Ollama over OpenAI or Anthropic deliberately:
- **Privacy** — resume data contains PII; it never leaves the machine
- **No API costs** — I could iterate freely during development without burning tokens
- **Learning** — I wanted to understand LLM inference parameters directly (temperature, context window, quantization trade-offs)

The trade-off is latency: 2–5 seconds per inference on GPU, 30+ seconds on CPU. Acceptable for a backend service where you show a loading state.

### All responses route through the LLM

Early versions returned hardcoded strings for greetings, errors, and search results. The responses felt robotic and inconsistent. I refactored so every user input — including edge cases, guard triggers, and empty results — passes through Ollama with a `special_llm_context` dict describing the situation. The model formats the response naturally. This was the single biggest UX improvement.

### Multi-strategy JSON parsing

The LLM sometimes returns valid JSON, sometimes wraps it in markdown code fences, sometimes mixes prose and JSON, sometimes uses single quotes instead of double quotes. Rather than hoping for consistent output, I built explicit fallbacks:
1. Direct `json.loads()` — works ~80% of the time
2. Regex to extract content inside ` ```json ... ``` ` fences
3. Regex cleanup (fix single quotes, trailing commas)
4. Key-value fallback parser for heavily malformed output

If the name field is empty after all four strategies, the system retries with a stricter, shorter prompt. This is a practical lesson: you cannot treat an LLM as a reliable function that returns well-formed data.

### Model size: 7B not 14B

`qwen2.5:14b` (18GB) doesn't fit in a 6GB VRAM RTX 3060 — it falls back to CPU and takes 30+ seconds per response, which kills usability. `qwen2.5:7b-instruct` quantized achieves ~100% GPU utilization and 2–5 second response times. The extraction quality difference is negligible for structured JSON from a well-crafted prompt. Smaller models with better prompts beat larger models with poor prompts.

---

## The Hardest Bug

**The CRUD routing failure (three interacting root causes)**

CRUD commands like "Update John's email to john@new.com" were silently failing — the system would acknowledge the request but nothing changed in the database. Debugging this took the most time.

Root cause 1: The multi-query detector was pattern-matching on the word "and" to detect compound questions. Resume text and update commands both contain "and" constantly. So "Update John's experience and set his role to Senior Engineer" was being split into sub-queries instead of routed as a single update. Fix: explicitly skip multi-query detection for any message that starts with a CRUD verb.

Root cause 2: The employee name lookup in the prompt only ran for `delete` and `remove` commands. `update`, `modify`, and `set` were not included. So the system never identified *which* employee to update. Fix: extend name extraction to all CRUD verbs.

Root cause 3: `create` commands don't reference an existing employee, so the employee-context check always failed for them. The system refused to proceed because it couldn't find an employee to attach context to. Fix: auto-bypass the context check for create/add commands.

Three separate assumptions in three separate code paths, all failing together. The lesson: intent classification at scale is genuinely complex — every query type needs its own detection and routing logic.

---

## Weaknesses — Own Them Before They Ask

| Weakness | What I'd say |
|---|---|
| **No authentication** | Any user can read or delete any employee. JWT with role-based access (admin vs. viewer) is the obvious next step. I omitted it to stay focused on the AI pipeline. |
| **In-memory session store** | Conversation history lives in a Python `dict`. A server restart wipes all sessions. Production fix: Redis with TTL-based expiry. |
| **Duplicate detection disabled** | The function exists but always returns false — I disabled it during development to avoid false positives from name-matching edge cases. Needs tuning before re-enabling. |
| **No streaming** | The LLM response is buffered entirely before sending to the frontend. Users wait 5–30 seconds with no feedback. Server-sent events or WebSocket streaming would fix this. |
| **FAISS + PostgreSQL consistency** | If PostgreSQL writes succeed but FAISS indexing fails (or vice versa), the system ends up in an inconsistent state. This needs a compensating transaction or a saga pattern. I documented it as a known limitation — it's a real distributed systems problem. |

---

## What I'd Do Differently

1. **Streaming first** — The 5–30 second silent wait is the biggest UX problem. I'd wire up server-sent events from day one rather than retrofitting.
2. **Redis for sessions** — In-memory dict was a fast start but it should never reach production. Redis with 24-hour TTL per session_id is straightforward.
3. **Transaction consistency** — FAISS and PostgreSQL writes should be wrapped in a compensating transaction: if FAISS fails, roll back the PostgreSQL insert. I'd use an outbox pattern or at minimum a cleanup job.
4. **Re-enable duplicate detection** — The function is written; it just needs tuning. Fuzzy name matching with a similarity threshold rather than exact matching would fix most false positives.
5. **JWT auth from the start** — Security is not an afterthought. I'd add it in the first week, not the last.

---

## What I Genuinely Learned

- **LLM output is not a reliable function call.** You need defensive parsing, Pydantic validation, and retry logic. Raw LLM JSON fails 10–20% of the time without these guards.
- **Intent classification grows exponentially.** Every new query type (skill search, date range, compound, temporal, null field, seniority, location) needs its own detection path. The chat handler reached 4400+ lines because of this. A proper intent classification layer with trained embeddings would be the scalable solution.
- **Multi-database consistency is a first-class problem.** It's not a "we'll fix it later" issue. Inconsistent state between PostgreSQL and FAISS is a real bug that users will hit.
- **Small models with good prompts beat large models with bad prompts.** Prompt engineering — being explicit about output format, providing examples, setting `temperature=0` — matters more than raw model size on constrained hardware.
- **Privacy-first design has real trade-offs.** Local LLM is the right call for PII, but the latency cost is significant. This is a genuine engineering trade-off, not a free lunch.
