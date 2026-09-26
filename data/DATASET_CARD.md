# IGEP inheritance benchmark — dataset card

## Scope

The benchmark contains 150 Vietnamese inheritance-law cases from two source
groups: 129 cases derived from published court judgments and 21 legal-education
cases (15 from Hue University of Law and 6 from the University of Economics and
Law, VNU-HCM). Each runtime record exposes `source_type` as either
`court_judgment_derived` or `legal_education_case`.

The reference side contains statutory articles and a recipient–amount
allocation. `reference_origin` distinguishes a `court_adjudicated_outcome`
from a `reviewed_educational_answer`.

The neutral name for the label across the complete dataset is **reference
allocation**. Only the court-derived subset may be described as containing a
court-adjudicated outcome. Neither group is presented as universal legal truth.

## Independent review

All 150 cases were independently checked by four reviewers. The reviewer panel
had the following anonymized qualifications at the time of review:

- Reviewer R1 had previously authored a publication on a Vietnamese-law
  benchmark;
- Reviewer R2 was the top-ranked graduate of a law programme;
- Reviewers R3 and R4 were university students.

The confirmed review covers the benchmark-level artifacts: the sanitized case
text, reference statutory articles, and reference allocation. This statement
does not imply that every field created later by automatic migration into the
full extraction schema was independently re-annotated by the same reviewers.

No numerical inter-annotator-agreement value is reported because the repository
does not contain the four pre-consensus annotation versions needed to calculate
it retrospectively. The paper must not invent or estimate such a value.

## Canonical artifacts

- `canonical/input.jsonl`: runtime inputs without article or allocation labels,
  with an explicit `source_type`;
- `canonical/reference.jsonl`: independently reviewed article and allocation
  references, with an explicit `reference_origin`;
- `canonical/gold.json`: full-schema data
  produced by migration and deterministic repair;
- `review/review_manifest.csv`: per-case record of the confirmed review
  scope;
- `review/PROTOCOL.md`: review statement and reporting limits.

## Important distinction

Independent benchmark review and full-schema migration validation are different
claims:

1. `reference.jsonl` records have `audit_status=independently_reviewed` because
   all four reviewers checked the benchmark-level labels independently.
2. `gold.json` is produced by deterministic migration and repair. It must not
   be presented as independently re-annotated full-schema gold solely on the
   basis of the benchmark-level review.
3. Schema validity means that a record satisfies structural and graph
   constraints; it does not by itself establish semantic correctness.

## Known documentation gaps

The current repository does not preserve reviewer-specific annotation files,
individual disagreement decisions, review dates, or a case-level adjudication
log. If those records exist elsewhere, they should be archived in a private or
public provenance package before submission. Until then, claims in the paper
should be limited to the facts documented above.

## Intended use

The benchmark is intended for research on Vietnamese inheritance-law fact
extraction, statute retrieval, executable legal reasoning, and monetary
allocation. It should not be used to provide legal advice or decide real cases.

## Privacy, provenance, and licensing

The released inputs should remain sanitized and should not reintroduce personal
identifiers removed during benchmark construction. Before public release, the
authors must document the precise source judgment identifier or stable
educational source record for each case where legally and ethically permissible,
and state the applicable redistribution terms. These provenance and licensing
fields are not yet complete in the repository.
