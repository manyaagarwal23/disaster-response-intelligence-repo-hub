"""Quick sanity check of the vector database: size, settings, one sample chunk."""

import collections

import chromadb

import config


client = chromadb.PersistentClient(
    path=str(config.CHROMA_PATH)
)

collection = client.get_collection(
    name=config.COLLECTION_NAME
)

print("Database path:", config.CHROMA_PATH)
print("Collection:", collection.name)
print("Settings:", collection.metadata)
print("Chunks stored:", collection.count())

all_metadata = collection.get(include=["metadatas"])["metadatas"]

print("Chunks by type:", dict(collections.Counter(m["type"] for m in all_metadata)))

result = collection.get(
    ids=["0"],
    include=["documents", "metadatas"]
)

print("\nSample chunk ID:", result["ids"][0])
print("Source:", result["metadatas"][0]["source"])
print("Lines:", result["metadatas"][0]["start_line"], "-", result["metadatas"][0]["end_line"])
print("\nCode:")
print(result["documents"][0])
