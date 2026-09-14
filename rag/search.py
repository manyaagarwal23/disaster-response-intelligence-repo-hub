import re

import chromadb

from sentence_transformers import SentenceTransformer


# ============================================================
# 1. Identifier Normalization
# ============================================================

def normalize_identifier(identifier):

    identifier = re.sub(
        r'([a-z0-9])([A-Z])',
        r'\1 \2',
        identifier
    )

    identifier = identifier.replace(
        "_",
        " "
    )

    identifier = identifier.replace(
        "-",
        " "
    )

    return identifier.lower().split()


# ============================================================
# 2. Connect to ChromaDB
# ============================================================

client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = client.get_collection(
    name="ushahidi_code"
)

print("Collection:", collection.name)
print("Stored units:", collection.count())


# ============================================================
# 3. Get Developer Question
# ============================================================

question = input("\nEnter your question: ")


# ============================================================
# 4. Detect PHP Filename
# ============================================================

filename_match = re.search(
    r'\b[\w.-]+\.php\b',
    question,
    re.IGNORECASE
)

if filename_match:

    filename = filename_match.group(0)

    print("\nDetected filename:", filename)

else:

    filename = None

    print("\nNo filename detected")


# ============================================================
# 5. Extract Question Words
# ============================================================

question_words = set(
    re.findall(
        r'[a-zA-Z0-9_]+',
        question.lower()
    )
)


# ============================================================
# 6. Create Question Embedding
# ============================================================

model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)

question_embedding = model.encode(
    question
)

print("\nQuestion embedding created")

print(
    "Vector dimensions:",
    len(question_embedding)
)


# ============================================================
# 7. Retrieve Candidate Methods / Functions
# ============================================================

if filename:

    results = collection.query(

        query_embeddings=[
            question_embedding.tolist()
        ],

        n_results=10,

        where={
            "filename": filename
        }
    )

else:

    results = collection.query(

        query_embeddings=[
            question_embedding.tolist()
        ],

        n_results=10
    )


# ============================================================
# 8. Calculate Hybrid Scores
# ============================================================

scored_results = []


for i in range(
    len(results["documents"][0])
):

    metadata = results["metadatas"][0][i]

    code = results["documents"][0][i]


    # --------------------------------------------------------
    # Normalize metadata identifiers
    # --------------------------------------------------------

    identifiers = [

        metadata.get("filename", ""),

        metadata.get("class", ""),

        metadata.get("method", ""),

        metadata.get("namespace", "")

    ]


    identifier_words = set()


    for identifier in identifiers:

        identifier_words.update(
            normalize_identifier(
                identifier
            )
        )


    # --------------------------------------------------------
    # Identifier matches
    # --------------------------------------------------------

    identifier_matches = (
        question_words &
        identifier_words
    )

    identifier_score = len(
        identifier_matches
    )


    # --------------------------------------------------------
    # Normalize code identifiers
    # --------------------------------------------------------

    normalized_code = re.sub(
        r'([a-z0-9])([A-Z])',
        r'\1 \2',
        code
    )

    normalized_code = normalized_code.replace(
        "_",
        " "
    )

    normalized_code = normalized_code.lower()


    # --------------------------------------------------------
    # Code-content matches
    # --------------------------------------------------------

    code_matches = []


    for word in question_words:

        if len(word) < 3:
            continue

        if word in normalized_code:

            code_matches.append(word)


    code_score = len(
        set(code_matches)
    )

        # --------------------------------------------------------
    # Structural matches
    # --------------------------------------------------------
    structural_text = " ".join([
        metadata.get("calls", ""),
        metadata.get("parameter_types", ""),
        metadata.get("assignments", "")
    ])

    normalized_structural = re.sub(
        r'([a-z0-9])([A-Z])',
        r'\1 \2',
        structural_text
    )

    normalized_structural = normalized_structural.replace(
        "_",
        " "
    )

    normalized_structural = normalized_structural.lower()

    structural_matches = []

    for word in question_words:
        if len(word) < 3:
            continue
        if word in normalized_structural:
            structural_matches.append(word)

    structural_score = len(
        set(structural_matches)
    )


    # --------------------------------------------------------
    # Semantic distance
    # --------------------------------------------------------

    distance = (
        results["distances"][0][i]
    )


    scored_results.append({

          "distance": distance,
         "structural_score": structural_score,
          "structural_matches":
           sorted(set(structural_matches)),
         "identifier_score":
             identifier_score,

        "code_score":
            code_score,

        "identifier_matches":
            sorted(identifier_matches),

        "code_matches":
            sorted(set(code_matches)),

        "source":
            metadata["source"],

        "filename":
            metadata["filename"],

        "namespace":
            metadata["namespace"],

        "class":
            metadata["class"],

        "method":
            metadata["method"],

        "type":
            metadata["type"],

        "content":
            code

    })


# ============================================================
# 9. Rank Results
# ============================================================

scored_results.sort(

    key=lambda x: (

        -x["code_score"],

        -x["identifier_score"],

        x["distance"]

    )

)


# ============================================================
# 10. Display Results
# ============================================================

print(
    "\nResults ranked using semantic + identifier + code retrieval:"
)

print(
    "\nRelevant code units found:"
)


for i, result in enumerate(
    scored_results
):

    print("\n" + "=" * 70)

    print(
        "Rank:",
        i + 1
    )

    print(
        "Code matches:",
        result["code_score"]
    )

    print(
        "Code matched words:",
        result["code_matches"]
    )
    print(
    "Structural matches:",
    result["structural_score"]
    )

    print(
    "Structural matched words:",
    result["structural_matches"]
    )

    print(
        "Identifier matches:",
        result["identifier_score"]
    )

    print(
        "Identifier matched words:",
        result["identifier_matches"]
    )

    print(
        "Distance:",
        result["distance"]
    )

    print(
        "Source:",
        result["source"]
    )

    print(
        "Namespace:",
        result["namespace"]
    )

    print(
        "Class:",
        result["class"]
    )

    print(
        "Method:",
        result["method"]
    )

    print(
        "Type:",
        result["type"]
    )

    print("-" * 70)

    print(
        result["content"]
    )


# ============================================================
# 11. Display Original Question
# ============================================================

print("\nYour question:")

print(question)