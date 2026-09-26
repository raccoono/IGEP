# IGEP

Research code and private data for a temporally aware Vietnamese inheritance-law
benchmark and reasoning pipeline.

## Essential layout

- `DESIGN.md`: system design.
- `EXPERIMENTS.md`: baseline definitions, outputs and evaluation levels.
- `ROADMAP.md`: research and publication plan.
- `data/benchmark.csv`: editable benchmark source.
- `data/canonical/`: experiment-ready input, references and extraction gold.
- `data/legal_corpus/`: official statutes, normalized corpus and crosswalk.
- `data/review/`: human review decisions and generated audit queue.
- `data/release/`: frozen split, statistics, provenance, licensing decision and checksums.
- `schema/`: extraction specification and schemas.
- `scripts/`: deterministic build, validation, run and evaluation commands.
- `taxonomy/frozen/`: frozen label taxonomy.
- `tests/`: evaluator tests.

## Rebuild and verify

```bash
python3 scripts/repair_benchmark.py
python3 scripts/repair_extraction.py
python3 scripts/build_canonical.py
python3 scripts/build_gold.py
python3 scripts/build_temporal_map.py
python3 scripts/build_temporal.py
python3 scripts/validate_corpus.py
python3 -m unittest discover -s tests -v
```

Research data are ignored by Git pending an explicit release and licensing
decision. Do not publish source documents, benchmark cases, or gold labels by
default.

## Current experiment status

`data/runs/extraction_dev_igep.jsonl` is an extraction-module run. Its result is
a structured fact graph, not the final list of heirs and distributed amounts.
The monolithic end-to-end baseline (B0) and coordinated modular baseline (B5)
defined in `EXPERIMENTS.md` have not yet been run. B0 is now runnable on the
development split:

```bash
python3 scripts/run.py allocate \
  --method b0 \
  --split development \
  --output data/runs/allocation_dev_b0.jsonl \
  --trace data/runs/allocation_dev_b0.trace.jsonl

python3 scripts/evaluate_allocation.py \
  --predictions data/runs/allocation_dev_b0.jsonl \
  --split development \
  --output-json data/eval/allocation_dev_b0.json \
  --output-md data/eval/allocation_dev_b0.md
```

B2 reuses the same model and allocation schema, adding only deterministic
BM25 top-5 context from `data/legal_corpus/normalized/statutes.jsonl`:

```bash
python3 scripts/run.py allocate \
  --method b2 \
  --split development \
  --output data/runs/allocation_dev_b2.jsonl \
  --trace data/runs/allocation_dev_b2.trace.jsonl
```

B4 changes only retrieval: it fuses BM25 and Voyage dense candidate rankings
with reciprocal rank fusion, then supplies the fused top-5 to the same direct
allocation LLM and allocation schema used by B2. Corpus embeddings are cached
locally under the ignored `data/cache/` directory.

```bash
# No credentials or API calls; uses deterministic fake embeddings.
python3 scripts/run.py allocate --method b4 --split development --limit 1 --dry-run

# Actual development experiment (run by the researcher after review).
python3 scripts/run.py allocate \
  --method b4 \
  --split development \
  --output data/runs/allocation_dev_b4.jsonl \
  --trace data/runs/allocation_dev_b4.trace.jsonl
```

B4 has no structured extraction, issue classification, planning, deterministic
execution, verification, answer repair, or abstention stage.

### B5 — Coordinated Modular LLM

B5 keeps B4's frozen hybrid retrieval unchanged and replaces the single direct
allocation call with four coordinated LLM calls: structured case extraction,
inheritance-issue analysis, statute-aware reasoning, and coordinated final
allocation. The final module uses the same allocation schema and evaluator as
B0/B2/B4. Traces retain every intermediate output, response ID, module usage,
total usage, execution order, retrieval IDs, validation errors, and runtime
errors.

```bash
# Offline construction check using deterministic fake embeddings.
python3 scripts/run.py allocate --method b5 --split development --limit 1 --dry-run

# Actual development experiment (run only after implementation review).
python3 scripts/run.py allocate \
  --method b5 \
  --split development \
  --output data/runs/allocation_dev_b5.jsonl \
  --trace data/runs/allocation_dev_b5.trace.jsonl
```

B5 is an LLM coordination baseline, not IGEP: it has no deterministic executor,
executable operation plan, post-execution verifier, repair/re-execution loop, or
formal abstention mechanism.
