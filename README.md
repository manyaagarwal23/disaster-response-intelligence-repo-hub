# Disaster Response Intelligence Repo Hub 🚀

An AI-powered intelligence hub for exploring disaster-response repositories (specifically the Ushahidi codebase). It features a state-of-the-art **Retrieval-Augmented Generation (RAG)** pipeline, semantic code search, and a beautiful premium Glassmorphism frontend that generates interactive visual architecture diagrams dynamically.

## ✨ Features

- **Semantic Code Search:** Uses `SentenceTransformers` to semantically match your natural language questions with codebase identifiers and logic.
- **AI Reranking & Generation:** Uses the ultra-fast **Groq API** to rerank search results and accurately explain code logic, data flows, and architectures.
- **Premium UI:** A fully custom HTML/CSS/JS frontend featuring a beautiful dark mode glassmorphism aesthetic, sleek animations, and an intuitive layout.
- **Dynamic Visual Architecture:** Automatically generates interactive **Mermaid.js** flowcharts and architecture diagrams based on the retrieved code.
- **Dual Explanation Modes:** View answers as a "Simple Explanation" for beginners or "Technical Details" for experienced developers.
- **Expandable Repository Evidence:** Transparently view the exact source files and code blocks the AI used to generate its answers.
- **Evaluation Pipeline:** Includes `evaluate.py` to test the RAG engine against a dataset of ground-truth Q&A pairs.

## 🛠 Tech Stack

### Backend
- **Python 3**
- **FastAPI** + **Uvicorn**: High-performance web server and REST API.
- **ChromaDB**: Lightweight vector database for storing and querying codebase embeddings.
- **SentenceTransformers**: (`BAAI/bge-base-en-v1.5`) for generating high-quality dense vector embeddings.
- **Groq API**: Lightning-fast LLM inference for generating final explanations and Mermaid code.

### Frontend
- **HTML5 / CSS3 / Vanilla JavaScript** (Zero complex framework overhead)
- **Glassmorphism UI**
- **Marked.js**: For rendering markdown text and code blocks.
- **Mermaid.js**: For rendering architecture and workflow diagrams.

## 📂 Project Structure

```text
disaster-response-repo-intelligence/
├── rag/
│   ├── frontend/             # 🎨 UI Layer (Glassmorphism Frontend)
│   │   ├── templates/        # index.html
│   │   └── static/           # CSS, JS, and Assets
│   ├── chroma_db/            # 🗄️ Vector Database (auto-generated)
│   ├── app.py                # 🚀 FastAPI Server Entrypoint
│   ├── rag_api.py            # 🧠 RAG Search & Retrieval Logic
│   ├── llm.py                # 🤖 Groq LLM Integration (Reranking)
│   ├── generator.py          # 📝 Groq LLM Integration (Answer Generation)
│   ├── ingest.py             # 📥 Database Ingestion Script
│   └── evaluate.py           # 📊 AI Accuracy Evaluation Script
├── ground_truth.json         # Dataset for evaluation
└── README.md
```

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python 3.9+ installed.

### 2. Installation
Clone the repository and install dependencies inside a virtual environment:
```bash
git clone https://github.com/your-username/disaster-response-repo-intelligence.git
cd disaster-response-repo-intelligence

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

# Install dependencies (ensure requirements.txt exists with FastAPI, ChromaDB, etc)
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

First, navigate to the `rag` directory:
```bash
cd rag
```

**(Optional) Build the Database:**
If you have the Ushahidi source code locally and need to rebuild the vector database:
```bash
python ingest.py
```

**Start the Server:**
```bash
python app.py
```
The server will start on `http://127.0.0.1:8000`. Open this URL in your browser to explore the gorgeous Visual AI Interface!

## 🧪 Evaluation

To run the automated test suite against the AI model:
```bash
cd rag
python evaluate.py
```
This script evaluates the AI's answers against the dataset defined in `ground_truth.json` and outputs performance metrics.
