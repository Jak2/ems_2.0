# EMS 2.0 Documentation Index

This folder contains all project documentation organized by category following the project architecture flow.

---

## Folder Structure

```
markdown/
├── 01-overview/          # Project overview and general notes
├── 02-architecture/      # System architecture and design guides
├── 03-setup/             # Environment setup and configuration
├── 04-development/       # Development reports and debugging
├── 05-features/          # Feature documentation and UI/UX
├── 06-backend/           # Backend-specific documentation
├── 07-frontend/          # Frontend-specific documentation
└── 08-interview/         # Interview questions and test cases
```

---

## 01-Overview

| File | Description |
|------|-------------|
| [README.md](01-overview/README.md) | Project overview and introduction |
| [CHANGELOG.md](01-overview/CHANGELOG.md) | Version history and changes |
| [NOTES.md](01-overview/NOTES.md) | Development notes and quick references |

---

## 02-Architecture

| File | Description |
|------|-------------|
| [PROJECT_GUIDE.md](02-architecture/PROJECT_GUIDE.md) | Complete project architecture guide |
| [ENV_ARCHITECTURE.md](02-architecture/ENV_ARCHITECTURE.md) | Environment and system architecture |
| [LLM_GUIDE.md](02-architecture/LLM_GUIDE.md) | LLM integration guide (Ollama, prompts) |

---

## 03-Setup

| File | Description |
|------|-------------|
| [ENV_README.md](03-setup/ENV_README.md) | Environment setup overview |
| [ENV_SETUP_GUIDE.md](03-setup/ENV_SETUP_GUIDE.md) | Step-by-step setup instructions |
| [ENV_IMPLEMENTATION_SUMMARY.md](03-setup/ENV_IMPLEMENTATION_SUMMARY.md) | Implementation details for setup |

---

## 04-Development

| File | Description |
|------|-------------|
| [PROJECT_DEVELOPMENT_REPORT.md](04-development/PROJECT_DEVELOPMENT_REPORT.md) | **Main development report** - All errors, solutions, lessons learned |
| [DATABASE_FIX_SUMMARY.md](04-development/DATABASE_FIX_SUMMARY.md) | Database issues and fixes |
| [IMPLEMENTATION_SUMMARY.md](04-development/IMPLEMENTATION_SUMMARY.md) | Implementation details and decisions |

---

## 05-Features

| File | Description |
|------|-------------|
| [NEW_FEATURES_SUMMARY.md](05-features/NEW_FEATURES_SUMMARY.md) | List of new features implemented |
| [UI_CHANGES_SUMMARY.md](05-features/UI_CHANGES_SUMMARY.md) | UI changes and improvements |
| [UX_IMPROVEMENTS_SUMMARY.md](05-features/UX_IMPROVEMENTS_SUMMARY.md) | UX improvements and user experience |

---

## 06-Backend

| File | Description |
|------|-------------|
| [README.md](06-backend/README.md) | Backend overview |
| [ARCHITECTURE.md](06-backend/ARCHITECTURE.md) | Backend architecture details |
| [README_DIAGNOSTICS.md](06-backend/README_DIAGNOSTICS.md) | Debugging and diagnostics guide |

---

## 07-Frontend

| File | Description |
|------|-------------|
| [README.md](07-frontend/README.md) | Frontend overview |

---

## 08-Interview

| File | Description |
|------|-------------|
| [EMS_PROJECT_QUESTIONS.md](08-interview/EMS_PROJECT_QUESTIONS.md) | EMS 2.0 project-specific interview questions |
| [TECHNOLOGY_QUESTIONS.md](08-interview/TECHNOLOGY_QUESTIONS.md) | LLM, Python, and technology interview questions |
| [HALLUCINATION_TEST_CASES.md](08-interview/HALLUCINATION_TEST_CASES.md) | Edge cases for testing LLM hallucination |

---

## Quick Links

### Getting Started
1. Start with [01-overview/README.md](01-overview/README.md)
2. Follow [03-setup/ENV_SETUP_GUIDE.md](03-setup/ENV_SETUP_GUIDE.md)
3. Understand architecture in [02-architecture/PROJECT_GUIDE.md](02-architecture/PROJECT_GUIDE.md)

### Troubleshooting
- Check [04-development/PROJECT_DEVELOPMENT_REPORT.md](04-development/PROJECT_DEVELOPMENT_REPORT.md) for common errors and solutions

### Architecture Flow
```
User Upload (Frontend)
    ↓
FastAPI Backend
    ↓
PDF Extraction (pdfplumber)
    ↓
LLM Processing (Ollama)
    ↓
Data Storage (PostgreSQL + MongoDB)
    ↓
Chat Interface (RAG + LLM)
```

---

*Last updated: February 1, 2026*
