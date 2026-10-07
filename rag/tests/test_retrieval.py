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
