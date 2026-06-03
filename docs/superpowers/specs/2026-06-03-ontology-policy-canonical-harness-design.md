# Ontology Policy Canonical Harness Design

## Goal

Add a new ontology-policy driven comparison path that improves the current harness without hard-coding the current 30 golden cases.

The current `harness+norm` path relies heavily on Claude normalization and judge behavior. The new path moves first-line normalization and comparison into deterministic code driven by field policies. LLM judge remains only as a fallback for fields where deterministic canonicalization is not decisive.

## Non-Goals

- Do not remove or rewrite the existing `baseline`, `guard`, or `harness+norm` paths.
- Do not tune logic by `case_id`, `golden_master.csv` rows, exact full raw strings, page numbers, or the current PDF layout.
- Do not implement full entity alias resolution in the first pass.
- Do not use Claude normalization in the new ontology-policy path.
- Do not make TTL/SHACL the only executable policy source in this iteration.

## Source Of Truth

The design uses three layers:

- `ontology/trust_fund.ttl`: concept model.
- `ontology/shapes.ttl`: structural and business validation rules.
- `ontology/field_policies.yaml`: executable ontology policy for canonicalization, comparison, absence semantics, and judge fallback.

`field_policies.yaml` is limited to the current `ExtractionResult` 14 fields, but each policy must be written as a fund/trust-domain rule, not a rule for the current report or golden set.

## New Modes

Add two score modes:

- `ontology_policy`: deterministic path only.
- `ontology_policy_judge`: deterministic path plus Claude judge fallback.

`ontology_policy` runs quickly and should not require external LLM calls. `ontology_policy_judge` is the final comparison mode and only calls judge for non-decisive fields whose policy allows it.

## Pipeline

`ontology_policy`:

```text
ExtractionResult
-> G1/G2/G3 guards
-> field policy lookup
-> canonicalization
-> deterministic comparison
-> decisive result or needs_review
-> score
```

`ontology_policy_judge`:

```text
ExtractionResult
-> G1/G2/G3 guards
-> field policy lookup
-> canonicalization
-> deterministic comparison
-> decisive result: final, no LLM call
-> non-decisive + judge_allowed=true: Claude judge fallback
-> non-decisive + judge_allowed=false: needs_review
-> score
```

Decisive canonical results cannot be overturned by LLM output.

## Canonical Package

Create `src/canonical/`:

- `types.py`: `FieldPolicy`, `CanonicalValue`, `CanonicalComparison`.
- `policy.py`: load and validate `ontology/field_policies.yaml`.
- `parsers.py`: deterministic parsers for percent, date, duration, boolean, and absence.
- `compare.py`: policy-based comparison.
- `pipeline.py`: bridge from `ExtractionResult` to `CrossCheckResult`-compatible outputs.

The canonical layer does not extract values from PDFs. It only interprets already extracted evidence.

## Field Policy

Register all 14 fields. Each policy includes:

- `label`
- `value_type`
- `canonicalizer`
- `compare_policy`
- `judge_allowed`
- `absence_semantics`
- optional range or derivation settings

First-pass canonicalizers:

- Percent fields: management fee, trust fee, sales fee, redemption fee.
- Date fields: inception date, maturity date.
- Duration fields: lockup period and maturity-date derivation when explicitly tied to inception date.
- Boolean field: redeemable flag.
- Absence semantics: field-specific handling of "없음", "해당 없음", "부과하지 아니함", and similar expressions.

First-pass judge fallback fields:

- `fund.name`
- `fund.type`
- `party.asset_manager`
- `party.trustee`
- `party.distributor`
- `redemption_terms.redemption_cycle`

These fields are policy-routed to judge fallback when raw exact match is not enough. They are not fully canonicalized in this iteration.

## Percent Policy

Deterministic percent canonicalization only accepts explicit units:

- `%`
- `bp` / basis point
- `1,000분의`, `1000분의`, `1천분의`

Unitless decimal values such as `0.0089` are not interpreted by deterministic code. They remain non-decisive and can go to judge fallback only when the field policy allows it.

This avoids pretending unitless numbers are safe while still making explicit domain units robust across IM formats.

## Date And Duration Policy

Absolute dates are canonicalized when written as ISO, dotted dates, slash dates, or Korean date expressions.

`lockup_period` canonicalizes standalone durations such as `3년` and `36개월`.

`fund.maturity_date` supports derived dates only when the raw text explicitly references inception date, such as:

- `설정일로부터 3년`
- `최초설정일로부터 36개월`

Derivation uses the same side's `fund.inception_date`:

- contract maturity uses contract inception.
- IM maturity uses IM inception.

Standalone maturity values such as `3년` or `36개월` are non-decisive and use judge fallback when allowed.

## Absence Semantics

Absence is field-specific:

- Some fee fields can interpret "없음", "해당 없음", "부과하지 아니함", or similar expressions as zero value.
- Required entity/name fields interpret absence expressions as missing evidence.
- Boolean fields can map absence-like or negative expressions to false when the policy explicitly allows it.

The same raw phrase can therefore produce different canonical meaning depending on field policy.

## CrossCheckResult Extension

Keep existing `CrossCheckResult` fields and add optional canonical evidence:

- `canonical_status`
- `canonical_reason_code`
- `canonical`

Existing scoring continues to use `final_status` and `guard_rejections`. The canonical fields provide machine-readable explanation and debugging evidence.

## Overfitting Guardrails

Implementation must not:

- Branch on `case_id`.
- Read or encode `golden_master.csv` rows as logic.
- Match exact full raw strings from the current report.
- Use current page numbers, current PDF filenames, or current table positions as policy.
- Add rules named after C021, C030, or any golden case.

Implementation may:

- Parse general expression families such as percent, permille, basis point, date, duration, boolean, and absence phrases.
- Use field meaning from `field_policies.yaml`.
- Use domain-level constraints such as value type, range, requiredness, and comparison policy.

`golden_master.csv` is a final scoring input, not a tuning source.

## Verification

Add focused tests for:

- Field policy loading and coverage of all 14 fields.
- Percent parser expression families.
- Date and duration parser expression families.
- Field-specific absence semantics.
- Canonical comparison decisive and non-decisive behavior.
- Judge fallback routing without calling judge for decisive canonical results.
- Existing scoring compatibility.

Run:

```bash
python -m pytest -q
python -m src.cli score --mode ontology_policy --out reports/scoring/score_ontology_policy.json
python scripts/score_ontology_policy.py
```

The final comparison should include existing modes plus:

- `ontology_policy`
- `ontology_policy_judge`

Target for the current provisional golden set:

- `ontology_policy_judge` F1 >= current `harness+norm` F1.
- Recall >= current `harness+norm` recall.
- Unit-trap false negatives are removed by general explicit-unit parsing, not by case-specific logic.
- Claude judge calls are fewer than current `harness+norm`.
