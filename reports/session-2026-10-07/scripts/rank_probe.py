"""Where do the relevant chunks land in the hybrid order, and what beats them?"""
import json, sys
sys.path.insert(0, "/app/rag")
import retrieval
qs = json.load(open("/app/rag/eval/questions.json"))
items = qs if isinstance(qs, list) else qs["questions"]
r = retrieval.get_retriever()
r.lexical = None   # vector candidates only (the shipped behaviour)
summary = []
for n, q in enumerate(items, 1):
    relevant = set(q["relevant"])
    res = r.search(q["question"], use_llm=False)
    hybrid = res["hybrid"]
    ranks = [i for i, x in enumerate(hybrid, 1) if x["source"] in relevant]
    first = ranks[0] if ranks else None
    summary.append((n, first))
    if first is None or first > 10:
        print(f"\n### q{n}: {q['question']}  -> first relevant at hybrid rank {first}")
        for i, x in enumerate(hybrid[:12], 1):
            mark = "**" if x["source"] in relevant else "  "
            print(f"  {mark}{i:2d} score={x['score']:.3f} sim={1-x['distance']:.3f} exact={x.get('exact_identifier_score', x.get('exact', '?'))} {x['source'].split('/')[-1]}::{x['method']}")
        for i in ranks[:3]:
            x = hybrid[i-1]
            print(f"  ** relevant @{i}: score={x['score']:.3f} sim={1-x['distance']:.3f} {x['source'].split('/')[-1]}::{x['method']}")
print("\nfirst-relevant hybrid ranks:", summary)
print("sample result keys:", sorted(hybrid[0].keys()))
