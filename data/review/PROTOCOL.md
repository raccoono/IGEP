# Dataset review protocol and evidence statement

## Confirmed facts

- Population reviewed: all 150 benchmark cases.
- Review design: four reviewers checked the cases independently.
- Confirmed scope: sanitized case text, reference statutory articles, and
  reference allocation.
- Source composition: 129 `court_judgment_derived` cases and 21
  `legal_education_case` records.
- Reviewer qualifications are reported anonymously:
  - R1: prior author of a publication on a Vietnamese-law benchmark;
  - R2: top-ranked graduate of a law programme;
  - R3–R4: university students.

This file records information confirmed by the dataset author. It deliberately
does not add details that are not currently evidenced in the repository.

## Reporting rules

The paper may state:

> All 150 cases were independently checked by four reviewers. The panel
> comprised one reviewer with prior publication experience on a Vietnamese-law
> benchmark, one top-ranked law graduate, and two university students.

The paper should additionally distinguish the source of the reference:

> For court-derived cases, allocation labels encode the adjudicated outcome of
> the source case. For legal-education cases, they encode the reviewed answer
> supplied by the benchmark source. Both are treated as references rather than
> universal legal truth.

The paper must not currently claim:

- a numerical inter-annotator-agreement score;
- a particular voting, consensus, or adjudication procedure;
- that reviewer-specific labels were retained;
- that all fields introduced by automatic full-schema migration were reviewed
  independently by all four reviewers.

Those claims require the corresponding records to be added first.

## Artifact boundaries

| Artifact | Review interpretation |
|---|---|
| `data/canonical/input.jsonl` | Sanitized input checked as part of the benchmark review |
| `data/canonical/reference.jsonl` | Articles and allocation independently checked by four reviewers |
| `data/canonical/extraction_gold_eval.jsonl` | Legacy decoded pre-annotation; status retained separately |
| `data/canonical/gold.json` | Automatically migrated/repaired full-schema artifact; schema-valid is not synonymous with independently re-annotated |

## Missing records recommended before submission

If available, archive the following without rewriting history:

1. the four reviewer-specific annotation exports;
2. review dates and annotation instructions used at the time;
3. disagreement and final-resolution records;
4. stable source identifiers for each judgment or educational problem;
5. documentation of case selection and exclusion.

These records would allow reproducible agreement statistics and a stronger
dataset-quality claim. Their absence does not negate the confirmed independent
review, but it limits what can be quantitatively demonstrated.
