# Disaster Response Intelligence Repo Hub
**Complete Project & Architecture Onboarding Report**

Welcome to the team! This document takes you from zero to productive: what the project does, which technologies it uses, and exactly how the code fits together.

---

## 1. What is this project?
The **Disaster Response Intelligence Repo Hub** is an AI-powered developer onboarding tool for **Ushahidi**, a large open-source PHP crisis-mapping platform used during earthquakes, floods and elections.

During a crisis, a volunteer developer may need to ship a fix within hours with almost no context. Instead of reading thousands of lines of PHP, they ask questions in plain English (e.g. *"Where is an incoming SMS report parsed?"*). The tool finds the relevant code (file + line numbers) and explains it, with a diagram where useful.

We achieve this using **Retrieval-Augmented Generation (RAG)**, plus a fast CI pipeline that acts as a safety net for rushed changes.

---

## 2. The Technology Stack

### Backend & AI
*   **Python 3.11:** the language for all backend logic.
*   **FastAPI + Uvicorn:** the web server (`app.py`), serving the UI and the `/api/ask` endpoint.
*   **tree-sitter (PHP grammar):** parses PHP into a syntax tree so we can cut the code at real boundaries (methods, functions, interfaces, traits) instead of arbitrary character counts.
*   **SentenceTransformers (`BAAI/bge-base-en-v1.5`):** turns code and questions into 768-dimensional vectors.
*   **ChromaDB:** a local vector database. It stores the vectors and finds the code closest in *meaning* to a question (cosine similarity).
*   **LangChain + Groq:** calls a cloud LLM (default `qwen/qwen3.8-27b`, configurable with `GROQ_MODEL`) to rerank results and write the final answer. **Optional:** without an API key, the tool still works as a semantic search engine.

### Frontend (UI)
*   **HTML / CSS / vanilla JavaScript** with a glassmorphism theme.
*   **Marked + DOMPurify:** render the LLM's markdown safely.
*   **Mermaid.js:** draws the flowcharts the LLM generates (in strict security mode).

### DevOps & Testing
*   **Pytest:** unit tests (fast, run on every push) and integration tests (real vector DB, run inside Docker).
*   **Ruff:** a linter that catches real bugs (undefined names, unused imports, common pitfalls).
*   **GitHub Actions:** CI that runs lint + unit tests first, then builds the Docker image and runs integration tests.
*   **Docker / Docker Compose:** packages the app for deployment on any VM (e.g. AWS EC2).
*   **Sweep.dev:** configured through `sweep.yaml` (the GitHub app must be installed on the repo for it to act).

---

## 3. End-to-End Workflow (How it Works)

### Phase A: Building the Brain (Ingestion), run once
1.  **Extraction:** `php_extractor.py` parses every PHP file under `src/`, `app/`, `config/`, `routes/` and `bootstrap/`. Each method/function becomes a unit, with its class/interface/trait name, line numbers, the calls it makes, parameter types, and whether it is abstract. Files with no functions (routes, config arrays) become one "file" unit, so they are searchable too.
2.  **Chunking:** `chunking.py` splits very long methods into overlapping 60-line windows (the embedding model only reads ~512 tokens). It also splits Ushahidi's markdown docs by heading.
3.  **Embedding & storage:** `ingestion.py` embeds every chunk and **rebuilds** the ChromaDB collection from scratch, so it never contains stale data.

### Phase B: Answering Questions
1.  **User asks:** the browser sends the question to `/api/ask` (`app.py`).
2.  **Semantic search:** `retrieval.py` embeds the question (with BGE's query instruction) and fetches the 30 closest chunks. If the question names a `.php` file, the search is limited to that file.
3.  **Hybrid ranking:** each candidate's similarity gets small bonuses for exact identifier matches (e.g. the class `UpdateUsecase`), matching words in the code and call graph, and being a real implementation rather than an abstract declaration.
4.  **LLM reranking (optional):** `llm.py` asks the LLM to reorder the top 10. Any result it forgets keeps its place at the end, so nothing is lost.
5.  **Generation:** `generator.py` sends the best 3 chunks to the LLM and parses its JSON answer (summary, technical details, Mermaid diagram).
6.  **Display:** the UI shows the answer cards, the diagram, and the **actually retrieved** code as evidence (file, line numbers, expandable code).

### Phase C: Measuring Quality
`evaluate.py` runs 33 questions from `eval/questions.json`, each with the files known to contain the answer, and reports MRR and Hit@1/3/5 for vector-only search, hybrid ranking, and hybrid + LLM.

---

## 4. File and Folder Breakdown

### 📁 Root Directory
*   `Dockerfile`, `docker-compose.yml`: container build and one-command deployment.
*   `.github/workflows/ci.yml`: the GitHub Actions pipeline.
*   `sweep.yaml`: configuration for the Sweep AI bot.
*   `ushahidi/` (not committed): the Ushahidi source, checked out at the pinned commit in `rag/config.py`.

### 📁 The Core Engine (`rag/`)
*   **`config.py`**: every path and setting in one place, overridable with environment variables.
*   **`app.py`**: the web server. Start it with `python app.py`.
*   **`retrieval.py`**: the search engine, shared by the web app, the CLI and the evaluation.
*   **`llm.py`**: the Groq client and the reranker.
*   **`generator.py`**: builds the answer prompt and parses the LLM's JSON.
*   **`rag_api.py`**: glues retrieval and generation together for one question.
*   **`search.py`**: command-line search (`python search.py "your question"`).
*   **`evaluate.py`** + **`eval/questions.json`**: the retrieval evaluation and its ground truth.
*   **`check_db.py`**: prints what is in the vector database.
*   **`chroma_db/`** (generated): the vector database.

### 📁 Ingestion
*   **`php_extractor.py`**: the tree-sitter PHP parser.
*   **`chunking.py`**: turns parsed units and docs into chunks + metadata.
*   **`ingestion.py`**: runs everything and writes ChromaDB.

### 📁 Frontend (`rag/frontend/`)
*   **`templates/index.html`**: page structure (Chat, Test Dataset, History, Repository, About tabs).
*   **`static/css/style.css`**: styling and glassmorphism effects.
*   **`static/js/script.js`**: calls the API and renders answers, diagrams and evidence safely.

### 📁 Testing (`rag/tests/`)
*   `fixtures/sample_repo/`: a tiny fake Ushahidi repo used by the tests.
*   `test_php_extractor.py`, `test_chunking.py`, `test_retrieval.py`, `test_llm_parsing.py`, `test_app.py`, `test_evaluate.py`: fast unit tests.
*   `test_integration.py`: builds a real vector DB from the fixture repo and checks that questions retrieve the right files (`pytest -m integration`).

---
**You are now fully onboarded. Happy coding!**
