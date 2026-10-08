import pytest
import retrieval
from retrieval import (
    apply_llm_order,
    build_result,
    detect_filename,
    extract_question_words,
    hybrid_rank,
    normalize_identifier,
)


def metadata(**overrides):
    base = {
        "source": "src/Example.php",
        "filename": "Example.php",
        "namespace": "Ushahidi\\Core",
        "class": "",
        "class_kind": "class",
        "method": "",
        "type": "method",
        "abstract": False,
        "start_line": 1,
        "end_line": 10,
        "calls": "",
        "parameter_types": "",
        "assignments": "",
    }
    base.update(overrides)
    return base


def test_normalize_identifier():
    assert normalize_identifier("FetchDataSourceQueryHandler") == [
        "fetch", "data", "source", "query", "handler",
    ]
    assert normalize_identifier("getSource") == ["get", "source"]
    assert normalize_identifier("SMSSyncController") == ["sms", "sync", "controller"]
    assert normalize_identifier("contact_search-fields") == ["contact", "search", "fields"]
    assert normalize_identifier("Ushahidi\\Core\\Usecase") == ["ushahidi", "core", "usecase"]
    assert normalize_identifier(None) == []


def test_question_words_split_identifiers_and_drop_stopwords():
    words = extract_question_words("Where is verifyEntityLoaded implemented?")

    assert "verifyentityloaded" in words
    assert {"verify", "entity", "loaded", "implemented"} <= words
    assert "where" not in words and "is" not in words


def test_detect_filename():
    assert detect_filename("Show me FetchDataSourceQueryHandler.php") == "FetchDataSourceQueryHandler.php"
    assert detect_filename("where is the map pin logic") is None


def test_exact_identifier_beats_slightly_closer_vector():
    words = extract_question_words("Show me the code for the UpdateUsecase class.")

    unrelated = build_result("...", metadata(source="a.php", **{"class": "X"}, method="other"), 0.20, 1, words)
    exact = build_result(
        "...", metadata(source="UpdateUsecase.php", filename="UpdateUsecase.php", **{"class": "UpdateUsecase"}, method="interact"),
        0.24, 2, words,
    )

    ranked = hybrid_rank([unrelated, exact])

    assert ranked[0]["source"] == "UpdateUsecase.php"
    assert exact["exact_identifier_score"] >= 1


def test_semantic_similarity_still_matters_without_lexical_evidence():
    words = extract_question_words("how are incoming text messages stored")

    far = build_result("...", metadata(source="far.php"), 0.60, 2, words)
    near = build_result("...", metadata(source="near.php"), 0.30, 1, words)

    assert hybrid_rank([far, near])[0]["source"] == "near.php"


def test_implementation_preferred_over_declaration():
    words = extract_question_words("verify entity loaded")

    declaration = build_result("...", metadata(source="decl.php", abstract=True, method="verifyEntityLoaded"), 0.30, 1, words)
    implementation = build_result("...", metadata(source="impl.php", abstract=False, method="verifyEntityLoaded"), 0.30, 2, words)

    assert implementation["implementation_score"] == 1
    assert declaration["implementation_score"] == 0
    assert hybrid_rank([declaration, implementation])[0]["source"] == "impl.php"


def test_apply_llm_order_never_drops_results():
    results = [{"id": i} for i in range(1, 6)]

    # Duplicates, out-of-range numbers and missing positions
    reordered = apply_llm_order(results, [3, 3, 9, 1, 0])

    assert [r["id"] for r in reordered] == [3, 1, 2, 4, 5]


def test_apply_llm_order_with_empty_order_keeps_hybrid_order():
    results = [{"id": i} for i in range(1, 4)]
    assert apply_llm_order(results, []) == results


# ---- lexical (BM25) candidates ----------------------------------------

def test_tokenize_splits_identifiers_and_stems_consistently():
    assert retrieval.tokenize("PostAuthorizer checks permissions") == ["post", "authorizer", "check", "permission"]
    assert retrieval.stem("created") == retrieval.stem("creates") == retrieval.stem("creating") == retrieval.stem("create")
    assert retrieval.tokenize("the is of") == []            # stopwords only


def test_lexical_index_ranks_rare_matching_terms_first():
    index = retrieval.LexicalIndex(
        ["a", "b", "c"],
        [
            "class PostPolicy { function create() { return $this->hasPermission('Manage Posts'); } }",
            "class PostRepository { function get($id) { return $this->db->find($id); } }",
            "class Acl { function hasPermission($user, $permission) { return in_array($permission, $user->permissions); } }",
        ],
    )

    hits = index.search("Where is the permission to create a post checked?", k=2)

    assert [chunk_id for chunk_id, _ in hits] == ["a", "c"]
    assert all(score > 0 for _, score in hits)
    assert index.search("nothing matches zzz") == []


def test_cosine_distance():
    assert retrieval.cosine_distance([1, 0], [1, 0]) == pytest.approx(0.0)
    assert retrieval.cosine_distance([1, 0], [0, 1]) == pytest.approx(1.0)
    assert retrieval.cosine_distance([0, 0], [1, 1]) == 1.0


def test_search_adds_lexical_candidates_the_vector_search_missed(monkeypatch):
    """A chunk the vector search never returns can still reach the hybrid list."""

    class FakeCollection:
        def __init__(self):
            self.docs = {
                "v1": ("File: src/A.php\nClass: A\nMethod: run\n\nreturn 1;", {"source": "src/A.php", "filename": "A.php", "class": "A", "method": "run", "type": "method"}, [1.0, 0.0]),
                "lex": ("File: src/PostPolicy.php\nClass: PostPolicy\nMethod: create\n\nhasPermission('Manage Posts')", {"source": "src/PostPolicy.php", "filename": "PostPolicy.php", "class": "PostPolicy", "method": "create", "type": "method"}, [0.9, 0.4358899]),
            }

        def count(self):
            return 2

        def query(self, query_embeddings, n_results, where=None):
            return {"ids": [["v1"]], "documents": [[self.docs["v1"][0]]], "metadatas": [[self.docs["v1"][1]]], "distances": [[0.1]]}

        def get(self, ids=None, include=None):
            ids = ids or list(self.docs)
            return {
                "ids": ids,
                "documents": [self.docs[i][0] for i in ids],
                "metadatas": [self.docs[i][1] for i in ids],
                "embeddings": [self.docs[i][2] for i in ids],
            }

    monkeypatch.setattr(retrieval.config, "LEXICAL_CANDIDATES", 15)

    retriever = retrieval.Retriever.__new__(retrieval.Retriever)
    retriever.collection = FakeCollection()
    retriever.lexical = retrieval.LexicalIndex(["v1", "lex"], [retriever.collection.docs["v1"][0], retriever.collection.docs["lex"][0]])
    retriever.embed_question = lambda question: [1.0, 0.0]

    result = retriever.search("Where is the permission to create a post checked?", use_llm=False)

    assert [r["id"] for r in result["semantic"]] == ["v1"]                  # vector list untouched
    assert {r["id"] for r in result["hybrid"]} == {"v1", "lex"}            # keyword hit merged in
    lexical = next(r for r in result["hybrid"] if r["id"] == "lex")
    assert lexical["lexical"] is True and lexical["semantic_rank"] == retrieval.CANDIDATES + 1
    assert lexical["distance"] == pytest.approx(0.1, abs=1e-6)              # real cosine distance
    assert result["hybrid"][0]["id"] == "lex"                               # equal distance: identifier bonuses win


def test_lexical_candidates_are_off_by_default(monkeypatch):
    monkeypatch.setattr(retrieval.config, "LEXICAL_CANDIDATES", 0)

    class Collection:
        def query(self, **kwargs):
            return {"ids": [["v1"]], "documents": [["x"]], "metadatas": [[{"source": "a.php"}]], "distances": [[0.2]]}

        def get(self, **kwargs):
            raise AssertionError("the keyword index must not be used when disabled")

    retriever = retrieval.Retriever.__new__(retrieval.Retriever)
    retriever.collection = Collection()
    retriever.lexical = None
    retriever.embed_question = lambda question: [1.0]

    assert [r["id"] for r in retriever.search("anything", use_llm=False)["hybrid"]] == ["v1"]
