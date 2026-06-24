# Design Spec: EMS 2.0 Project Report

**Date**: 2026-06-23  
**Type**: Documentation — Project Report  
**Output file**: `EMS_2.0_PROJECT_REPORT.md` (project root)

---

## Purpose

Produce a comprehensive project report for EMS 2.0 that answers:
- **What** is this project?
- **Why** was it built?
- **How** was it built (architecture, stack, design decisions)?

Audience: mixed — technical (developers, reviewers) and semi-technical (portfolio readers, interviewers).

---

## Report Structure

### 1. Executive Summary
One-paragraph plain-English summary. What EMS 2.0 is, what problem it solves, what makes it distinct (local LLM, no-forms chatbot interface).

### 2. Motivation & Learning Goals
- Problem being solved: traditional EMS systems require manual data entry
- Learning goals: local LLM integration, RAG, vector stores, multi-DB architecture, NLP UI
- Context: personal learning project under `my_learning_projects/`

### 3. Tech Stack
Table of all technologies with their role in the system.

### 4. System Architecture & Data Flows
- CV Upload Flow (PDF → GridFS → LLM → PostgreSQL → FAISS → Job polling)
- Chat/Query Flow (prompt → intent classification → employee resolution → LLM → response)
- CRUD Operations (NL parsing → validation → DB operations → LLM-formatted response)
- Service Communication Map

### 5. Key Features
- Resume Upload & Auto-Extraction (PDF + OCR for images)
- Natural Language CRUD (create/read/update/delete via chat)
- RAG with FAISS (semantic employee search)
- Session Memory & Pronoun Resolution
- Anti-Hallucination Guards (5 guards)
- Multi-Query Decomposition

### 6. Validation & Robustness Architecture (7 Layers)
Summarise the layered defence: Input Validation → Duplicate Detection → Intent Classification → Identity Verification → Anti-Hallucination Guards → LLM Processing → DB Operations

### 7. Challenges & Solutions
Document the major bugs fixed (BUG-001 through BUG-005) and engineering decisions made.

### 8. Known Limitations & Future Improvements
Be honest about what's partial or disabled (duplicate detection, no auth, no rate limiting).

---

## Tone & Style
- Factual, direct — no filler
- Technical terms used but briefly explained
- Code snippets only where they clarify a concept
- Diagrams reproduced from existing docs (ASCII)

---

## Source Files Used
- `README.md` — flows, stack, quick start
- `PROJECT_SUMMARY.md` — interview-ready summary, challenges solved
- `ARCHITECTURE_CHECKS.md` — 7-layer validation, bugs, changelog
- `ROBUSTNESS_CHANGES.md` — specific improvements made
- `AI_CONSULTATION_PROMPT.md` — edge cases and learning context
- `backend/app/main.py` — source of truth for all logic
- `backend/app/db/models.py` — Employee model (22+ fields)
- `backend/app/services/llm_adapter.py` — Ollama HTTP + CLI adapter
