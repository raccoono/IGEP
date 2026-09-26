# Canonical artifacts

Generated files used by experiments:

- `input.jsonl`: model inputs without answer labels.
- `reference.jsonl`: reviewed articles and monetary allocations.
- `gold.json`: full extraction-schema gold produced deterministically.
- `temporal.jsonl`: opening-level, time-aware citation references.

The editable benchmark source is `../benchmark.csv`. Rebuild in order:

```bash
python3 scripts/repair_benchmark.py
python3 scripts/repair_extraction.py
python3 scripts/build_canonical.py
python3 scripts/build_gold.py
python3 scripts/build_temporal_map.py
python3 scripts/build_temporal.py
```

Do not edit generated files directly. Human citation decisions belong in
`../review/citation_reviews.json`.
