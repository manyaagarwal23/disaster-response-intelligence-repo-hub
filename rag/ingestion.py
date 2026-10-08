import sys

import config
from chunking import build_embedding_text, build_metadata, collect_chunks


BATCH_SIZE = 500


def main():

    # ============================================================
    # 1. Repository Configuration
    # ============================================================

    repo_path = config.REPO_PATH

    if not repo_path.is_dir():

        print(f"Ushahidi repository not found at: {repo_path}")
        print("Clone it first (pinned commit):")
        print(f"  git clone {config.USHAHIDI_REPO_URL} {repo_path}")
        print(f"  git -C {repo_path} checkout {config.USHAHIDI_COMMIT}")
        print("or set USHAHIDI_PATH to its location.")

        sys.exit(1)

    # ============================================================
    # 2. Find Files and Extract Chunks
    # ============================================================

    php_files, doc_files, chunks = collect_chunks(
        repo_path, config.INCLUDE_DIRS, config.DOC_DIRS
    )

    print("PHP files selected:", len(php_files))
    print("Markdown docs selected:", len(doc_files))
    print("Chunks extracted:", len(chunks))

    if not chunks:

        print("Nothing to index.")

        sys.exit(1)

    # ============================================================
    # 3. Prepare Text for Embeddings
    # ============================================================

    embedding_texts = [
        build_embedding_text(chunk)
        for chunk in chunks
    ]

    # ============================================================
    # 4. Load Embedding Model and Create Embeddings
    # ============================================================

    # Heavy imports are done here so the module can be imported
    # (e.g. by tests) without loading torch.
    from sentence_transformers import SentenceTransformer
    import chromadb

    print("\nLoading embedding model...")

    model = SentenceTransformer(config.EMBEDDING_MODEL)

    print("\nCreating embeddings...")

    all_embeddings = model.encode(
        embedding_texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    # ============================================================
    # 5. Rebuild ChromaDB Collection
    # ============================================================
    # The collection is always rebuilt, so re-running ingestion
    # after the code or the extractor changes never leaves stale
    # vectors behind.

    client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))

    if config.COLLECTION_NAME in [
        c if isinstance(c, str) else c.name
        for c in client.list_collections()
    ]:

        client.delete_collection(config.COLLECTION_NAME)

    collection = client.create_collection(
        name=config.COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": config.EMBEDDING_MODEL,
            "ushahidi_commit": config.USHAHIDI_COMMIT,
        },
    )

    # ============================================================
    # 6. Store Embeddings in Batches
    # ============================================================

    for start in range(0, len(chunks), BATCH_SIZE):

        end = start + BATCH_SIZE

        collection.add(
            ids=[str(i) for i in range(start, min(end, len(chunks)))],
            embeddings=all_embeddings[start:end].tolist(),
            documents=[chunk["content"] for chunk in chunks[start:end]],
            metadatas=[build_metadata(chunk) for chunk in chunks[start:end]],
        )

    # ============================================================
    # 7. Final Information
    # ============================================================

    print("\n" + "-" * 50)
    print("INGESTION COMPLETE")
    print("-" * 50)
    print("PHP files:", len(php_files))
    print("Markdown docs:", len(doc_files))
    print("Chunks:", len(chunks))
    print("Vector dimensions:", len(all_embeddings[0]))
    print("ChromaDB documents:", collection.count())
    print("Database path:", config.CHROMA_PATH)
    print("-" * 50)


if __name__ == "__main__":

    main()
