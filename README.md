# Disaster Response Intelligence Repo Hub 🚀

An AI onboarding assistant for the [Ushahidi](https://github.com/ushahidi/platform) crisis-mapping platform. A volunteer developer pulled into a crisis can ask *"where is an incoming SMS report parsed?"* and get the exact files and line numbers, an explanation, and a diagram in seconds. A fast CI pipeline acts as a safety net for rushed changes.

## ✨ Features

- **Semantic code search:** questions are matched against PHP methods, route/config files and Ushahidi's markdown docs, stored as vectors in **ChromaDB**.
- **Hybrid ranking:** vector similarity (BGE embeddings), boosted by exact identifier, code and call-graph matches. An optional **LLM reranker** (Groq via LangChain) then reorders the top 10.
- **Grounded answers:** the LLM answers only from the retrieved code. "Repository Evidence" shows the chunks that were *actually retrieved* (file + line numbers + code), never sources the LLM claims.
- **Works without an API key:** with no `GROQ_API_KEY` set, the app still returns search results. The same happens when the LLM is down or rate limited.
- **Measured, not claimed:** `evaluate.py` scores retrieval against a 33-question ground-truth dataset (MRR, Hit@k).
- **Fast CI:** lint + unit tests in about a minute, then a Docker build with end-to-end tests on a real vector DB.

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Interface | FastAPI web UI (HTML/CSS/JS, Marked + DOMPurify, Mermaid), CLI (`search.py`) |
| Application | `retrieval.py` (hybrid search), `rag_api.py`, `generator.py`, `llm.py` |
| Model | Groq API, `qwen/qwen3.8-27b` by default (set `GROQ_MODEL` to change) |
| Data | ChromaDB (cosine), Sentence Transformers `BAAI/bge-base-en-v1.5`, tree-sitter PHP parser |
| DevOps | GitHub Actions, Docker / Docker Compose, Ruff, Pytest |

## 🔄 How it works

```text
Ushahidi repo (pinned commit)
   │  php_extractor.py  - tree-sitter: methods/functions (+ interfaces, traits, enums),
   │                      whole-file chunks for routes/config, line numbers
   │  chunking.py       - split long methods into overlapping windows, markdown by heading
   ▼
ingestion.py ──► BGE embeddings ──► ChromaDB  (rag/chroma_db, rebuilt on every run)

Question ──► retrieval.py
               1. vector search (30 candidates, BGE query instruction)
               2. hybrid score  = similarity + identifier/code/structural/implementation bonuses
               3. LLM rerank of top 10   (optional, llm.py)
         ──► generator.py: top 3 chunks → LLM → JSON {simple, technical, diagram}
         ──► UI: answer cards + Mermaid diagram + retrieved evidence
```

## 📂 Project Structure

```text
├── rag/
│   ├── app.py               # FastAPI server (/, /api/ask, /healthz)
│   ├── config.py            # All paths & settings (env-overridable)
│   ├── php_extractor.py     # tree-sitter PHP parser
│   ├── chunking.py          # Chunk building, embedding text, metadata
│   ├── ingestion.py         # Builds the ChromaDB vector database
│   ├── retrieval.py         # Shared hybrid search (used by API, CLI, eval)
│   ├── llm.py               # Groq client + LLM reranker
│   ├── generator.py         # Answer generation + JSON parsing
│   ├── rag_api.py           # Retrieval + generation for one question
│   ├── search.py            # CLI search
│   ├── evaluate.py          # Retrieval evaluation (MRR, Hit@k)
│   ├── check_db.py          # Inspect the vector database
│   ├── eval/questions.json  # Ground-truth dataset (33 questions)
│   ├── tests/               # Unit + integration tests, fixture repo
│   └── frontend/            # Web UI
├── Dockerfile, docker-compose.yml
├── .github/workflows/ci.yml
└── sweep.yaml
```

## 🚀 Getting Started (local)

Requires **Python 3.11** (3.10–3.12 work; 3.13+ may lack wheels for some ML packages).

```bash
git clone https://github.com/manyaagarwal23/disaster-response-intelligence-repo-hub.git
cd disaster-response-intelligence-repo-hub
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

cd rag
pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu   # CPU-only, much smaller
pip install -r requirements.txt

# 1. Get Ushahidi at the pinned commit (next to the rag/ folder)
git clone https://github.com/ushahidi/platform.git ../ushahidi
git -C ../ushahidi checkout 78f81b4be6c9aa7cc0a49d6b9d53cf744f45d382

# 2. Build the vector database (~20-40 min on CPU, once)
python ingestion.py
python check_db.py                    # optional sanity check

# 3. (Optional) enable LLM answers - without it you get search results only
export GROQ_API_KEY="gsk_..."         # PowerShell: $env:GROQ_API_KEY="gsk_..."

# 4. Run
python app.py                         # http://localhost:8000
python search.py "where is an incoming SMS report parsed"   # or use the CLI
```

## 🐳 Docker

```bash
echo "GROQ_API_KEY=gsk_..." > .env    # optional
docker compose up --build             # http://localhost:8000
```

On first start, the container fetches Ushahidi at the pinned commit and builds the vector DB into the `rag-data` volume (20–40 min on CPU). Later starts are instant. `/healthz` reports whether the DB is ready.

**Deploying to a VM (e.g. AWS EC2, at least 4 GB RAM):** install Docker, clone this repo, create `.env`, run `docker compose up -d --build`, and open port 8000 in the security group (or put a reverse proxy in front of it).

## 🧪 Testing & Evaluation

```bash
cd rag
pip install -r requirements-dev.txt
ruff check .
pytest                    # fast unit tests (seconds, no ML libraries needed)
pytest -m integration     # end-to-end: real ChromaDB + embedding model (needs requirements.txt)
```

### Retrieval evaluation

```bash
python evaluate.py --output eval/results.json
```

For each question in `eval/questions.json`, the dataset lists the Ushahidi files that contain the answer. The script reports where the first correct file appears in three rankings: **semantic** (vector only), **hybrid**, and **llm** (hybrid + Groq rerank, only when `GROQ_API_KEY` is set).

**Latest results** (2026-10-07, Ushahidi `78f81b4`, 5,698 chunks, Groq `qwen/qwen3.8-27b`):

| Ranking | MRR@10 | Hit@1 | Hit@3 | Hit@5 |
|---|---|---|---|---|
| semantic (vector only) | 0.587 | 48.5% | 63.6% | 72.7% |
| hybrid | 0.614 | 51.5% | 66.7% | 75.8% |
| **hybrid + LLM rerank** (used by the app) | **0.803** | **75.8%** | **81.8%** | **84.8%** |

Weakest area: permission questions. For 3 of them ("Where is the permission to create a post checked?", "What happens when a user without permissions tries to update a post?", "How does the system validate input data before creating a post?"), the right file never reaches the 30 candidates, so no reranker can recover it.

## ⚙️ CI/CD

`.github/workflows/ci.yml` runs on every push and pull request to `main`:

1. **Lint & unit tests** (~1 min): Ruff (bug-catching rules), pytest, and a ground-truth check against the pinned Ushahidi commit.
2. **Docker build & integration tests** (only if 1 passes): builds the production image and runs `pytest -m integration` inside it.

A newer push cancels the outdated run, so feedback stays fast under pressure.

## 📝 Notes for the next phase

- **Added ahead of plan (working, not yet demoed):** Docker/Compose packaging with a CI Docker stage, a PR job that suggests Ruff fixes (Sweep's GitHub bot is discontinued, so `sweep.yaml` is inactive), markdown-doc indexing, and search-only mode without a Groq key.
- **Still to do from the brief:** deploying to AWS/VM, CodiumAI/Qodo-generated regression tests, Sourcegraph integration, and updating the architecture diagrams (they still show Ollama/Streamlit, but the code uses Groq/FastAPI).
