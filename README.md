# MoinSystems AI DevFlow Copilot

Local-first, zero-paid-API Generative AI product that converts unstructured client briefs and meeting notes into schema-validated, reviewable software engineering artifacts.

## Architecture (Day 1 Milestone)
- **Frontend (`ui/streamlit_app.py`):** Streamlit UI for submitting requirements, viewing structured drafts, and enforcing human-review indicators[cite: 1, 2].
- **Backend (`app/api/routes.py`):** FastAPI service separating UI from AI orchestration and SQLite persistence[cite: 1, 2].
- **Local GenAI (`app/services/ollama_service.py`):** Ollama adapter running `qwen3:4b` with strict Pydantic JSON schema enforcement (`think=False`, `temperature=0.1`)[cite: 1, 2].
- **Prompts (`app/prompts/spec_v1.txt`):** Versioned prompt enforcing anti-hallucination and explicit `assumptions` vs `open_questions` separation[cite: 1, 2].
- **Persistence (`devflow.db`):** SQLite database tracking `projects`, `input_documents`, `generation_runs`, and `artifacts`.

## Setup & Run Instructions
1. Install [Ollama](https://ollama.com/) and pull the local model[cite: 1, 2]:
   ```powershell
   ollama pull qwen3:4b