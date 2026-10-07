import os

import pytest

import config
from evaluate import first_relevant_rank, load_questions, summarize


def test_first_relevant_rank():
    results = [{"source": "a.php"}, {"source": "b.php"}, {"source": "c.php"}]

    assert first_relevant_rank(results, ["b.php", "c.php"]) == 2
    assert first_relevant_rank(results, ["z.php"]) is None
    # Only the top k results count
    assert first_relevant_rank(results, ["c.php"], k=2) is None


def test_summarize_metrics():
    summary = summarize([1, 2, None, 4])

    assert summary["queries"] == 4
    assert summary["mrr"] == pytest.approx((1 + 0.5 + 0 + 0.25) / 4)
    assert summary["hit@1"] == 25.0
    assert summary["hit@3"] == 50.0
    assert summary["hit@5"] == 75.0


def test_summarize_empty():
    assert summarize([])["mrr"] == 0.0


def test_question_dataset_is_well_formed():
    questions = load_questions()

    assert len(questions) >= 30
    assert len({q["question"] for q in questions}) == len(questions)

    for q in questions:
        assert q["question"].strip()
        assert q["relevant"], q["question"]
        assert all("\\" not in path for path in q["relevant"])


@pytest.mark.skipif(
    not config.REPO_PATH.is_dir(),
    reason="Ushahidi repository not cloned",
)
def test_ground_truth_files_exist_in_ushahidi():
    for q in load_questions():
        for path in q["relevant"]:
            assert os.path.exists(config.REPO_PATH / path), path
