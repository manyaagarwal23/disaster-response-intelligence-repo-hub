# Session outputs — 2026-10-07

Everything produced during the afternoon/evening work session that previously
lived only in temporary locations (Claude's scratchpad, background-job output
files, or the terminal), saved here permanently. No API keys are stored in
this folder (checked).

## scripts/

Helper scripts used to measure and verify. Paths inside them point at the
dev VM (`/app/rag` = the repo's `rag/` folder inside the `drih-app` container).

| Script | What it does | How it was run |
|---|---|---|
| `ff_ui.py` | Scripted Firefox (Selenium) run of every tab with 20 functional checks; saves `docs/screenshots/ui-*.png` | `python ff_ui.py docs/screenshots/ui` (needs `pip install selenium`, Firefox + geckodriver) |
| `diag.py` | Measures element positions/scroll containers of the Ask page (found the landing-layout bug) | same environment as `ff_ui.py` |
| `cssdiag.py` | Inspects the live CSS cascade in the browser (showed `.search-container` was outside `.home-layout`) | same |
| `recall_probe.py` | For the permission questions: vector vs BM25 candidates and distances of the relevant chunks | `docker exec drih-app python /tmp/recall_probe.py` |
| `rank_probe.py` | Hybrid rank of the relevant chunks for every benchmark question and what outranks them | `docker exec drih-app python /tmp/rank_probe.py` |
| `score_experiment.py` | Offline comparison of hybrid-scoring variants on all 33 questions | `docker exec drih-app python /tmp/score_experiment.py` |
| `slides_v4.py` | Builds deck v4 (new UI screenshot on slide 10) from v3 | `python slides_v4.py <out.pptx> docs/screenshots/ui-home.png` (needs `python-pptx`) |

## job-logs/

Raw output of the background jobs.

| Log | Content |
|---|---|
| `bj62vspgd.log` | Retrieval evaluation without LLM, before the BM25 experiment (full run: `reports/eval/recall-check-run.log`) |
| `b8ym1boqf.log` | Same evaluation with BM25 candidates (full run: `reports/eval/recall-after-lexical-run.log`) |
| `biin8fram.log` | 7-question subset with the LLM reranker seeing 25 candidates (full run: `reports/eval/rerank25-subset-run.log`) |
| `beh670gmc.log` | First forced local-fallback test (both keys invalid): the local model produced junk text, which led to the junk filter |
| `bom73bigr.log` | Final forced local-fallback test through the real API path: coherent answer in 85 s (also `reports/ollama-fallback-2026-10-07.log`) |

## Results that were only shown in the terminal

### Recall probe (`recall_probe.py`) — permission questions

Relevant files ARE among the 30 vector candidates; they just rank low.

| Q | Question | Relevant chunks in vector top 30 | Closest relevant chunk (cosine distance) |
|---|---|---|---|
| 23 | Where is the permission to create a post checked? | PostPolicy ×2, PostAuthorizer | 0.366 PostPolicy::isFormRestricted |
| 24 | How does the system determine which roles can create posts? | PostPolicy ×4, PostAuthorizer | 0.367 PostPolicy::isFormRestricted |
| 25 | How does the system check whether a user has Manage Posts permission? | PostPolicy ×2, PostAuthorizer ×2, EloquentPostRepository | 0.382 PostPolicy::isAllowed |
| 28 | What happens when a user without permissions tries to update a post? | PostAuthorizer ×2 | 0.402 PostAuthorizer::isAllowed |
| 30 | How does the system validate input data before creating a post? | PostRequest ×2 | 0.360 PostRequest::storeRules |

BM25 (plain) placed PostAuthorizer/PostPolicy at ranks 3–6 for q23 but did not
help q30 (CreatePostCommand only at rank 36).

### Rank probe (`rank_probe.py`) — first relevant hybrid rank per question

```
q1 1, q2 1, q3 1, q4 1, q5 1, q6 2, q7 1, q8 8, q9 1, q10 5, q11 1, q12 1, q13 1,
q14 1, q15 1, q16 6, q17 1, q18 5, q19 1, q20 1, q21 5, q22 2, q23 17, q24 9,
q25 17, q26 7, q27 3, q28 24, q29 3, q30 14, q31 1, q32 1, q33 3
```

The misses lose to chunks that get the exact-identifier bonus twice (file name
and class name), e.g. `Create.php::checkRequiredStages`, `PostPermissions.php::canUser…`.

### Scoring experiment (`score_experiment.py`) — 33 questions, no LLM

| Variant | MRR@10 | Hit@1 | Hit@3 | Hit@5 | Hit@10 | Changes vs baseline |
|---|---|---|---|---|---|---|
| A baseline | 0.614 | 51.5% | 66.7% | 75.8% | 90.9% | — |
| B dedupe file/class bonus | 0.598 | 48.5% | 66.7% | 75.8% | 90.9% | q20 1→2 |
| C dedupe + 1-word ids ×0.5 | 0.611 | 48.5% | 69.7% | 78.8% | 90.9% | q8 8→7, q24 9→2; q20 1→2 |
| D C + exact weight 0.08 | 0.608 | 48.5% | 66.7% | 78.8% | 90.9% | +q30 14→13; q33 3→4 |
| E dedupe + 1-word ids ×0.25 | 0.621 | 51.5% | 66.7% | 78.8% | 90.9% | q8, q16, q23, q24, q30 better; **q33 3→10** |
| F B + exact weight 0.15 | 0.598 | 48.5% | 66.7% | 75.8% | 90.9% | q20 1→2 |

Decision: scoring unchanged (no variant improves without hurting another question).

### BM25 keyword candidates (full run)

| | MRR@10 | Hit@1 | Hit@3 | Hit@5 |
|---|---|---|---|---|
| hybrid before | 0.614 | 51.5% | 66.7% | 75.8% |
| hybrid with BM25 | 0.605 | 51.5% | 60.6% | 75.8% |

q24 9→missing, q27 3→4, q29 3→4. Decision: kept behind `LEXICAL_CANDIDATES=0` (off).

### LLM reranker over 25 candidates (7-question subset)

| Q | Before (top-10 rerank, morning run) | After (top-25, 320-char previews) |
|---|---|---|
| 23 | missing | 1 |
| 25 | 4 | 3 |
| 28 | missing | 6 |
| 30 | missing | 1 |
| 1, 31, 33 (controls) | 1, 1, 1 | 1, 1, 1 |

One measured run. A later live call for q23 ranked the V3 `Create` validator
first, so the reranker is not deterministic across calls.

### Groq key chain test

Key 1 set to an invalid key, key 2 real:
```
Groq key 1 rejected (Error code: 401 - Invalid API Key); skipping it from now on.
reply: 'OK' | provider: groq#2 | 0.6s
dead keys after the call: [0]
```
Normal path afterwards: `provider groq#1`, 3.7 s for "Where are the V5 API routes for posts defined?".

### Local model (Ollama `llama3.2:3b`) on the dev VM CPU

| Test | Result |
|---|---|
| Installed models (nothing downloaded) | llama3.2:3b 2.0 GB, qwen2.5-coder:1.5b-instruct 1.0 GB, deepseek-coder:1.3b 0.8 GB, nomic-embed-text 0.3 GB |
| Short prompt, 30 tokens, our options | coherent sentence, 1.3 tokens/s |
| Short prompt, 30 tokens, Ollama defaults | coherent sentence, 1.8 tokens/s |
| Full answer prompt (1,215 tokens), 40-token reply | prompt read in 30 s, coherent JSON start, 95 s total |
| First forced fallback (full prompt, 1,200-token cap) | **junk text** ("TSA withinphonhaus底 cold … within within …") → junk filter added |
| Final forced fallback via API (compact prompt, 160-token cap) | coherent summary in 85 s, note + backup diagram shown |

RAM available while the model was loaded: about 2.3 GB.

### Browser checks (`ff_ui.py`, final run)

All 20 checks passed: stats loaded, 6 question cards, light/dark toggle, `/`
shortcut, Code Search 10 results in under 0.5 s with syntax highlighting and
GitHub links, pipeline stepper, answer with timings (2.5 s), diagram rendered,
modal open/close, New chat, history count, 33 dataset questions, no page errors.
