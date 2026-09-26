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
