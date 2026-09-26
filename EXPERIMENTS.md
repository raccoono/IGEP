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

## B5 — Coordinated modular LLM baseline

```text
extractor agent
→ legal-issue/retrieval agent
→ allocation-reasoning agent
→ verification agent
→ final heir-to-amount allocation
```

Each role has a fixed prompt and structured hand-off. This is the coordinated
multi-agent-style baseline. It must use the same underlying model, temperature,
legal corpus, and final answer schema as B0 wherever possible so that the
comparison measures orchestration rather than unrelated resource changes.

The initial B5 baseline may allow its allocation agent to calculate the final
amounts. The proposed IGEP method can then replace or constrain individual
modules with validated extraction, temporal retrieval, an executable plan, a
deterministic executor, and bounded repair.

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
