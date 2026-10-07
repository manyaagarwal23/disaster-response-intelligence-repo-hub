# Disaster Response Intelligence Repo Hub
**Complete Project & Architecture Onboarding Report**

Welcome to the team! This document takes you from zero to productive: what the project does, which technologies it uses, and exactly how the code fits together.

---

## 1. What is this project?
The **Disaster Response Intelligence Repo Hub** is an AI-powered developer onboarding tool for **Ushahidi**, a large open-source PHP crisis-mapping platform used during earthquakes, floods and elections.

During a crisis, a volunteer developer may need to ship a fix within hours with almost no context. Instead of reading thousands of lines of PHP, they ask questions in plain English (e.g. *"Where is an incoming SMS report parsed?"*). The tool finds the relevant code (file + line numbers), explains it, draws a diagram, and links to the file on GitHub. For quick lookups there is an instant **Code Search** that needs no AI at all.

We achieve this using **Retrieval-Augmented Generation (RAG)**, plus a fast CI pipeline with an AI safety net for rushed changes.

---

## 2. The Technology Stack

### Backend & AI
*   **Python 3.11:** the language for all backend logic.
*   **FastAPI + Uvicorn:** the web server (`app.py`) serving the UI and the API (`/api/ask`, `/api/search`, `/api/stats`, `/healthz`).
*   **tree-sitter (PHP grammar):** parses PHP into a syntax tree so we can cut the code at real boundaries (methods, functions, interfaces, traits) instead of arbitrary character counts.
*   **SentenceTransformers (`BAAI/bge-base-en-v1.5`):** turns code and questions into 768-dimensional vectors.
*   **ChromaDB:** a local vector database. It stores the vectors and finds the code closest in *meaning* to a question (cosine similarity).
*   **LangChain + Groq:** calls a cloud LLM (default `qwen/qwen3.8-27b`, configurable with `GROQ_MODEL`) to rerank results and write the final answer. **Optional:** without an API key, or when Groq is rate-limited, the tool still works as a semantic search engine.

### Frontend (UI)
*   **HTML / CSS / vanilla JavaScript**, the "Beacon" theme (dark by default, light theme toggle in the sidebar), with highlight.js for syntax-highlighted evidence.
*   **Marked + DOMPurify:** render the LLM's markdown safely.
*   **Mermaid.js:** draws the flowcharts the LLM generates (strict security mode), with a backup diagram built from the retrieved code if the LLM's diagram fails.

### DevOps & Testing
*   **Pytest:** unit tests (fast, run on every push), auto-generated regression tests, and integration tests (real vector DB, run inside Docker).
*   **Ruff:** a linter that catches real bugs (undefined names, unused imports, common pitfalls).
*   **GitHub Actions:** CI that runs lint + unit tests first, then an AI safety net on pull requests, then builds the Docker image and runs integration tests.
*   **Docker / Docker Compose:** packages the app for deployment on any VM (e.g. AWS EC2); `deploy/install_on_ubuntu.sh` sets up a fresh machine.
*   **Groq-powered tools:** `tools/ai_review.py` (reviews a diff for risky patterns) and `tools/generate_tests.py` (writes regression tests for a module and keeps only those that pass).

---

## 3. End-to-End Workflow (How it Works)

### Phase A: Building the Brain (Ingestion), run once
1.  **Extraction:** `php_extractor.py` parses every PHP file under `src/`, `app/`, `config/`, `routes/` and `bootstrap/`. Each method/function becomes a unit, with its class/interface/trait name, line numbers, the calls it makes, parameter types, and whether it is abstract. Files with no functions (routes, config arrays) become one "file" unit, so they are searchable too.
2.  **Chunking:** `chunking.py` splits very long methods into overlapping 60-line windows (the embedding model only reads ~512 tokens). It also splits Ushahidi's markdown docs by heading.
3.  **Embedding & storage:** `ingestion.py` embeds every chunk and **rebuilds** the ChromaDB collection from scratch (5,698 chunks), so it never contains stale data.

### Phase B: Answering Questions
1.  **User asks:** the browser sends the question to `/api/ask` (`app.py`).
2.  **Semantic search:** `retrieval.py` embeds the question (with BGE's query instruction) and fetches the 30 closest chunks. If the question names a `.php` file, the search is limited to that file.
3.  **Hybrid ranking:** each candidate's similarity gets small bonuses for exact identifier matches (e.g. the class `UpdateUsecase`), matching words in the code and call graph, and being a real implementation rather than an abstract declaration. **Code Search stops here** and returns the hits in well under a second.
4.  **LLM reranking (optional):** `llm.py` asks the LLM to reorder the top candidates (`RERANK_TOP_K` in `config.py`, with a short code preview of each). Any result it forgets keeps its place at the end, so nothing is lost. Short Groq rate-limit pauses are waited out automatically.
5.  **Generation:** `generator.py` sends the best 3 chunks to the LLM and parses its JSON answer (summary, technical details, Mermaid diagram).
6.  **Display:** the UI shows the answer cards, the diagram (or a backup diagram built from the retrieved code), timings, and the **actually retrieved** code as evidence (file, line numbers, expandable code, GitHub link). History is kept in the browser across refreshes.

### Phase C: Measuring Quality
`evaluate.py` runs 33 questions from `eval/questions.json`, each with the files known to contain the answer, and reports MRR, Hit@1/3/5 and latency for vector-only search, hybrid ranking, and hybrid + LLM. Every run is saved under `reports/eval/`.

### Phase D: Protecting Rushed Changes
On every push, GitHub Actions lints and runs the unit tests in about a minute. On pull requests, `tools/ai_review.py` reviews the diff for bugs, security holes and removed tests and comments on the PR, while `tools/generate_tests.py` writes regression tests for the changed modules. A Docker build with integration tests runs last.

---

## 4. File and Folder Breakdown

### 📁 Root Directory
*   `Dockerfile`, `docker-compose.yml`: container build and one-command deployment.
*   `.github/workflows/ci.yml`: the GitHub Actions pipeline.
*   `deploy/`: `install_on_ubuntu.sh` (EC2 user-data or manual) and deployment notes.
*   `scripts/smoke_test_compose.sh`: proves the one-command start from scratch; writes `reports/compose-smoke-<date>.log`.
*   `reports/`: health checks, evaluation runs, ingestion and smoke-test logs, AI reviews, generated-test reports. Outputs are always saved here, never only on screen.
*   `docs/screenshots/`: UI screenshots before and after the redesign.
*   `docs/slides/`: the team deck (v4 = v3 with the new UI screenshot on slide 10).
*   `sweep.yaml`: configuration for the (discontinued) Sweep bot; kept for reference.
*   `ushahidi/` (not committed): the Ushahidi source, checked out at the pinned commit in `rag/config.py`.

### 📁 The Core Engine (`rag/`)
*   **`config.py`**: every path and setting in one place, overridable with environment variables; loads `.env`.
*   **`app.py`**: the web server. Start it with `python app.py`.
*   **`retrieval.py`**: the search engine, shared by the web app, the CLI and the evaluation; records timings. Also holds an optional BM25 keyword index (`LEXICAL_CANDIDATES`, off by default: measured, no gain).
*   **`llm.py`**: the Groq client, rate-limit-aware retries, and the reranker.
*   **`generator.py`**: builds the answer prompt and parses the LLM's JSON.
*   **`rag_api.py`**: glues retrieval and generation together; also serves Code Search and stats.
*   **`search.py`**: command-line search (`python search.py "your question"`).
*   **`evaluate.py`** + **`eval/questions.json`**: the retrieval evaluation and its ground truth.
*   **`check_db.py`**: prints what is in the vector database.
*   **`chroma_db/`** (generated): the vector database.

### 📁 Ingestion
*   **`php_extractor.py`**: the tree-sitter PHP parser.
*   **`chunking.py`**: turns parsed units and docs into chunks + metadata.
*   **`ingestion.py`**: runs everything and writes ChromaDB.

### 📁 Tools (`rag/tools/`)
*   **`ai_review.py`**: Sweep-style AI review of a git diff → Markdown report / PR comment.
*   **`generate_tests.py`**: CodiumAI-style regression-test generator → `tests/generated/`.

### 📁 Frontend (`rag/frontend/`)
*   **`templates/index.html`**: page structure (Ask, Code Search, Test Dataset, History, Repository, About tabs; live status panel).
*   **`static/css/style.css`**: the theme.
*   **`static/js/script.js`**: calls the API and renders answers, diagrams, evidence, search results and history safely.

### 📁 Testing (`rag/tests/`)
*   `fixtures/sample_repo/`: a tiny fake Ushahidi repo used by the tests.
*   `test_php_extractor.py`, `test_chunking.py`, `test_retrieval.py`, `test_llm_parsing.py`, `test_app.py`, `test_rag_api.py`, `test_evaluate.py`: fast unit tests.
*   `generated/`: regression tests written by `tools/generate_tests.py` (only tests that passed at generation time are kept).
*   `test_integration.py`: builds a real vector DB from the fixture repo and checks that questions retrieve the right files (`pytest -m integration`).

---
**You are now fully onboarded. Happy coding!**
