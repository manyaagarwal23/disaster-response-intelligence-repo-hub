from pathlib import Path

from sentence_transformers import SentenceTransformer
import chromadb

from php_extractor import extract_php_units


# ============================================================
# 1. Repository Configuration
# ============================================================

REPO_PATH = Path("../ushahidi")

INCLUDE_DIRS = {
    "src",
    "app",
    "config",
    "routes",
    "bootstrap",
}


# ============================================================
# 2. Find PHP Source Files
# ============================================================

php_files = []

for file in REPO_PATH.rglob("*.php"):

    relative_path = file.relative_to(REPO_PATH)

    if relative_path.parts[0] in INCLUDE_DIRS:

        php_files.append(file)


print("PHP files selected:", len(php_files))


# ============================================================
# 3. Read Source Files and Extract PHP Units
# ============================================================

def read_source_file(file_path):

    try:

        return file_path.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        return file_path.read_text(
            encoding="utf-8",
            errors="ignore"
        )


units = []


for file in php_files:

    content = read_source_file(file)

    extracted_units = extract_php_units(
        content
    )

    relative_path = str(
        file.relative_to(REPO_PATH)
    )

    for unit in extracted_units:

        units.append({

            "unit_id": len(units),

            "source": relative_path,

            "filename": file.name,

            "namespace": unit["namespace"] or "",

            "class": unit["class"] or "",

            "method": unit["method"] or "",

            "type": unit["type"],

            "content": unit["content"],

            "calls": unit["calls"],

            "parameter_types": unit[
                "parameter_types"
            ],

            "assignments": unit[
                "assignments"
            ]

        })


print(
    "PHP units extracted:",
    len(units)
)


# ============================================================
# 4. Prepare Text for Embeddings
# ============================================================

embedding_texts = []


for unit in units:

    calls_text = " ".join(
        f'{call["object"]} {call["method"]}'
        for call in unit["calls"]
    )

    parameter_text = " ".join(
        f'{name} {parameter_type}'
        for name, parameter_type
        in unit["parameter_types"].items()
    )

    assignment_text = " ".join(
        f'{assignment["left"]} {assignment["right"]}'
        for assignment in unit["assignments"]
    )

    text = f"""
Namespace: {unit["namespace"]}
Class: {unit["class"]}
Method: {unit["method"]}
Type: {unit["type"]}

Calls:
{calls_text}

Parameter types:
{parameter_text}

Property assignments:
{assignment_text}

Code:
{unit["content"]}
"""

    embedding_texts.append(
        text.strip()
    )


print(
    "Embedding texts prepared:",
    len(embedding_texts)
)


# ============================================================
# 5. Load Local Embedding Model
# ============================================================

print("\nLoading embedding model...")

model = SentenceTransformer(
    "BAAI/bge-base-en-v1.5"
)


# ============================================================
# 6. Create Embeddings
# ============================================================

print("\nCreating embeddings...")

all_embeddings = model.encode(
    embedding_texts,
    show_progress_bar=True
)


print("\nAll embeddings created")

print(
    "Number of embeddings:",
    len(all_embeddings)
)

print(
    "Embedding dimensions:",
    len(all_embeddings[0])
)


# ============================================================
# 7. Connect to ChromaDB
# ============================================================

client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = client.get_or_create_collection(
    name="ushahidi_code"
)


print("\nChromaDB collection ready")

print(
    "Collection:",
    collection.name
)


# ============================================================
# 8. Store Embeddings in ChromaDB
# ============================================================

if collection.count() == 0:

    collection.add(

        ids=[
            str(unit["unit_id"])
            for unit in units
        ],

        embeddings=all_embeddings.tolist(),

        documents=[
            unit["content"]
            for unit in units
        ],

        metadatas=[

            {
                "source": unit["source"],

                "filename": unit["filename"],

                "namespace": unit["namespace"],

                "class": unit["class"],

                "method": unit["method"],

                "type": unit["type"],

                "calls": " | ".join(
                    f'{call["object"]}->{call["method"]}'
                    for call in unit["calls"]
                ),

                "parameter_types": " | ".join(
                    f'{name}->{parameter_type}'
                    for name, parameter_type
                    in unit["parameter_types"].items()
                ),

                "assignments": " | ".join(
                    f'{assignment["left"]}={assignment["right"]}'
                    for assignment
                    in unit["assignments"]
                )

            }

            for unit in units

        ]

    )

    print(
        "\nPHP units stored in ChromaDB"
    )

else:

    print(
        "\nChromaDB already contains data"
    )


# ============================================================
# 9. Final Information
# ============================================================

print("\n" + "-" * 50)

print("INGESTION COMPLETE")

print("-" * 50)

print(
    "PHP files:",
    len(php_files)
)

print(
    "Methods/functions:",
    len(units)
)

print(
    "Vectors:",
    len(all_embeddings)
)

print(
    "Vector dimensions:",
    len(all_embeddings[0])
)

print(
    "ChromaDB documents:",
    collection.count()
)

print("-" * 50)