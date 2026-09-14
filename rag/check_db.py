import chromadb

client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = client.get_collection(
    name="ushahidi_code"
)

result = collection.get(
    ids=["0"],
    include=["documents", "metadatas"]
)

print("Chunk ID:", result["ids"][0])
print("Source:", result["metadatas"][0]["source"])
print("Filename:", result["metadatas"][0]["filename"])
print("\nCode:")
print(result["documents"][0])