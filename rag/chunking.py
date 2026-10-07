import re

from php_extractor import extract_php_units


# BGE reads at most 512 tokens (~2000 characters of code). Longer
# units are split into overlapping windows so the end of a long
# method is still searchable instead of being silently cut off.
MAX_CHUNK_LINES = 60

CHUNK_OVERLAP_LINES = 10

MAX_DOC_CHARS = 1800


# ============================================================
# 1. Read Source Files
# ============================================================

def read_source_file(file_path):

    try:

        return file_path.read_text(encoding="utf-8")

    except UnicodeDecodeError:

        return file_path.read_text(encoding="utf-8", errors="ignore")


def find_files(repo_path, include_dirs, pattern):

    files = []

    for file in sorted(repo_path.rglob(pattern)):

        relative_path = file.relative_to(repo_path)

        if relative_path.parts[0] in include_dirs:

            files.append(file)

    return files


# ============================================================
# 2. Split Long Units into Windows
# ============================================================

def split_into_windows(content, start_line):
    """
    Return (window_text, first_line, last_line) tuples.
    Short content is returned unchanged as a single window.
    """

    lines = content.split("\n")

    if len(lines) <= MAX_CHUNK_LINES:

        return [(content, start_line, start_line + len(lines) - 1)]

    windows = []

    step = MAX_CHUNK_LINES - CHUNK_OVERLAP_LINES

    for offset in range(0, len(lines), step):

        window = lines[offset:offset + MAX_CHUNK_LINES]

        windows.append((
            "\n".join(window),
            start_line + offset,
            start_line + offset + len(window) - 1,
        ))

        if offset + MAX_CHUNK_LINES >= len(lines):

            break

    return windows


# ============================================================
# 3. PHP Chunks
# ============================================================

def php_chunks_from_code(code, relative_path, filename):

    chunks = []

    for unit in extract_php_units(code):

        windows = split_into_windows(unit["content"], unit["start_line"])

        for part, (text, first_line, last_line) in enumerate(windows, 1):

            chunks.append({

                "source": relative_path,

                "filename": filename,

                "language": "php",

                "namespace": unit["namespace"] or "",

                "class": unit["class"] or "",

                "class_kind": unit["class_kind"] or "",

                "method": unit["method"] or "",

                "type": unit["type"],

                "abstract": unit["abstract"],

                "start_line": first_line,

                "end_line": last_line,

                "part": part,

                "parts": len(windows),

                "content": text,

                "calls": unit["calls"],

                "parameter_types": unit["parameter_types"],

                "assignments": unit["assignments"],

            })

    return chunks


# ============================================================
# 4. Markdown Documentation Chunks
# ============================================================

def markdown_chunks_from_text(text, relative_path, filename):
    """
    Split a markdown document on headings, then split long
    sections into pieces of at most MAX_DOC_CHARS characters.
    """

    sections = []

    current_heading = ""

    current_lines = []

    current_start = 1

    for line_number, line in enumerate(text.split("\n"), 1):

        if re.match(r"^#{1,6}\s", line) and current_lines:

            sections.append((current_heading, current_start, current_lines))

            current_lines = []

            current_start = line_number

        if re.match(r"^#{1,6}\s", line):

            current_heading = line.lstrip("#").strip()

        current_lines.append(line)

    if current_lines:

        sections.append((current_heading, current_start, current_lines))

    chunks = []

    for heading, start, lines in sections:

        buffer = []

        buffer_start = start

        for offset, line in enumerate(lines):

            buffer.append(line)

            if sum(len(x) + 1 for x in buffer) >= MAX_DOC_CHARS:

                chunks.append((heading, buffer_start, start + offset, buffer))

                buffer = []

                buffer_start = start + offset + 1

        if buffer:

            chunks.append((heading, buffer_start, start + len(lines) - 1, buffer))

    return [

        {
            "source": relative_path,
            "filename": filename,
            "language": "markdown",
            "namespace": "",
            "class": "",
            "class_kind": "",
            "method": heading,
            "type": "doc",
            "abstract": False,
            "start_line": first_line,
            "end_line": last_line,
            "part": 1,
            "parts": 1,
            "content": "\n".join(lines),
            "calls": [],
            "parameter_types": {},
            "assignments": [],
        }

        for heading, first_line, last_line, lines in chunks

        if "\n".join(lines).strip()

    ]


# ============================================================
# 5. Text that gets Embedded
# ============================================================

def build_embedding_text(chunk):

    if chunk["type"] == "doc":

        return (
            f"Documentation: {chunk['source']}\n"
            f"Section: {chunk['method']}\n\n"
            f"{chunk['content']}"
        )

    calls_text = " ".join(
        f'{call["object"]} {call["method"]}'
        for call in chunk["calls"]
    )

    parameter_text = " ".join(
        f"{name} {parameter_type}"
        for name, parameter_type in chunk["parameter_types"].items()
    )

    assignment_text = " ".join(
        f'{assignment["left"]} {assignment["right"]}'
        for assignment in chunk["assignments"]
    )

    text = f"""
File: {chunk["source"]}
Namespace: {chunk["namespace"]}
{chunk["class_kind"].capitalize() or "Class"}: {chunk["class"]}
Method: {chunk["method"]}
Type: {chunk["type"]}

Calls:
{calls_text}

Parameter types:
{parameter_text}

Property assignments:
{assignment_text}

Code:
{chunk["content"]}
"""

    return text.strip()


# ============================================================
# 6. Metadata stored in ChromaDB
# ============================================================
# ChromaDB metadata values must be str / int / float / bool.

def build_metadata(chunk):

    return {

        "source": chunk["source"],

        "filename": chunk["filename"],

        "language": chunk["language"],

        "namespace": chunk["namespace"],

        "class": chunk["class"],

        "class_kind": chunk["class_kind"],

        "method": chunk["method"],

        "type": chunk["type"],

        "abstract": bool(chunk["abstract"]),

        "start_line": int(chunk["start_line"]),

        "end_line": int(chunk["end_line"]),

        "part": int(chunk["part"]),

        "parts": int(chunk["parts"]),

        "calls": " | ".join(
            f'{call["object"]}->{call["method"]}'
            for call in chunk["calls"]
        ),

        "parameter_types": " | ".join(
            f"{name}->{parameter_type}"
            for name, parameter_type in chunk["parameter_types"].items()
        ),

        "assignments": " | ".join(
            f'{assignment["left"]}={assignment["right"]}'
            for assignment in chunk["assignments"]
        ),

    }


# ============================================================
# 7. Collect every Chunk of a Repository
# ============================================================

def collect_chunks(repo_path, include_dirs, doc_dirs):

    chunks = []

    php_files = find_files(repo_path, include_dirs, "*.php")

    for file in php_files:

        chunks.extend(php_chunks_from_code(
            read_source_file(file),
            file.relative_to(repo_path).as_posix(),
            file.name,
        ))

    doc_files = find_files(repo_path, doc_dirs, "*.md")

    for file in doc_files:

        chunks.extend(markdown_chunks_from_text(
            read_source_file(file),
            file.relative_to(repo_path).as_posix(),
            file.name,
        ))

    return php_files, doc_files, chunks
