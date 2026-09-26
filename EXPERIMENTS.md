# Experimental design

## What counts as the final result

The primary task output is the final inheritance allocation:

```json
{
  "case_id": "1",
  "allocations": [
    {"recipient": "A", "amount": 500000000, "currency": "VND"}
  ],
  "cited_articles": ["BLDS2015_651"]
}
```

Primary end-to-end metrics compare the predicted recipients and amounts with
`data/canonical/reference.jsonl`. Extraction schemas, retrieved statutes,
plans, and traces are intermediate outputs and receive separate module metrics.

## B0 — Monolithic end-to-end LLM

```text
case text
→ one LLM call
→ cited final heir-to-amount allocation
```

The same model receives the complete task and returns the final answer in one
call. It may reason internally, but no intermediate extraction, retrieval,
planning, or verification result is supplied by another agent. This is the
single-LLM baseline requested for the paper.

Required variants should be frozen before testing:

- `B0-closed-book`: case text only;
- `B0-RAG`: case text plus statutes retrieved by a fixed baseline retriever.

The frozen sparse-retrieval variant is B2: BM25 over the canonical article-level
statute corpus (`retrieval_text`, stable `citation_id`), using the raw case text
as query and `top_k=5`, followed by the same direct-allocation model and schema.

## B4 — Hybrid RAG + direct allocation

```text
raw case text
→ BM25 top-20 + Voyage cosine top-20
→ reciprocal rank fusion (k=60)
→ fused top-5 statutes
→ the same direct-allocation LLM and output schema as B2
```

B4 isolates the retrieval intervention. It does not use structured extraction,
issue classification or taxonomy filtering, temporal filtering, planning,
deterministic execution, verification, repair, or abstention. Its prompt version
is `b4_hybrid_v1`; no B4 results are recorded here before the controlled run.

## B5 — Coordinated Modular LLM

```text
frozen B4 hybrid retrieval
→ structured case-extraction LLM
→ inheritance/legal-issue analysis LLM
→ statute-aware reasoning LLM
→ coordinated final-allocation LLM
→ existing allocation schema
```

Each role has a fixed prompt, strict intermediate JSON schema, and structured
hand-off. Retrieval is exactly B4 (BM25 top-20 + Voyage cosine top-20, RRF k=60,
fused top-5), so the intervention is modular reasoning rather than a new
retriever. All four calls use the frozen model/inference configuration and prompt
version `b5_modular_v1`. The trace records call count, order, response IDs,
per-module and total usage, intermediate outputs, retrieval provenance, elapsed
time, validation errors, and failures.

B5 permits its LLM reasoning module to calculate intermediate values and its
final LLM module to produce amounts. It does not use an executable plan,
deterministic inheritance/arithmetic executor, external semantic fact validator,
post-execution verifier, repair/re-execution loop, or formal abstention. Those
distinguish the proposed IGEP method. No B5 performance result is recorded until
the controlled API experiment is run by the researcher.

## Proposed method — IGEP

```text
validated extraction
→ temporal hybrid retrieval
→ constrained plan
→ deterministic executor
→ legal/arithmetic verifier
→ final heir-to-amount allocation or abstention
```

IGEP is not the same as the current file
`data/runs/extraction_dev_igep.jsonl`. That file evaluates only the extraction
module and contains no final allocation prediction.

## Evaluation levels

| Level | Output | Reference | Main metrics |
|---|---|---|---|
| End-to-end | heirs and amounts | `reference.jsonl` | heir F1, amount accuracy, allocation exact match, conservation |
| Retrieval | ranked citations | `temporal.jsonl` | Recall@k, MRR, nDCG |
| Extraction | structured facts | reviewed extraction gold | component F1, exact match, evidence faithfulness |
| Planning | executable operations | reviewed/oracle plans | validity, operation and dependency accuracy |
| Reliability | answer or abstention | supported-scope labels | coverage, risk at coverage, critical-error rate |

## Experiment discipline

- Develop prompts and systems on the 30-case development split only.
- Do not inspect test answers during development.
- Freeze prompts, model/version, decoding parameters, corpus/index, and code
  before the 120-case held-out test run.
- Run B0, B1, and IGEP on the same split and report paired bootstrap confidence
  intervals over cases.
- Preserve predictions and traces for every reported run.
- Extraction diagnostic scores built from prediction-initialized annotations
  are not publication results until the semantic gold is independently checked.
