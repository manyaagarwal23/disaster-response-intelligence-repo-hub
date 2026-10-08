"""Why do the permission questions miss? Probe vector and BM25 candidate sets."""
import json, sys
sys.path.insert(0, "/app/rag")
import retrieval
from retrieval import tokenize, LexicalIndex, extract_question_words, cosine_distance

qs = json.load(open("/app/rag/eval/questions.json"))
items = qs if isinstance(qs, list) else qs["questions"]
targets = [23, 24, 25, 28, 30]
r = retrieval.get_retriever()
index = r.lexical
# all chunk texts, by id, for inspection
rows = r.collection.get(include=["documents", "metadatas"])
by_id = {i: (d, m) for i, d, m in zip(rows["ids"], rows["documents"], rows["metadatas"])}

SYN = {
    "permission": ["policy", "authorizer", "authorize", "privilege", "allowed", "acl", "role", "auth"],
    "unauthorized": ["authorizer", "policy", "allowed", "forbidden", "auth"],
    "role": ["acl", "permission", "policy", "privilege"],
    "validate": ["validator", "request", "rules", "valid", "validation"],
    "check": ["verify", "allowed"],
}
def expand(question):
    toks = tokenize(question)
    extra = []
    for raw, syns in SYN.items():
        if retrieval.stem(raw) in toks:
            extra += [retrieval.stem(s) for s in syns]
    return toks + extra

for n in targets:
    q = items[n-1]; question = q["question"]; relevant = set(q["relevant"])
    emb = r.embed_question(question)
    sem = r.semantic_search(question, embedding=emb)
    worst = max(x["distance"] for x in sem)
    print(f"\n### q{n}: {question}")
    print("   tokens:", tokenize(question), "| expanded extra:", [t for t in expand(question) if t not in tokenize(question)])
    print(f"   vector top30: worst distance {worst:.3f}; relevant files inside: {[x['source'].split('/')[-1] for x in sem if x['source'] in relevant]}")
    # BM25 plain and expanded: where do relevant files land?
    for label, text in (("bm25 plain", question), ("bm25 +syn", " ".join(expand(question)))):
        hits = index.search(text, k=60)
        found = [(rank, by_id[cid][1]["source"].split("/")[-1], round(score, 1)) for rank, (cid, score) in enumerate(hits, 1) if by_id[cid][1]["source"] in relevant]
        print(f"   {label:10}: top-60 relevant hits {found[:6]} | top5 files {[by_id[c][1]['source'].split('/')[-1] for c,_ in hits[:5]]}")
    # distances of the relevant chunks vs. the vector cutoff
    rel_chunks = [(cid, d, m) for cid, (d, m) in by_id.items() if m["source"] in relevant]
    got = r.collection.get(ids=[c for c, _, _ in rel_chunks], include=["embeddings", "metadatas"])
    dists = sorted((round(cosine_distance(emb, [float(x) for x in e]), 3), m["source"].split("/")[-1] + ":" + str(m.get("method"))) for e, m in zip(got["embeddings"], got["metadatas"]))
    print("   closest relevant chunks by distance:", dists[:4])
