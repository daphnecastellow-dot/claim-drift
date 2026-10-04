# Claim Drift

**Version:** 0.1  
**Status:** experimental

Claim Drift tracks **how claims change across versions** without treating every change as deception, error, or fabrication.

Sourceweave can show where a detail enters a source lineage. Claim Drift looks more closely at the transformation itself:

> **What changed between one version and the next?**

A claim may gain specificity, lose a qualifier, become more certain, acquire a cause, shift a date, substitute an identity, or intensify its wording. Claim Drift preserves those changes explicitly.

## Drift types

Claim Drift supports:

- `addition`
- `omission`
- `intensification`
- `attenuation`
- `certainty-shift`
- `causal-shift`
- `identity-shift`
- `temporal-shift`
- `location-shift`
- `quantity-shift`
- `sequence-shift`
- `semantic-substitution`
- `other`

These are **descriptions of textual or narrative change**, not judgments about motive or truth.

## What it records

A project contains:

- sources
- claim versions
- explicit version-to-version transitions
- one or more drift observations per transition
- the text before and after each observed change
- notes explaining why the change was classified that way

## Quick start

```bash
python claim_drift.py new drift.json --title "North Reach door story"

python claim_drift.py source drift.json "1904 station log" \
  --kind primary --date 1904-11-03

python claim_drift.py version drift.json \
  "The north door was open." \
  --source S001

python claim_drift.py version drift.json \
  "The locked north door had been forced open." \
  --source S002

python claim_drift.py drift drift.json V001 V002 \
  --type addition \
  --before "door" \
  --after "locked north door" \
  --note "The later wording introduces a lock state."

python claim_drift.py drift drift.json V001 V002 \
  --type causal-shift \
  --before "was open" \
  --after "had been forced open" \
  --note "The later wording adds an implied mechanism."

python claim_drift.py render drift.json -o report.md
python claim_drift.py timeline drift.json -o timeline.md
python claim_drift.py mermaid drift.json -o drift.mmd
python claim_drift.py audit drift.json
```

## Outputs

Claim Drift can produce:

- plain JSON
- a Markdown report
- a compact chronological/version timeline
- a Mermaid transition graph
- a structural audit

## Audit behavior

The audit checks the recorded drift structure, not historical truth.

It can flag:

- a version with no source
- a transition with no drift observations
- a transition that points from a later dated source to an earlier dated source
- a drift observation with no note explaining the classification

A flag does not mean the version is false. It means the transformation record may need more context.

## Example

The fictional example in [`examples/demo.json`](examples/demo.json) follows a door description through four retellings:

`open` → `found open` → `locked door forced open` → `door violently smashed inward`

The example records exactly what changed at each step without inferring intent.

See:

- [`examples/demo.md`](examples/demo.md)
- [`examples/demo.mmd`](examples/demo.mmd)

## What Claim Drift does not do

Claim Drift does not automatically detect lies.

It does not assume later versions are worse than earlier ones.

It does not treat vivid wording as proof of fabrication.

It does not infer motive from narrative change.

It does not replace source-lineage work.

It records the mutation so the researcher can inspect what changed before deciding why.

## Tests

```bash
python -m unittest discover -s tests -v
```

## License and reuse

**No reuse license has been granted.**

This public build is available for inspection and development by its maintainers. Do not assume that public visibility grants permission to copy, redistribute, modify, sell, incorporate, or relicense the code or documentation.

See [`COPYRIGHT.md`](COPYRIGHT.md).

## Working principle

Do not call it a new story until you can show what changed.
