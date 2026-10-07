"""
Shared retrieval logic used by the web API (rag_api.py), the CLI
(search.py) and the evaluation (evaluate.py), so all three measure
and serve exactly the same pipeline.

The scoring helpers at the top are pure functions with no heavy
dependencies, so they can be unit-tested without ChromaDB or torch.
"""

import math
import re
import threading
import time

import config


STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were",
    "how", "what", "where", "when", "why", "which",
    "who", "does", "do", "did", "can", "could",
    "would", "should", "this", "that", "these",
    "those", "to", "of", "in", "on", "for", "from",
    "with", "and", "or", "as", "by", "me", "show",
    "it", "be", "its", "there", "explain",
}

# Weights of the hybrid score. Semantic similarity (0..1) is the
# base; lexical evidence adds a bonus on top of it. Tuned on the
# evaluation set in evaluate.py - re-run it after changing these.
WEIGHTS = {
    "exact_identifier": 0.10,
    "identifier": 0.03,
    "code": 0.01,
    "structural": 0.01,
    "implementation": 0.02,
}

CANDIDATES = 30

RERANK_TOP_K = config.RERANK_TOP_K


# ============================================================
# 1. Question Analysis
# ============================================================

def normalize_identifier(identifier):
    """
    Split a programming identifier into lowercase words:
    "FetchDataSourceQuery" -> ["fetch", "data", "source", "query"]
    """

    identifier = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", identifier or "")

    identifier = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", identifier)

    identifier = re.sub(r"[_\-\\/.:]", " ", identifier)

    return identifier.lower().split()


def extract_question_words(question):

    words = set()

    for word in re.findall(r"[a-zA-Z0-9_]+", question):

        if word.lower() in STOPWORDS:

            continue

        words.add(word.lower())

        words.update(
            token
            for token in normalize_identifier(word)
            if token not in STOPWORDS
        )

    return words


def detect_filename(question):

    match = re.search(r"\b[\w.-]+\.php\b", question, re.IGNORECASE)

    return match.group(0) if match else None


# ============================================================
# 2. Hybrid Scoring
# ============================================================

def normalize_code(text):

    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text or "")

    return text.replace("_", " ").lower()


def score_candidate(question_words, document, metadata, distance):

    identifiers = [
        metadata.get("filename", "").removesuffix(".php"),
        metadata.get("class", ""),
        metadata.get("method", ""),
    ]

    identifier_words = set()

    for identifier in identifiers + [metadata.get("namespace", "")]:

        identifier_words.update(normalize_identifier(identifier))

    identifier_matches = question_words & identifier_words

    # An identifier counts as an exact match when every one of its
    # words appears in the question ("UpdateUsecase" <- "update usecase")
    exact_identifier_score = sum(
        1
        for identifier in identifiers
        if normalize_identifier(identifier)
        and all(
            token in question_words
            for token in normalize_identifier(identifier)
        )
    )

    normalized_code = normalize_code(document)

    code_matches = sorted({
        word
        for word in question_words
        if len(word) >= 3 and word in normalized_code
    })

    normalized_structural = normalize_code(" ".join([
        metadata.get("calls", ""),
        metadata.get("parameter_types", ""),
        metadata.get("assignments", ""),
    ]))

    structural_matches = sorted({
        word
        for word in question_words
        if len(word) >= 3 and word in normalized_structural
    })

    implementation_score = (
        1
        if metadata.get("type") in ("method", "function")
        and metadata.get("abstract") is False
        else 0
    )

    # Cosine distance -> similarity
    similarity = 1.0 - distance

    score = (
        similarity
        + WEIGHTS["exact_identifier"] * exact_identifier_score
        + WEIGHTS["identifier"] * len(identifier_matches)
        + WEIGHTS["code"] * len(code_matches)
        + WEIGHTS["structural"] * len(structural_matches)
        + WEIGHTS["implementation"] * implementation_score
    )

    return {
        "score": score,
        "similarity": similarity,
        "distance": distance,
        "exact_identifier_score": exact_identifier_score,
        "identifier_matches": sorted(identifier_matches),
        "code_matches": code_matches,
        "structural_matches": structural_matches,
        "implementation_score": implementation_score,
    }


def build_result(document, metadata, distance, semantic_rank, question_words):

    result = {
        "semantic_rank": semantic_rank,
        "source": metadata.get("source", ""),
        "filename": metadata.get("filename", ""),
        "namespace": metadata.get("namespace", ""),
        "class": metadata.get("class", ""),
        "class_kind": metadata.get("class_kind", ""),
        "method": metadata.get("method", ""),
        "type": metadata.get("type", ""),
        "start_line": metadata.get("start_line"),
        "end_line": metadata.get("end_line"),
        "content": document,
    }

    result.update(score_candidate(question_words, document, metadata, distance))

    return result


def hybrid_rank(results):

    return sorted(results, key=lambda r: (-r["score"], r["distance"]))


def apply_llm_order(results, order):
    """
    Reorder results by a list of 1-based positions returned by the
    LLM reranker. Positions the LLM forgot keep their hybrid order
    at the end, so a sloppy LLM answer can never drop results.
    """

    seen = []

    for position in order:

        if 1 <= position <= len(results) and position not in seen:

            seen.append(position)

    remaining = [
        position
        for position in range(1, len(results) + 1)
        if position not in seen
    ]

    return [results[position - 1] for position in seen + remaining]



# ============================================================
# 2b. Lexical index (BM25): candidates the vector search misses
# ============================================================
#
# Vector search alone misses some questions entirely: "Where is the
# permission to create a post checked?" never surfaces PostPolicy or
# PostAuthorizer among the 30 nearest chunks. A small in-memory BM25
# index over the same chunk texts adds the best keyword matches as
# extra candidates. Each extra gets its real cosine distance to the
# question and goes through the same hybrid scoring, so nothing is
# ever ranked by keywords alone.

LEXICAL_CANDIDATES = 15   # default k for LexicalIndex.search; the live path uses config.LEXICAL_CANDIDATES

BM25_K1 = 1.2

BM25_B = 0.75


def stem(word):
    """
    Crude but consistent stemmer, applied to documents and questions
    alike: permissions/permission -> permission, created/creates/
    creating/create -> creat, checked/checks -> check.
    """

    for suffix in ("ing", "ed", "es", "s"):

        if word.endswith(suffix) and len(word) - len(suffix) >= 3:

            word = word[: -len(suffix)]

            break

    if word.endswith("e") and len(word) > 4:

        word = word[:-1]

    return word


def tokenize(text):
    """
    Lowercased, stemmed word tokens of code or prose. Identifiers are
    split into their words first (PostAuthorizer -> post, authorizer),
    stopwords and very short tokens are dropped.
    """

    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text or "")

    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)

    return [
        stem(word)
        for word in re.findall(r"[a-z][a-z0-9]*", text.lower())
        if len(word) >= 3 and word not in STOPWORDS
    ]


def cosine_distance(a, b):

    dot = sum(x * y for x, y in zip(a, b, strict=True))

    norm_a = math.sqrt(sum(x * x for x in a))

    norm_b = math.sqrt(sum(y * y for y in b))

    return 1.0 - dot / (norm_a * norm_b) if norm_a and norm_b else 1.0


class LexicalIndex:
    """BM25 over chunk texts, built once in memory from the collection."""

    def __init__(self, ids, documents):

        self.ids = list(ids)

        self.lengths = []

        self.postings = {}

        for index, text in enumerate(documents):

            counts = {}

            for token in tokenize(text):

                counts[token] = counts.get(token, 0) + 1

            self.lengths.append(sum(counts.values()))

            for term, frequency in counts.items():

                self.postings.setdefault(term, []).append((index, frequency))

        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 1.0

    def search(self, text, k=LEXICAL_CANDIDATES):
        """Top-k (chunk id, BM25 score) pairs for a question."""

        scores = {}

        total = len(self.ids)

        for term in set(tokenize(text)):

            posting = self.postings.get(term)

            if not posting:

                continue

            idf = math.log(1 + (total - len(posting) + 0.5) / (len(posting) + 0.5))

            for index, frequency in posting:

                norm = BM25_K1 * (1 - BM25_B + BM25_B * self.lengths[index] / self.avg_length)

                scores[index] = scores.get(index, 0.0) + idf * frequency * (BM25_K1 + 1) / (frequency + norm)

        best = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]

        return [(self.ids[index], score) for index, score in best]


# ============================================================
# 3. Retriever (ChromaDB + embedding model)
# ============================================================

class DatabaseNotReadyError(RuntimeError):
    pass


class Retriever:

    def __init__(self):

        import chromadb
        from sentence_transformers import SentenceTransformer

        self.client = chromadb.PersistentClient(path=str(config.CHROMA_PATH))

        self.connect()

        self.model = SentenceTransformer(config.EMBEDDING_MODEL)

    def connect(self):

        try:

            self.collection = self.client.get_collection(name=config.COLLECTION_NAME)

        except Exception as error:

            raise DatabaseNotReadyError(
                f"Vector database '{config.COLLECTION_NAME}' not found at "
                f"{config.CHROMA_PATH}. Build it with: python ingestion.py"
            ) from error

        if self.collection.count() == 0:

            raise DatabaseNotReadyError(
                "Vector database is empty. Build it with: python ingestion.py"
            )

        # Optional keyword index (config.LEXICAL_CANDIDATES > 0); the
        # retriever works without it
        self.lexical = None

        if config.LEXICAL_CANDIDATES > 0:

            try:

                rows = self.collection.get(include=["documents"])

                self.lexical = LexicalIndex(rows["ids"], rows["documents"])

            except Exception as error:

                print(f"Lexical index unavailable ({error}); using vector search only.")

    def query(self, **kwargs):
        """
        Query the collection. ingestion.py rebuilds the collection, which
        invalidates the handle a running server holds - reconnect once
        instead of failing every request until a restart.
        """

        try:

            return self.collection.query(**kwargs)

        except Exception as error:

            if "does not exist" not in str(error):

                raise

            self.connect()

            return self.collection.query(**kwargs)

    def stats(self):
        """Counts of what is indexed, computed once and cached."""

        if getattr(self, "_stats", None) is None:

            metadata = self.collection.get(include=["metadatas"])["metadatas"]

            by_type = {}

            for item in metadata:

                by_type[item.get("type", "?")] = by_type.get(item.get("type", "?"), 0) + 1

            self._stats = {
                "chunks": len(metadata),
                "by_type": by_type,
                "files": len({item.get("source") for item in metadata}),
                "embedding_model": config.EMBEDDING_MODEL,
                "ushahidi_commit": (self.collection.metadata or {}).get("ushahidi_commit", config.USHAHIDI_COMMIT),
            }

        return self._stats

    def embed_question(self, question):

        return self.model.encode(
            config.QUERY_INSTRUCTION + question,
            normalize_embeddings=True,
        ).tolist()

    def semantic_search(self, question, n_results=CANDIDATES, embedding=None):
        """
        Pure vector search, ordered by cosine distance.
        A filename mentioned in the question restricts the search
        to that file (falling back to the whole repo if no match).
        """

        question_words = extract_question_words(question)

        if embedding is None:

            embedding = self.embed_question(question)

        filename = detect_filename(question)

        raw = None

        if filename:

            raw = self.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where={"filename": filename},
            )

            if not raw["documents"][0]:

                raw = None

        if raw is None:

            raw = self.query(
                query_embeddings=[embedding],
                n_results=n_results,
            )

        results = []

        for rank, (chunk_id, document, metadata, distance) in enumerate(
            zip(raw["ids"][0], raw["documents"][0], raw["metadatas"][0], raw["distances"][0], strict=True),
            1,
        ):

            result = build_result(document, metadata, distance, rank, question_words)

            result["id"] = chunk_id

            results.append(result)

        return results

    def lexical_candidates(self, question, embedding, exclude_ids, k=LEXICAL_CANDIDATES):
        """
        Best BM25 keyword matches that the vector search did not return,
        as full results with their real cosine distance to the question.
        """

        index = getattr(self, "lexical", None)

        if index is None:

            return []

        hits = [chunk_id for chunk_id, _ in index.search(question, k + len(exclude_ids)) if chunk_id not in exclude_ids][:k]

        if not hits:

            return []

        rows = self.collection.get(ids=hits, include=["documents", "metadatas", "embeddings"])

        question_words = extract_question_words(question)

        results = []

        for position, (chunk_id, document, metadata, vector) in enumerate(
            zip(rows["ids"], rows["documents"], rows["metadatas"], rows["embeddings"], strict=True),
            1,
        ):

            distance = cosine_distance(embedding, [float(x) for x in vector])

            result = build_result(document, metadata, distance, CANDIDATES + position, question_words)

            result["id"] = chunk_id

            result["lexical"] = True

            results.append(result)

        return results

    def search(self, question, use_llm=True):
        """
        Full pipeline. Returns all three orderings so the evaluation
        can compare them:
          semantic - vector search only
          hybrid   - vector + lexical/structural scoring
          final    - hybrid top-k reordered by the LLM (if available)
        """

        started = time.perf_counter()

        embedding = self.embed_question(question)

        semantic = self.semantic_search(question, embedding=embedding)

        # Optional keyword matches the vector search missed, scored the same way
        extras = []

        if config.LEXICAL_CANDIDATES > 0:

            extras = self.lexical_candidates(question, embedding, {r.get("id") for r in semantic}, k=config.LEXICAL_CANDIDATES)

        hybrid = hybrid_rank(semantic + extras)

        retrieval_ms = round((time.perf_counter() - started) * 1000)

        final = hybrid

        llm_used = False

        rerank_ms = 0

        if use_llm:

            from llm import rerank

            top = hybrid[:RERANK_TOP_K]

            rerank_started = time.perf_counter()

            order = rerank(question, top)

            rerank_ms = round((time.perf_counter() - rerank_started) * 1000)

            if order is not None:

                final = apply_llm_order(top, order) + hybrid[RERANK_TOP_K:]

                llm_used = True

        return {
            "semantic": semantic,
            "hybrid": hybrid,
            "final": final,
            "llm_used": llm_used,
            "timings": {"retrieval_ms": retrieval_ms, "rerank_ms": rerank_ms},
        }


_retriever = None

_retriever_lock = threading.Lock()


def get_retriever():
    """
    Load the database and model once and reuse them. The lock makes
    concurrent first requests (and the start-up warm-up) wait for one
    load instead of each building their own retriever.
    """

    global _retriever

    if _retriever is None:

        with _retriever_lock:

            if _retriever is None:

                _retriever = Retriever()

    return _retriever
