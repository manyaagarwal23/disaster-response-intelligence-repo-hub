import chunking
from chunking import (
    build_embedding_text,
    build_metadata,
    collect_chunks,
    markdown_chunks_from_text,
    php_chunks_from_code,
    split_into_windows,
)


INCLUDE_DIRS = {"src", "routes"}

DOC_DIRS = {"src"}


def test_short_content_is_one_window():
    assert split_into_windows("a\nb\nc", 10) == [("a\nb\nc", 10, 12)]


def test_long_content_is_split_with_overlap():
    lines = [f"line {i}" for i in range(1, 151)]
    windows = split_into_windows("\n".join(lines), 1)

    # Every line is covered and windows overlap
    covered = set()
    for text, first, last in windows:
        assert len(text.split("\n")) <= chunking.MAX_CHUNK_LINES
        assert text.split("\n")[0] == f"line {first}"
        assert text.split("\n")[-1] == f"line {last}"
        covered.update(range(first, last + 1))
    assert covered == set(range(1, 151))
    assert windows[1][1] <= windows[0][2]


def test_long_method_is_split_into_parts():
    body = "\n".join(f"        $x{i} = {i};" for i in range(100))
    code = f"<?php\nclass Big {{\n    public function huge()\n    {{\n{body}\n    }}\n}}\n"

    chunks = php_chunks_from_code(code, "src/Big.php", "Big.php")

    assert len(chunks) > 1
    assert all(c["method"] == "huge" and c["class"] == "Big" for c in chunks)
    assert [c["part"] for c in chunks] == list(range(1, len(chunks) + 1))
    assert all(c["parts"] == len(chunks) for c in chunks)


def test_markdown_split_by_heading(read_fixture):
    chunks = markdown_chunks_from_text(
        read_fixture("src/Ushahidi/DataSource/data-flows.md"),
        "src/Ushahidi/DataSource/data-flows.md",
        "data-flows.md",
    )

    headings = [c["method"] for c in chunks]
    assert headings == ["Data source flows", "Incoming SMS", "Outgoing messages"]
    assert all(c["type"] == "doc" for c in chunks)
    assert "Twilio" in chunks[1]["content"]
    assert chunks[1]["start_line"] == 5


def test_metadata_only_contains_chroma_compatible_values(read_fixture):
    chunks = php_chunks_from_code(
        read_fixture("src/Ushahidi/DataSource/Twilio/TwilioController.php"),
        "src/Ushahidi/DataSource/Twilio/TwilioController.php",
        "TwilioController.php",
    )

    for chunk in chunks:
        metadata = build_metadata(chunk)
        for value in metadata.values():
            assert isinstance(value, (str, int, float, bool))
        # Needed by the retriever's implementation signal
        assert metadata["abstract"] is False
        assert metadata["start_line"] >= 1


def test_embedding_text_contains_identifiers(read_fixture):
    chunks = php_chunks_from_code(
        read_fixture("src/Ushahidi/Contracts/EntityExists.php"),
        "src/Ushahidi/Contracts/EntityExists.php",
        "EntityExists.php",
    )

    text = build_embedding_text(chunks[0])
    assert "Interface: EntityExists" in text
    assert "Method: exists" in text
    assert "src/Ushahidi/Contracts/EntityExists.php" in text


def test_collect_chunks_covers_code_routes_and_docs(sample_repo):
    php_files, doc_files, chunks = collect_chunks(sample_repo, INCLUDE_DIRS, DOC_DIRS)

    sources = {c["source"] for c in chunks}

    assert len(php_files) == 4
    assert len(doc_files) == 1
    assert "routes/api.php" in sources
    assert "src/Ushahidi/DataSource/data-flows.md" in sources
    # Sources always use forward slashes, even on Windows
    assert all("\\" not in s for s in sources)
