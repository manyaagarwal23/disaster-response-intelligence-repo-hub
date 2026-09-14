import chromadb
from sentence_transformers import SentenceTransformer

client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = client.get_collection(
    name="ushahidi_code"
)

model = SentenceTransformer("all-MiniLM-L6-v2")

question = "Show me FetchDataSourceQueryHandler.php"

question_embedding = model.encode(question)

results = collection.query(
    query_embeddings=[question_embedding.tolist()],
    n_results=10,
    where={"filename": "FetchDataSourceQueryHandler.php"}
)

print("Results found:", len(results["ids"][0]))

for i in range(len(results["ids"][0])):
    print("\n" + "=" * 60)
    print("Rank:", i + 1)
    print("ID:", results["ids"][0][i])
    print("Source:", results["metadatas"][0][i]["source"])
    print("Filename:", results["metadatas"][0][i]["filename"])
    print("Distance:", results["distances"][0][i])
    print("=" * 60)
    print(results["documents"][0][i])