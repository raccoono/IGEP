# Review artifacts

- `PROTOCOL.md`: review scope and reporting limits.
- `review_manifest.csv`: benchmark-level review status per case.
- `temporal_map.csv`: succession openings and applicable legal regimes.
- `citation_reviews.json`: durable human overrides for temporal citations.
- `citation_audit.csv`: generated review queue and current decisions.
- `dev_gold_approval.md`: approved semantic-annotation decisions for the
  30-case development split.
- `dev_gold_full_review.md`: consolidated development-gold and diagnostic
  evaluation review packet.
- `dev_gold_evidence.jsonl`: exact evidence spans for development semantic
  facts.

Only `citation_reviews.json` should be edited when approving or revising
citations. Regenerate the temporal outputs with:

```bash
python3 scripts/build_temporal_map.py
python3 scripts/build_temporal.py
```

## Frozen temporal-citation audit

All 213 openings now have a recorded review decision. The statute-retrieval
evaluation population contains 158 openings. The other 55 are retained in the
benchmark but are not eligible for that metric:

- 31 undated openings already excluded by the temporal protocol;
- 13 pre-10/09/1990 openings requiring a composite historical corpus;
- 11 openings from eight cases whose citations were reviewed but whose facts or
  allocations still require case-level repair.

For the latter two groups, `review_status=reviewed` means that the audit reached
an explicit exclusion decision. It does not mean that missing historical law or
case-level allocation problems were silently resolved.
