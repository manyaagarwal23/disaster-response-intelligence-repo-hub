FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/huggingface \
    CHROMA_PATH=/data/chroma_db \
    USHAHIDI_PATH=/data/ushahidi \
    ANONYMIZED_TELEMETRY=False

# git is needed to fetch the Ushahidi source on first start
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/rag

# Dependencies first, so code changes don't reinstall them.
# CPU-only torch keeps the image ~1.5 GB smaller than the CUDA build.
COPY rag/requirements.txt rag/requirements-dev.txt ./
RUN pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt \
    && pip install pytest==9.1.1 httpx==0.28.1

# Bake the embedding model into the image (no download at runtime)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5')"

# The model is in the image now: never contact Hugging Face at runtime
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY rag/ ./

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data \
    && chown -R app:app /data /app \
    && chmod +x docker-entrypoint.sh

USER app

# Vector DB + Ushahidi checkout persist here between container restarts
VOLUME /data

EXPOSE 8000

# First start builds the vector DB (can take 20-40 min on CPU)
HEALTHCHECK --interval=30s --timeout=5s --start-period=60m --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

ENTRYPOINT ["./docker-entrypoint.sh"]

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
