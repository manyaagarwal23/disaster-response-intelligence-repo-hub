"""Offline hybrid-scoring variants on cached vector candidates (no LLM)."""
import json, sys
sys.path.insert(0, "/app/rag")
import retrieval
from retrieval import normalize_identifier, normalize_code, extract_question_words, WEIGHTS

qs = json.load(open("/app/rag/eval/questions.json"))
items = qs if isinstance(qs, list) else qs["questions"]
r = retrieval.get_retriever(); r.lexical = None
cache = []
for q in items:
    sem = r.semantic_search(q["question"])
    cache.append((q, sem))

def rescore(result, question_words, variant):
    md = {"filename": result["filename"], "class": result["class"], "method": result["method"], "namespace": result["namespace"], "type": result["type"]}
    identifiers = [md["filename"].removesuffix(".php"), md["class"], md["method"]]
    if variant.get("dedupe"):
        seen, uniq = set(), []
        for ident in identifiers:
            key = tuple(normalize_identifier(ident))
            if key and key not in seen: seen.add(key); uniq.append(ident)
        identifiers = uniq
    exact = 0.0
    for ident in identifiers:
        words = normalize_identifier(ident)
        if words and all(w in question_words for w in words):
            exact += variant.get("short_factor", 1.0) if len(words) == 1 else 1.0
    w = dict(WEIGHTS); w.update(variant.get("weights", {}))
    score = result["similarity"] + w["exact_identifier"] * exact + w["identifier"] * len(result["identifier_matches"]) \
        + w["code"] * len(result["code_matches"]) + w["structural"] * len(result["structural_matches"]) + w["implementation"] * result["implementation_score"]
    return score

def evaluate(variant):
    ranks = []
    for q, sem in cache:
        qw = extract_question_words(q["question"])
        ordered = sorted(sem, key=lambda x: (-rescore(x, qw, variant), x["distance"]))
        relevant = set(q["relevant"])
        first = next((i for i, x in enumerate(ordered, 1) if x["source"] in relevant), None)
        ranks.append(first)
    mrr = sum(1 / rk for rk in ranks if rk and rk <= 10) / len(ranks)
    hit = lambda k: sum(1 for rk in ranks if rk and rk <= k) / len(ranks)
    return mrr, hit(1), hit(3), hit(5), hit(10), ranks

variants = {
    "A baseline": {},
    "B dedupe file/class": {"dedupe": True},
    "C dedupe + short ids x0.5": {"dedupe": True, "short_factor": 0.5},
    "D C + exact 0.08": {"dedupe": True, "short_factor": 0.5, "weights": {"exact_identifier": 0.08}},
    "E dedupe + short x0.25": {"dedupe": True, "short_factor": 0.25},
    "F B + exact 0.15": {"dedupe": True, "weights": {"exact_identifier": 0.15}},
}
base = None
for name, v in variants.items():
    mrr, h1, h3, h5, h10, ranks = evaluate(v)
    if base is None: base = ranks
    worse = [(i + 1, b, n) for i, (b, n) in enumerate(zip(base, ranks)) if (n or 99) > (b or 99)]
    better = [(i + 1, b, n) for i, (b, n) in enumerate(zip(base, ranks)) if (n or 99) < (b or 99)]
    print(f"{name:28} MRR@10 {mrr:.3f}  Hit@1 {h1:.1%}  Hit@3 {h3:.1%}  Hit@5 {h5:.1%}  Hit@10 {h10:.1%} | better {better} | worse {worse}")
