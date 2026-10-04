# Disaster Response Intelligence Repo Hub 🚀

An AI-powered intelligence hub for exploring disaster-response repositories (specifically the Ushahidi codebase). It features a state-of-the-art **Retrieval-Augmented Generation (RAG)** pipeline, semantic code search, and a beautiful premium Glassmorphism frontend that generates interactive visual architecture diagrams dynamically.

## ✨ Features

- **Semantic Code Search:** Uses `SentenceTransformers` to semantically match your natural language questions with codebase identifiers and logic.
- **LangChain AI Orchestration:** Powered by **LangChain** and **ChatGroq** (Qwen model) to rerank search results and accurately explain code logic, data flows, and architectures.
- **Premium UI:** A fully custom HTML/CSS/JS frontend featuring a beautiful dark mode glassmorphism aesthetic, sleek animations, custom repository dashboards, and an intuitive layout.
- **Dynamic Visual Architecture:** Automatically generates interactive **Mermaid.js** flowcharts and architecture diagrams based on the retrieved code.
- **Dual Explanation Modes:** View answers as a "Simple Explanation" for beginners or "Technical Details" for experienced developers.
- **Expandable Repository Evidence:** Transparently view the exact source files and code blocks the AI used to generate its answers.
- **CI/CD & Automation:** Features GitHub Actions for automated unit testing and a `sweep.yaml` configuration for automated AI pull requests.

## 🛠 Tech Stack

### Backend
- **Python 3.10**
- **FastAPI** + **Uvicorn**: High-performance web server and REST API.
- **ChromaDB**: Lightweight vector database for storing and querying codebase embeddings.
- **SentenceTransformers**: (`BAAI/bge-base-en-v1.5`) for generating high-quality dense vector embeddings.
- **LangChain & Groq**: Professional LLM orchestration using `langchain_groq` for lightning-fast, highly accurate inference and answer generation.

### Frontend
- **HTML5 / CSS3 / Vanilla JavaScript** (Zero complex framework overhead)
- **Glassmorphism UI**
- **Marked.js**: For rendering markdown text and code blocks.
- **Mermaid.js**: For rendering architecture and workflow diagrams.

### DevOps & Testing
- **GitHub Actions**: Automated CI/CD pipeline (`.github/workflows/ci.yml`).
- **Sweep.dev**: AI development assistant (`sweep.yaml`).
- **Pytest**: Automated unit testing for the AST extraction logic (`rag/tests/`).

## 📂 Project Structure

```text
disaster-response-repo-intelligence/
├── rag/
│   ├── frontend/             # 🎨 UI Layer (Glassmorphism Frontend)
│   ├── tests/                # 🧪 Pytest Unit Tests
│   ├── chroma_db/            # 🗄️ Vector Database (auto-generated)
│   ├── app.py                # 🚀 FastAPI Server Entrypoint
│   ├── rag_api.py            # 🧠 RAG Search & Retrieval Logic
│   ├── llm.py                # 🤖 LangChain/Groq Integration (Reranking)
│   ├── generator.py          # 📝 LangChain/Groq Integration (Answer Generation)
│   ├── ingest.py             # 📥 Database Ingestion Script
│   └── evaluate.py           # 📊 AI Accuracy Evaluation Script
├── .github/workflows/        # ⚙️ GitHub Actions CI/CD configs
├── sweep.yaml                # 🧹 Sweep AI Bot configuration
├── PROJECT_REPORT.md         # 📚 Complete End-to-End Onboarding Report
└── README.md
```

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python 3.9+ installed.

### 2. Installation
Clone the repository and install dependencies inside a virtual environment:
```bash
git clone https://github.com/Depender01/disaster-response-repo-intelligence.git
cd disaster-response-repo-intelligence

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

# Install dependencies
cd rag
pip install -r requirements.txt
```

### 3. Environment Variables
You must set your Groq API key to use the LLM generation:
```bash
# On Windows (PowerShell):
$env:GROQ_API_KEY="your_api_key_here"

# On Mac/Linux:
export GROQ_API_KEY="your_api_key_here"
```

### 4. Running the Application

Ensure you are in the `rag` directory:
```bash
cd rag
```

**Start the Server:**
```bash
python app.py
```
The server will start on `http://127.0.0.1:8000`. Open this URL in your browser to explore the gorgeous Visual AI Interface!

## 🧪 Testing & Evaluation

### Unit Tests (CI/CD)
The project includes a full unit test suite verified via GitHub actions. Run them locally with:
```bash
cd rag
pytest tests/
```

### RAG Evaluation
To evaluate the RAG AI Engine against the ground-truth dataset:
```bash
cd rag
python evaluate.py
```

