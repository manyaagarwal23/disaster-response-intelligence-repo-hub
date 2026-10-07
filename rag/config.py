import os
from pathlib import Path


# ============================================================
# Central configuration
# ============================================================
# Every path is resolved relative to this file, so scripts work
# no matter which directory they are started from. Each value can
# be overridden with an environment variable (used by Docker/CI).

RAG_DIR = Path(__file__).resolve().parent

PROJECT_DIR = RAG_DIR.parent


# Load secrets such as GROQ_API_KEY from the project's .env file
# (gitignored). Variables already set in the environment win.
def load_env_file(path):

    if not path.is_file():

        return

    for line in path.read_text(encoding="utf-8").splitlines():

        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:

            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env_file(PROJECT_DIR / ".env")


# Ushahidi source code that gets indexed
REPO_PATH = Path(
    os.environ.get("USHAHIDI_PATH", PROJECT_DIR / "ushahidi")
)

# Pinned upstream commit, so ingestion and evaluation are reproducible
USHAHIDI_REPO_URL = "https://github.com/ushahidi/platform.git"

USHAHIDI_COMMIT = "78f81b4be6c9aa7cc0a49d6b9d53cf744f45d382"


# Vector database
CHROMA_PATH = Path(
    os.environ.get("CHROMA_PATH", RAG_DIR / "chroma_db")
)

COLLECTION_NAME = "ushahidi_code"


# Embedding model (BGE expects this instruction in front of queries,
# but NOT in front of the documents being indexed)
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

QUERY_INSTRUCTION = (
    "Represent this sentence for searching relevant passages: "
)


# LLM (Groq). Preview models can be removed by Groq without notice,
# so the model is configurable instead of hardcoded.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")


# Directories of the Ushahidi repository that contain PHP code
INCLUDE_DIRS = {
    "src",
    "app",
    "config",
    "routes",
    "bootstrap",
}

# Directories that contain documentation worth indexing
DOC_DIRS = {
    "docs",
    "src",
}
