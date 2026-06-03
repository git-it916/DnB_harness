# Ontology Policy Canonical Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `ontology_policy` and `ontology_policy_judge` scoring paths that use ontology field policy plus deterministic canonical comparison before limited LLM judge fallback.

**Architecture:** Keep existing `baseline`, `guard`, and `harness+norm` behavior intact. Add `ontology/field_policies.yaml` as executable field policy and a new `src/canonical/` package that converts extracted evidence into canonical values, compares them, and emits `CrossCheckResult`-compatible results. `ontology_policy_judge` reuses Claude judge only for non-decisive policy-allowed fields and never calls Claude normalization.

**Tech Stack:** Python 3.11, Pydantic models, PyYAML via existing dependencies if available or stdlib fallback not acceptable, Typer CLI, pytest.

---

## File Structure

- Create `ontology/field_policies.yaml`: executable policy for all 14 `ExtractionResult` fields.
- Create `src/canonical/__init__.py`: public canonical package exports.
- Create `src/canonical/types.py`: `FieldPolicy`, `CanonicalValue`, `CanonicalComparison`, enums.
- Create `src/canonical/policy.py`: load and validate field policy coverage.
- Create `src/canonical/parsers.py`: deterministic percent/date/duration/boolean/absence parsers.
- Create `src/canonical/compare.py`: compare canonical values under a field policy.
- Create `src/canonical/pipeline.py`: build policy-based `CrossCheckResult` records from `ExtractionResult`.
- Modify `src/pipelines/cross_check.py`: add optional canonical explanation fields to `CrossCheckResult`.
- Modify `src/scoring/evaluate.py`: add deterministic `ontology_policy` mode and judge fallback evaluator.
- Modify `src/cli/main.py`: accept `--mode ontology_policy`.
- Create `scripts/score_ontology_policy.py`: final scoring path with Claude judge fallback.
- Create tests under `tests/`: focused canonical and integration coverage.

---

### Task 1: Extend CrossCheckResult With Canonical Evidence

**Files:**
- Modify: `src/pipelines/cross_check.py`
- Test: `tests/test_cross_check.py`

- [ ] **Step 1: Write failing serialization test**

Append to `tests/test_cross_check.py`:

```python
def test_cross_check_result_accepts_optional_canonical_metadata():
    result = CrossCheckResult(
        field="fee_schedule.sales_fee",
        label="판매보수",
        status=CrossCheckStatus.NEEDS_REVIEW,
        missing_side=MissingSide.NONE,
        final_status=FinalCheckStatus.SAME_AFTER_NORMALIZATION,
        final_reason_code="canonical_numeric_equal",
        final_reason="Canonical values are equal after explicit unit conversion.",
        canonical_status="decisive",
        canonical_reason_code="numeric_equal_after_unit_conversion",
        canonical={
            "contract": {"value": "0.3", "unit": "percent_per_year"},
            "im": {"value": "0.3", "unit": "percent_per_year"},
        },
        contract=CrossCheckValue(raw_text="연 1,000분의 3", citation=None),
        im=CrossCheckValue(raw_text="연 0.3%", citation=None),
    )

    dumped = result.model_dump()
    assert dumped["canonical_status"] == "decisive"
    assert dumped["canonical"]["contract"]["value"] == "0.3"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python -m pytest tests/test_cross_check.py::test_cross_check_result_accepts_optional_canonical_metadata -q
```

Expected: fail because `CrossCheckResult` forbids extra fields.

- [ ] **Step 3: Add optional fields**

In `src/pipelines/cross_check.py`, update `CrossCheckResult`:

```python
class CrossCheckResult(StrictResultModel):
    field: str
    label: str
    status: CrossCheckStatus
    missing_side: MissingSide
    normalization_status: str | None = None
    final_status: FinalCheckStatus | None = None
    final_reason_code: str | None = None
    final_reason: str | None = None
    canonical_status: str | None = None
    canonical_reason_code: str | None = None
    canonical: dict[str, Any] | None = None
    contract: CrossCheckValue
    im: CrossCheckValue
```

- [ ] **Step 4: Run test**

Run:

```bash
python -m pytest tests/test_cross_check.py::test_cross_check_result_accepts_optional_canonical_metadata -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/pipelines/cross_check.py tests/test_cross_check.py
git commit -m "feat: add canonical metadata to cross check results"
```

---

### Task 2: Add Field Policy File And Loader

**Files:**
- Create: `ontology/field_policies.yaml`
- Create: `src/canonical/__init__.py`
- Create: `src/canonical/types.py`
- Create: `src/canonical/policy.py`
- Test: `tests/test_canonical_policy.py`

- [ ] **Step 1: Write failing policy tests**

Create `tests/test_canonical_policy.py`:

```python
from src.canonical.policy import load_field_policies


EXPECTED_FIELDS = {
    "fund.name",
    "fund.type",
    "fund.inception_date",
    "fund.maturity_date",
    "party.asset_manager",
    "party.trustee",
    "party.distributor",
    "fee_schedule.management_fee",
    "fee_schedule.trust_fee",
    "fee_schedule.sales_fee",
    "redemption_terms.is_redeemable",
    "redemption_terms.lockup_period",
    "redemption_terms.redemption_cycle",
    "redemption_terms.redemption_fee",
}


def test_field_policies_cover_all_extraction_fields():
    policies = load_field_policies()
    assert set(policies) == EXPECTED_FIELDS


def test_fee_policy_allows_judge_fallback_and_uses_percent_canonicalizer():
    policies = load_field_policies()
    sales_fee = policies["fee_schedule.sales_fee"]
    assert sales_fee.value_type == "percent_per_year"
    assert sales_fee.canonicalizer == "percent"
    assert sales_fee.compare_policy == "numeric_equal"
    assert sales_fee.judge_allowed is True


def test_entity_policy_routes_to_judge_fallback():
    policies = load_field_policies()
    trustee = policies["party.trustee"]
    assert trustee.canonicalizer == "none"
    assert trustee.compare_policy == "judge_fallback"
    assert trustee.judge_allowed is True
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python -m pytest tests/test_canonical_policy.py -q
```

Expected: fail because `src.canonical` does not exist.

- [ ] **Step 3: Create policy YAML**

Create `ontology/field_policies.yaml`:

```yaml
fund.name:
  label: 펀드명
  value_type: text
  canonicalizer: none
  compare_policy: judge_fallback
  judge_allowed: true
  absence_semantics: missing_evidence

fund.type:
  label: 펀드 유형
  value_type: text
  canonicalizer: none
  compare_policy: judge_fallback
  judge_allowed: true
  absence_semantics: missing_evidence

fund.inception_date:
  label: 설정일
  value_type: date
  canonicalizer: date
  compare_policy: date_equal
  judge_allowed: false
  absence_semantics: missing_evidence

fund.maturity_date:
  label: 만기일
  value_type: date
  canonicalizer: maturity_date
  compare_policy: date_equal
  judge_allowed: true
  absence_semantics: missing_evidence
  derive_from: fund.inception_date

party.asset_manager:
  label: 운용사
  value_type: entity_name
  canonicalizer: none
  compare_policy: judge_fallback
  judge_allowed: true
  absence_semantics: missing_evidence

party.trustee:
  label: 신탁업자
  value_type: entity_name
  canonicalizer: none
  compare_policy: judge_fallback
  judge_allowed: true
  absence_semantics: missing_evidence

party.distributor:
  label: 판매사
  value_type: entity_name
  canonicalizer: none
  compare_policy: judge_fallback
  judge_allowed: true
  absence_semantics: missing_evidence

fee_schedule.management_fee:
  label: 운용보수
  value_type: percent_per_year
  canonicalizer: percent
  compare_policy: numeric_equal
  judge_allowed: true
  absence_semantics: missing_evidence
  range: {min: 0, max: 5}

fee_schedule.trust_fee:
  label: 신탁보수
  value_type: percent_per_year
  canonicalizer: percent
  compare_policy: numeric_equal
  judge_allowed: true
  absence_semantics: missing_evidence
  range: {min: 0, max: 2}

fee_schedule.sales_fee:
  label: 판매보수
  value_type: percent_per_year
  canonicalizer: percent
  compare_policy: numeric_equal
  judge_allowed: true
  absence_semantics: missing_evidence
  range: {min: 0, max: 3}

redemption_terms.is_redeemable:
  label: 환매 가능 여부
  value_type: boolean
  canonicalizer: boolean
  compare_policy: boolean_equal
  judge_allowed: false
  absence_semantics: missing_evidence

redemption_terms.lockup_period:
  label: 락업 기간
  value_type: duration
  canonicalizer: duration
  compare_policy: duration_equal
  judge_allowed: false
  absence_semantics: missing_evidence

redemption_terms.redemption_cycle:
  label: 환매 주기
  value_type: text
  canonicalizer: none
  compare_policy: judge_fallback
  judge_allowed: true
  absence_semantics: missing_evidence

redemption_terms.redemption_fee:
  label: 환매수수료
  value_type: percent_per_year
  canonicalizer: percent
  compare_policy: numeric_equal
  judge_allowed: true
  absence_semantics: zero_value
  range: {min: 0, max: 100}
```

- [ ] **Step 4: Create canonical types and loader**

Create `src/canonical/types.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class FieldPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value_type: str
    canonicalizer: str
    compare_policy: str
    judge_allowed: bool
    absence_semantics: str
    range: dict[str, float] | None = None
    derive_from: str | None = None


class CanonicalValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    value: str | None = None
    unit: str | None = None
    method: str | None = None
    reason_code: str
    reason: str
    metadata: dict[str, Any] = {}


class CanonicalComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    final_status: str
    reason_code: str
    reason: str
    contract: CanonicalValue
    im: CanonicalValue
    judge_allowed: bool
```

Create `src/canonical/policy.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from src.canonical.types import FieldPolicy

DEFAULT_POLICY_PATH = Path("ontology/field_policies.yaml")


def load_field_policies(path: Path = DEFAULT_POLICY_PATH) -> dict[str, FieldPolicy]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"field policy file must contain a mapping: {path}")
    return {
        str(field): FieldPolicy.model_validate(payload)
        for field, payload in data.items()
    }
```

Create `src/canonical/__init__.py`:

```python
"""Ontology policy canonicalization package."""

from src.canonical.policy import load_field_policies
from src.canonical.types import CanonicalComparison, CanonicalValue, FieldPolicy

__all__ = [
    "CanonicalComparison",
    "CanonicalValue",
    "FieldPolicy",
    "load_field_policies",
]
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_canonical_policy.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add ontology/field_policies.yaml src/canonical tests/test_canonical_policy.py
git commit -m "feat: add ontology field policy loader"
```

---

### Task 3: Implement Canonical Parsers

**Files:**
- Create: `src/canonical/parsers.py`
- Test: `tests/test_canonical_parsers.py`

- [ ] **Step 1: Write failing parser tests**

Create `tests/test_canonical_parsers.py`:

```python
from src.canonical.parsers import (
    parse_boolean,
    parse_date,
    parse_duration_months,
    parse_percent,
)


def test_parse_percent_explicit_units():
    assert parse_percent("연 0.89%").value == "0.89"
    assert parse_percent("[운용] 연[ 0.89 ] %").value == "0.89"
    assert parse_percent("연 1,000분의 8.9").value == "0.89"
    assert parse_percent("연 1000분의 8.9").value == "0.89"
    assert parse_percent("연 1천분의 8.9").value == "0.89"
    assert parse_percent("89bp").value == "0.89"


def test_parse_percent_unitless_decimal_is_ambiguous():
    result = parse_percent("0.0089")
    assert result.status == "non_decisive"
    assert result.reason_code == "percent_unit_missing"


def test_parse_date_common_formats():
    assert parse_date("2025-07-22").value == "2025-07-22"
    assert parse_date("2025.07.22").value == "2025-07-22"
    assert parse_date("2025/07/22").value == "2025-07-22"
    assert parse_date("2025년 7월 22일").value == "2025-07-22"


def test_parse_duration_months_years_and_months():
    assert parse_duration_months("3년").value == "36"
    assert parse_duration_months("36개월").value == "36"
    assert parse_duration_months("1년 6개월").value == "18"


def test_parse_boolean_korean_expressions():
    assert parse_boolean("환매 가능").value == "true"
    assert parse_boolean("환매 불가").value == "false"
    assert parse_boolean("환매할 수 없음").value == "false"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python -m pytest tests/test_canonical_parsers.py -q
```

Expected: fail because parsers do not exist.

- [ ] **Step 3: Implement parsers**

Create `src/canonical/parsers.py`:

```python
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from src.canonical.types import CanonicalValue

_PERCENT_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*%")
_PERMILLE_RE = re.compile(r"(?:1[,，]?000|1000|1\s*천)\s*분의\s*([0-9]+(?:\.[0-9]+)?)")
_BP_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(?:bp|bps|basis\s*points?)", re.IGNORECASE)
_KR_DATE_RE = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_DURATION_YEAR_RE = re.compile(r"([0-9]+)\s*년")
_DURATION_MONTH_RE = re.compile(r"([0-9]+)\s*개월")


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


def _parsed(value: str, unit: str, method: str, reason_code: str, reason: str) -> CanonicalValue:
    return CanonicalValue(
        status="decisive",
        value=value,
        unit=unit,
        method=method,
        reason_code=reason_code,
        reason=reason,
    )


def _non_decisive(reason_code: str, reason: str) -> CanonicalValue:
    return CanonicalValue(
        status="non_decisive",
        reason_code=reason_code,
        reason=reason,
    )


def parse_percent(raw: str | None) -> CanonicalValue:
    if raw is None or not raw.strip():
        return _non_decisive("missing_raw_text", "Raw text is missing.")
    text = raw.replace("，", ",")
    percent_text = re.sub(r"[\[\]()]", " ", text)

    match = _PERCENT_RE.search(percent_text)
    if match:
        return _parsed(match.group(1), "percent_per_year", "percent", "percent_unit", "Explicit percent unit.")

    match = _PERMILLE_RE.search(text)
    if match:
        value = Decimal(match.group(1)) / Decimal("10")
        return _parsed(_decimal_text(value), "percent_per_year", "permille", "permille_unit", "Explicit permille expression.")

    match = _BP_RE.search(text)
    if match:
        value = Decimal(match.group(1)) / Decimal("100")
        return _parsed(_decimal_text(value), "percent_per_year", "basis_point", "basis_point_unit", "Explicit basis point unit.")

    if re.fullmatch(r"\s*[0-9]+(?:\.[0-9]+)?\s*", text):
        return _non_decisive("percent_unit_missing", "Unitless numeric percent evidence is ambiguous.")
    return _non_decisive("percent_unparseable", "No explicit percent, permille, or basis point unit was found.")


def parse_date(raw: str | None) -> CanonicalValue:
    if raw is None or not raw.strip():
        return _non_decisive("missing_raw_text", "Raw text is missing.")
    text = raw.strip()
    for pattern in (r"(\d{4})-(\d{1,2})-(\d{1,2})", r"(\d{4})\.(\d{1,2})\.(\d{1,2})", r"(\d{4})/(\d{1,2})/(\d{1,2})"):
        match = re.search(pattern, text)
        if match:
            return _date_from_parts(match.groups(), "absolute_date")
    match = _KR_DATE_RE.search(text)
    if match:
        return _date_from_parts(match.groups(), "korean_date")
    return _non_decisive("date_unparseable", "No supported absolute date expression was found.")


def _date_from_parts(parts: tuple[str, str, str], method: str) -> CanonicalValue:
    try:
        y, m, d = (int(p) for p in parts)
        parsed = date(y, m, d)
    except ValueError:
        return _non_decisive("date_invalid", "Date components do not form a valid date.")
    return _parsed(parsed.isoformat(), "date", method, "date_parsed", "Absolute date parsed.")


def parse_duration_months(raw: str | None) -> CanonicalValue:
    if raw is None or not raw.strip():
        return _non_decisive("missing_raw_text", "Raw text is missing.")
    text = raw.strip()
    years = sum(int(m.group(1)) for m in _DURATION_YEAR_RE.finditer(text))
    months = sum(int(m.group(1)) for m in _DURATION_MONTH_RE.finditer(text))
    total = years * 12 + months
    if total <= 0:
        return _non_decisive("duration_unparseable", "No supported duration expression was found.")
    return _parsed(str(total), "months", "duration", "duration_parsed", "Duration parsed as months.")


def parse_boolean(raw: str | None) -> CanonicalValue:
    if raw is None or not raw.strip():
        return _non_decisive("missing_raw_text", "Raw text is missing.")
    text = re.sub(r"\s+", "", raw)
    if any(token in text for token in ("불가", "불가능", "없음", "아니", "제한")):
        return _parsed("false", "boolean", "boolean", "boolean_false", "Negative boolean expression.")
    if any(token in text for token in ("가능", "허용", "할수있")):
        return _parsed("true", "boolean", "boolean", "boolean_true", "Positive boolean expression.")
    return _non_decisive("boolean_unparseable", "No supported boolean expression was found.")
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_canonical_parsers.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/canonical/parsers.py tests/test_canonical_parsers.py
git commit -m "feat: add deterministic canonical parsers"
```

---

### Task 4: Implement Policy-Based Canonical Comparison

**Files:**
- Create: `src/canonical/compare.py`
- Test: `tests/test_canonical_compare.py`

- [ ] **Step 1: Write failing comparison tests**

Create `tests/test_canonical_compare.py`:

```python
from src.canonical.compare import compare_values
from src.canonical.policy import load_field_policies


def test_percent_explicit_units_compare_same():
    policy = load_field_policies()["fee_schedule.management_fee"]
    result = compare_values(
        "fee_schedule.management_fee",
        policy,
        "연 1,000분의 8.9",
        "[운용] 연[ 0.89 ] %",
    )
    assert result.status == "decisive"
    assert result.final_status == "same_after_normalization"
    assert result.reason_code == "canonical_numeric_equal"


def test_percent_explicit_units_compare_different():
    policy = load_field_policies()["fee_schedule.sales_fee"]
    result = compare_values("fee_schedule.sales_fee", policy, "0.3%", "0.03%")
    assert result.status == "decisive"
    assert result.final_status == "different_after_normalization"
    assert result.reason_code == "canonical_numeric_difference"


def test_percent_unitless_value_is_not_decisive():
    policy = load_field_policies()["fee_schedule.sales_fee"]
    result = compare_values("fee_schedule.sales_fee", policy, "0.003", "0.3%")
    assert result.status == "non_decisive"
    assert result.final_status == "needs_review"


def test_duration_values_compare_same():
    policy = load_field_policies()["redemption_terms.lockup_period"]
    result = compare_values("redemption_terms.lockup_period", policy, "3년", "36개월")
    assert result.status == "decisive"
    assert result.final_status == "same_after_normalization"


def test_boolean_values_compare_different():
    policy = load_field_policies()["redemption_terms.is_redeemable"]
    result = compare_values("redemption_terms.is_redeemable", policy, "환매 가능", "환매 불가")
    assert result.status == "decisive"
    assert result.final_status == "different_after_normalization"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python -m pytest tests/test_canonical_compare.py -q
```

Expected: fail because `src.canonical.compare` does not exist.

- [ ] **Step 3: Implement comparison**

Create `src/canonical/compare.py`:

```python
from __future__ import annotations

from decimal import Decimal

from src.canonical.parsers import parse_boolean, parse_date, parse_duration_months, parse_percent
from src.canonical.types import CanonicalComparison, CanonicalValue, FieldPolicy
from src.pipelines.cross_check import FinalCheckStatus


def compare_values(
    field: str,
    policy: FieldPolicy,
    contract_raw: str | None,
    im_raw: str | None,
) -> CanonicalComparison:
    contract = canonicalize_value(field, policy, contract_raw)
    im = canonicalize_value(field, policy, im_raw)

    if contract.status != "decisive" or im.status != "decisive":
        return CanonicalComparison(
            status="non_decisive",
            final_status=str(FinalCheckStatus.NEEDS_REVIEW),
            reason_code="canonical_not_decisive",
            reason="One or both sides could not be canonicalized decisively.",
            contract=contract,
            im=im,
            judge_allowed=policy.judge_allowed,
        )

    same = contract.unit == im.unit and contract.value == im.value
    if same:
        return CanonicalComparison(
            status="decisive",
            final_status=str(FinalCheckStatus.SAME_AFTER_NORMALIZATION),
            reason_code=_same_reason(policy.compare_policy),
            reason="Canonical values are equal under field policy.",
            contract=contract,
            im=im,
            judge_allowed=policy.judge_allowed,
        )
    return CanonicalComparison(
        status="decisive",
        final_status=str(FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION),
        reason_code=_different_reason(policy.compare_policy),
        reason="Canonical values differ under field policy.",
        contract=contract,
        im=im,
        judge_allowed=policy.judge_allowed,
    )


def canonicalize_value(field: str, policy: FieldPolicy, raw: str | None) -> CanonicalValue:
    absence = canonicalize_absence(policy, raw)
    if absence is not None:
        return absence
    if policy.canonicalizer == "percent":
        return parse_percent(raw)
    if policy.canonicalizer == "date":
        return parse_date(raw)
    if policy.canonicalizer == "duration":
        return parse_duration_months(raw)
    if policy.canonicalizer == "boolean":
        return parse_boolean(raw)
    return CanonicalValue(
        status="non_decisive",
        reason_code="canonicalizer_not_configured",
        reason=f"No deterministic canonicalizer is configured for {field}.",
    )


def canonicalize_absence(policy: FieldPolicy, raw: str | None) -> CanonicalValue | None:
    if raw is None:
        return CanonicalValue(
            status="non_decisive",
            reason_code="missing_raw_text",
            reason="Raw text is missing.",
        )
    text = raw.strip()
    if not text:
        return CanonicalValue(
            status="non_decisive",
            reason_code="missing_raw_text",
            reason="Raw text is empty.",
        )
    compact = text.replace(" ", "")
    absence_tokens = ("없음", "해당없음", "해당사항없음", "부과하지아니함", "면제")
    if not any(token in compact for token in absence_tokens):
        return None
    if policy.absence_semantics == "zero_value":
        return CanonicalValue(
            status="decisive",
            value="0",
            unit=policy.value_type,
            method="absence_zero",
            reason_code="absence_as_zero",
            reason="Absence expression is configured as zero value for this field.",
        )
    return CanonicalValue(
        status="non_decisive",
        reason_code="absence_as_missing",
        reason="Absence expression is configured as missing evidence for this field.",
    )


def _same_reason(compare_policy: str) -> str:
    if compare_policy == "numeric_equal":
        return "canonical_numeric_equal"
    if compare_policy == "date_equal":
        return "canonical_date_equal"
    if compare_policy == "duration_equal":
        return "canonical_duration_equal"
    if compare_policy == "boolean_equal":
        return "canonical_boolean_equal"
    return "canonical_equal"


def _different_reason(compare_policy: str) -> str:
    if compare_policy == "numeric_equal":
        return "canonical_numeric_difference"
    if compare_policy == "date_equal":
        return "canonical_date_difference"
    if compare_policy == "duration_equal":
        return "canonical_duration_difference"
    if compare_policy == "boolean_equal":
        return "canonical_boolean_difference"
    return "canonical_difference"
```

- [ ] **Step 4: Run comparison tests**

Run:

```bash
python -m pytest tests/test_canonical_compare.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/canonical/compare.py tests/test_canonical_compare.py
git commit -m "feat: compare canonical values by field policy"
```

---

### Task 5: Add Derived Maturity Date And Pipeline Bridge

**Files:**
- Create: `src/canonical/pipeline.py`
- Modify: `src/canonical/compare.py`
- Test: `tests/test_canonical_pipeline.py`

- [ ] **Step 1: Write failing pipeline tests**

Create `tests/test_canonical_pipeline.py` with helper extraction builder copied from `tests/test_cross_check.py` style:

```python
from src.canonical.pipeline import cross_check_with_policy
from src.schemas.extraction import (
    Citation,
    ComparableField,
    DocumentValue,
    ExtractionResult,
    FeeScheduleExtraction,
    FundExtraction,
    PartyExtraction,
    RedemptionTermsExtraction,
)


def _dv(raw: str | None, document: str = "신탁계약서") -> DocumentValue:
    if raw is None:
        return DocumentValue(value=None, unit=None, raw_text=None, citation=None)
    return DocumentValue(
        value=None,
        unit=None,
        raw_text=raw,
        citation=Citation(document=document, page=1),
    )


def _field(contract: str | None, im: str | None) -> ComparableField:
    return ComparableField(contract=_dv(contract), im=_dv(im, "IM"))


def _empty_field() -> ComparableField:
    return _field(None, None)


def _extraction(**fields) -> ExtractionResult:
    return ExtractionResult(
        schema_version="v0",
        fund=FundExtraction(
            name=fields.get("fund_name", _empty_field()),
            type=fields.get("fund_type", _empty_field()),
            inception_date=fields.get("inception_date", _empty_field()),
            maturity_date=fields.get("maturity_date", _empty_field()),
        ),
        party=PartyExtraction(
            asset_manager=_empty_field(),
            trustee=_empty_field(),
            distributor=_empty_field(),
        ),
        fee_schedule=FeeScheduleExtraction(
            management_fee=fields.get("management_fee", _empty_field()),
            trust_fee=_empty_field(),
            sales_fee=fields.get("sales_fee", _empty_field()),
        ),
        redemption_terms=RedemptionTermsExtraction(
            is_redeemable=fields.get("is_redeemable", _empty_field()),
            lockup_period=fields.get("lockup_period", _empty_field()),
            redemption_cycle=_empty_field(),
            redemption_fee=fields.get("redemption_fee", _empty_field()),
        ),
    )


def test_policy_cross_check_adds_canonical_metadata_for_percent_match():
    extraction = _extraction(
        management_fee=_field("연 1,000분의 8.9", "[운용] 연[ 0.89 ] %")
    )
    result = next(r for r in cross_check_with_policy(extraction) if r.field == "fee_schedule.management_fee")
    assert result.final_status == "same_after_normalization"
    assert result.canonical_status == "decisive"
    assert result.canonical["contract"]["method"] == "permille"


def test_policy_cross_check_derives_maturity_from_same_side_inception():
    extraction = _extraction(
        inception_date=_field("2025년 7월 22일", "2025.07.22"),
        maturity_date=_field("설정일로부터 3년", "2028-07-22"),
    )
    result = next(r for r in cross_check_with_policy(extraction) if r.field == "fund.maturity_date")
    assert result.final_status == "same_after_normalization"
    assert result.canonical["contract"]["value"] == "2028-07-22"


def test_policy_cross_check_maturity_standalone_duration_is_not_decisive():
    extraction = _extraction(
        inception_date=_field("2025년 7월 22일", "2025.07.22"),
        maturity_date=_field("3년", "2028-07-22"),
    )
    result = next(r for r in cross_check_with_policy(extraction) if r.field == "fund.maturity_date")
    assert result.final_status == "needs_review"
    assert result.canonical_status == "non_decisive"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python -m pytest tests/test_canonical_pipeline.py -q
```

Expected: fail because pipeline does not exist or derived maturity is not implemented.

- [ ] **Step 3: Implement pipeline and derived date support**

Create `src/canonical/pipeline.py`:

```python
from __future__ import annotations

from datetime import date
from typing import Iterable

from src.canonical.compare import compare_values
from src.canonical.parsers import parse_date, parse_duration_months
from src.canonical.policy import load_field_policies
from src.canonical.types import CanonicalComparison, CanonicalValue, FieldPolicy
from src.pipelines.cross_check import (
    CrossCheckResult,
    CrossCheckStatus,
    CrossCheckValue,
    FIELD_LABELS,
    FinalCheckStatus,
    MissingSide,
)
from src.schemas.extraction import ComparableField, ExtractionResult


def cross_check_with_policy(extraction: ExtractionResult) -> list[CrossCheckResult]:
    policies = load_field_policies()
    raw_results = {
        field_path: _compare_field_with_policy(field_path, field, policies[field_path], extraction)
        for field_path, field in _iter_comparable_fields(extraction)
    }
    return list(raw_results.values())


def _compare_field_with_policy(
    field_path: str,
    field: ComparableField,
    policy: FieldPolicy,
    extraction: ExtractionResult,
) -> CrossCheckResult:
    missing_side = _missing_side(field)
    if missing_side != MissingSide.NONE:
        return _result_from_missing(field_path, field, missing_side)

    comparison = _compare_with_derivation(field_path, policy, field, extraction)
    status = CrossCheckStatus.NEEDS_REVIEW
    return CrossCheckResult(
        field=field_path,
        label=FIELD_LABELS[field_path],
        status=status,
        missing_side=MissingSide.NONE,
        final_status=FinalCheckStatus(comparison.final_status),
        final_reason_code=comparison.reason_code,
        final_reason=comparison.reason,
        canonical_status=comparison.status,
        canonical_reason_code=comparison.reason_code,
        canonical={
            "contract": comparison.contract.model_dump(mode="json"),
            "im": comparison.im.model_dump(mode="json"),
            "judge_allowed": comparison.judge_allowed,
        },
        contract=CrossCheckValue(raw_text=field.contract.raw_text, citation=field.contract.citation),
        im=CrossCheckValue(raw_text=field.im.raw_text, citation=field.im.citation),
    )


def _compare_with_derivation(
    field_path: str,
    policy: FieldPolicy,
    field: ComparableField,
    extraction: ExtractionResult,
) -> CanonicalComparison:
    if field_path != "fund.maturity_date":
        return compare_values(field_path, policy, field.contract.raw_text, field.im.raw_text)
    contract = _canonical_maturity(field.contract.raw_text, extraction.fund.inception_date.contract.raw_text)
    im = _canonical_maturity(field.im.raw_text, extraction.fund.inception_date.im.raw_text)
    return _comparison_from_values(policy, contract, im)


def _canonical_maturity(raw: str | None, inception_raw: str | None) -> CanonicalValue:
    direct = parse_date(raw)
    if direct.status == "decisive":
        return direct
    if raw is None:
        return direct
    compact = raw.replace(" ", "")
    if "설정일" not in compact and "최초설정일" not in compact:
        return CanonicalValue(
            status="non_decisive",
            reason_code="maturity_duration_without_reference",
            reason="Maturity duration does not explicitly reference inception date.",
        )
    inception = parse_date(inception_raw)
    duration = parse_duration_months(raw)
    if inception.status != "decisive" or duration.status != "decisive":
        return CanonicalValue(
            status="non_decisive",
            reason_code="maturity_derivation_failed",
            reason="Maturity derivation requires decisive inception date and duration.",
        )
    derived = _add_months(date.fromisoformat(inception.value), int(duration.value))
    return CanonicalValue(
        status="decisive",
        value=derived.isoformat(),
        unit="date",
        method="derived_from_inception",
        reason_code="maturity_derived_from_inception",
        reason="Maturity date derived from same-side inception date.",
        metadata={"inception_date": inception.value, "duration_months": duration.value},
    )


def _comparison_from_values(policy: FieldPolicy, contract: CanonicalValue, im: CanonicalValue) -> CanonicalComparison:
    if contract.status != "decisive" or im.status != "decisive":
        return CanonicalComparison(
            status="non_decisive",
            final_status=str(FinalCheckStatus.NEEDS_REVIEW),
            reason_code="canonical_not_decisive",
            reason="One or both sides could not be canonicalized decisively.",
            contract=contract,
            im=im,
            judge_allowed=policy.judge_allowed,
        )
    if contract.unit == im.unit and contract.value == im.value:
        return CanonicalComparison(
            status="decisive",
            final_status=str(FinalCheckStatus.SAME_AFTER_NORMALIZATION),
            reason_code="canonical_date_equal",
            reason="Canonical dates are equal under field policy.",
            contract=contract,
            im=im,
            judge_allowed=policy.judge_allowed,
        )
    return CanonicalComparison(
        status="decisive",
        final_status=str(FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION),
        reason_code="canonical_date_difference",
        reason="Canonical dates differ under field policy.",
        contract=contract,
        im=im,
        judge_allowed=policy.judge_allowed,
    )


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, _last_day_of_month(year, month))
    return date(year, month, day)


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def _result_from_missing(field_path: str, field: ComparableField, missing_side: MissingSide) -> CrossCheckResult:
    return CrossCheckResult(
        field=field_path,
        label=FIELD_LABELS[field_path],
        status=CrossCheckStatus.MISSING_EVIDENCE,
        missing_side=missing_side,
        final_status=FinalCheckStatus.MISSING_EVIDENCE,
        final_reason_code="missing_evidence",
        final_reason="One or both sides are missing raw evidence.",
        contract=CrossCheckValue(raw_text=field.contract.raw_text, citation=field.contract.citation),
        im=CrossCheckValue(raw_text=field.im.raw_text, citation=field.im.citation),
    )


def _missing_side(field: ComparableField) -> MissingSide:
    contract_missing = field.contract.raw_text is None
    im_missing = field.im.raw_text is None
    if contract_missing and im_missing:
        return MissingSide.BOTH
    if contract_missing:
        return MissingSide.CONTRACT
    if im_missing:
        return MissingSide.IM
    return MissingSide.NONE


def _iter_comparable_fields(extraction: ExtractionResult) -> Iterable[tuple[str, ComparableField]]:
    yield "fund.name", extraction.fund.name
    yield "fund.type", extraction.fund.type
    yield "fund.inception_date", extraction.fund.inception_date
    yield "fund.maturity_date", extraction.fund.maturity_date
    yield "party.asset_manager", extraction.party.asset_manager
    yield "party.trustee", extraction.party.trustee
    yield "party.distributor", extraction.party.distributor
    yield "fee_schedule.management_fee", extraction.fee_schedule.management_fee
    yield "fee_schedule.trust_fee", extraction.fee_schedule.trust_fee
    yield "fee_schedule.sales_fee", extraction.fee_schedule.sales_fee
    yield "redemption_terms.is_redeemable", extraction.redemption_terms.is_redeemable
    yield "redemption_terms.lockup_period", extraction.redemption_terms.lockup_period
    yield "redemption_terms.redemption_cycle", extraction.redemption_terms.redemption_cycle
    yield "redemption_terms.redemption_fee", extraction.redemption_terms.redemption_fee
```

- [ ] **Step 4: Run pipeline tests**

Run:

```bash
python -m pytest tests/test_canonical_pipeline.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/canonical/pipeline.py tests/test_canonical_pipeline.py
git commit -m "feat: add ontology policy cross check pipeline"
```

---

### Task 6: Integrate Deterministic ontology_policy Score Mode

**Files:**
- Modify: `src/scoring/evaluate.py`
- Modify: `src/cli/main.py`
- Test: `tests/test_scoring.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing scoring test**

Append to `tests/test_scoring.py`:

```python
def test_evaluate_ontology_policy_mode_uses_canonical_comparison():
    records = evaluate_golden(
        load_golden_master(),
        mode="ontology_policy",
        contract_pages=22,
        im_pages=32,
    )
    assert len(records) == 30
    assert any(r.final_reason_code and r.final_reason_code.startswith("canonical_") for r in records)
```

- [ ] **Step 2: Run failing scoring test**

Run:

```bash
python -m pytest tests/test_scoring.py::test_evaluate_ontology_policy_mode_uses_canonical_comparison -q
```

Expected: fail because mode is unsupported.

- [ ] **Step 3: Modify evaluator**

In `src/scoring/evaluate.py`, change:

```python
SUPPORTED_MODES = ("ontology", "guard", "ontology_policy")
```

Add import inside the `evaluate_golden` function after guard handling:

```python
        if mode == "ontology_policy":
            ctx = GuardContext(
                contract_pdf=Path("contract.pdf"),
                im_pdf=Path("im.pdf"),
                contract_pages=contract_pages,
                im_pages=im_pages,
                config=GuardConfig(g1_format=True, g2_citation=True, g3_constraint=True),
            )
            guarded, events = apply_guards(
                raw_extraction_json=extraction.model_dump_json(), ctx=ctx
            )
            if guarded is not None:
                extraction = guarded
            guard_rejections = _rejections_for_field(events, case.field)

            from src.canonical.pipeline import cross_check_with_policy

            result = next(r for r in cross_check_with_policy(extraction) if r.field == case.field)
            records.append(
                CaseRecord(
                    case_id=case.case_id,
                    field=case.field,
                    gold_label=case.gold_label,
                    difficulty=case.difficulty,
                    mutation_type=case.mutation_type,
                    harness_signal=case.harness_signal,
                    final_status=str(result.final_status),
                    final_reason_code=result.final_reason_code,
                    guard_rejections=guard_rejections,
                )
            )
            continue
```

Keep existing `ontology` and `guard` behavior unchanged.

- [ ] **Step 4: Add CLI test**

Append to `tests/test_cli.py`:

```python
def test_cli_score_ontology_policy(tmp_path):
    out = tmp_path / "score_ontology_policy.json"
    result = runner.invoke(
        app,
        ["score", "--mode", "ontology_policy", "--out", str(out)],
    )
    assert result.exit_code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["mode"] == "ontology_policy"
    assert report["n_cases"] == 30
```

- [ ] **Step 5: Run tests**

Run:

```bash
python -m pytest tests/test_scoring.py::test_evaluate_ontology_policy_mode_uses_canonical_comparison tests/test_cli.py::test_cli_score_ontology_policy -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/scoring/evaluate.py src/cli/main.py tests/test_scoring.py tests/test_cli.py
git commit -m "feat: add deterministic ontology policy scoring mode"
```

---

### Task 7: Add ontology_policy_judge Script

**Files:**
- Modify: `src/scoring/evaluate.py`
- Create: `scripts/score_ontology_policy.py`
- Test: `tests/test_scoring.py`

- [ ] **Step 1: Write failing pure fallback test**

Append to `tests/test_scoring.py`:

```python
from src.pipelines.llm_judge import JudgeStatus
from src.scoring.evaluate import resolve_policy_with_judge


def test_resolve_policy_with_judge_only_updates_needs_review():
    assert (
        resolve_policy_with_judge(FinalCheckStatus.EXACT_MATCH, JudgeStatus.DIFFERENT)
        == FinalCheckStatus.EXACT_MATCH
    )
    assert (
        resolve_policy_with_judge(FinalCheckStatus.NEEDS_REVIEW, JudgeStatus.SAME)
        == FinalCheckStatus.SAME_AFTER_NORMALIZATION
    )
    assert (
        resolve_policy_with_judge(FinalCheckStatus.NEEDS_REVIEW, JudgeStatus.DIFFERENT)
        == FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION
    )
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python -m pytest tests/test_scoring.py::test_resolve_policy_with_judge_only_updates_needs_review -q
```

Expected: fail because `resolve_policy_with_judge` does not exist.

- [ ] **Step 3: Implement judge evaluator**

Add to `src/scoring/evaluate.py`:

```python
def resolve_policy_with_judge(final_status: FinalCheckStatus, judge_status) -> FinalCheckStatus:
    from src.pipelines.llm_judge import JudgeStatus

    if final_status != FinalCheckStatus.NEEDS_REVIEW or judge_status is None:
        return final_status
    if judge_status == JudgeStatus.SAME:
        return FinalCheckStatus.SAME_AFTER_NORMALIZATION
    return FinalCheckStatus.DIFFERENT_AFTER_NORMALIZATION
```

Add `evaluate_golden_ontology_policy_judge`:

```python
def evaluate_golden_ontology_policy_judge(
    cases: list[GoldenCase],
    *,
    contract_pages: int,
    im_pages: int,
    client,
) -> list[CaseRecord]:
    from src.canonical.pipeline import cross_check_with_policy
    from src.pipelines.llm_judge import judge_needs_review

    records: list[CaseRecord] = []
    for case in cases:
        comparable = _field_from_case(case)
        extraction = _build_extraction(case.field, comparable)
        ctx = GuardContext(
            contract_pdf=Path("contract.pdf"),
            im_pdf=Path("im.pdf"),
            contract_pages=contract_pages,
            im_pages=im_pages,
            config=GuardConfig(g1_format=True, g2_citation=True, g3_constraint=True),
        )
        guarded, events = apply_guards(raw_extraction_json=extraction.model_dump_json(), ctx=ctx)
        if guarded is not None:
            extraction = guarded
        guard_rejections = _rejections_for_field(events, case.field)

        cc = cross_check_with_policy(extraction)
        result = next(r for r in cc if r.field == case.field)
        judge_allowed = bool((result.canonical or {}).get("judge_allowed"))
        judged = {}
        if result.final_status == FinalCheckStatus.NEEDS_REVIEW and judge_allowed:
            judged = {j.field: j.status for j in judge_needs_review([result], llm=client)}
        final = resolve_policy_with_judge(result.final_status, judged.get(result.field))

        records.append(
            CaseRecord(
                case_id=case.case_id,
                field=case.field,
                gold_label=case.gold_label,
                difficulty=case.difficulty,
                mutation_type=case.mutation_type,
                harness_signal=case.harness_signal,
                final_status=str(final),
                final_reason_code="ontology_policy_judge" if judged else result.final_reason_code,
                guard_rejections=guard_rejections,
            )
        )
    return records
```

- [ ] **Step 4: Create script**

Create `scripts/score_ontology_policy.py`:

```python
"""ontology_policy_judge scoring: canonical policy first, Claude judge fallback only."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from src.client.anthropic_client import AnthropicJSONClient  # noqa: E402
from src.scoring.evaluate import evaluate_golden_ontology_policy_judge  # noqa: E402
from src.scoring.golden import load_golden_master  # noqa: E402
from src.scoring.scorer import score_cases  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="ontology_policy_judge scoring")
    parser.add_argument("--contract-pages", type=int, default=22)
    parser.add_argument("--im-pages", type=int, default=32)
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "reports" / "scoring" / "score_ontology_policy_judge.json",
    )
    args = parser.parse_args()

    cases = load_golden_master()
    client = AnthropicJSONClient()
    started = time.time()
    records = evaluate_golden_ontology_policy_judge(
        cases,
        contract_pages=args.contract_pages,
        im_pages=args.im_pages,
        client=client,
    )
    wall = time.time() - started
    report = score_cases(
        records,
        mode="ontology_policy_judge",
        golden_version="v0.1",
        run_id="ontology_policy_judge_live",
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    m, c = report["metrics"], report["confusion"]
    print(f"[ontology_policy_judge DONE] {len(cases)} cases wall={wall:.0f}s")
    print(
        f"  P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} "
        f"acc={m['accuracy']:.3f} hallucination={m['hallucination_rate']:.3f}"
    )
    print(f"  TP={c['tp']} FP={c['fp']} FN={c['fn']} TN={c['tn']} missing_excluded={c['missing_excluded']}")
    print(f"  -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run pure test**

Run:

```bash
python -m pytest tests/test_scoring.py::test_resolve_policy_with_judge_only_updates_needs_review -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/scoring/evaluate.py scripts/score_ontology_policy.py tests/test_scoring.py
git commit -m "feat: add ontology policy judge scoring path"
```

---

### Task 8: Final Verification And Docs Update

**Files:**
- Modify: `docs/runbooks/reproduce-results.md`
- Modify: `docs/STATUS.md`
- Test: full suite and deterministic score command

- [ ] **Step 1: Run focused canonical tests**

Run:

```bash
python -m pytest tests/test_canonical_policy.py tests/test_canonical_parsers.py tests/test_canonical_compare.py tests/test_canonical_pipeline.py -q
```

Expected: all pass.

- [ ] **Step 2: Run full suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Run deterministic ontology_policy score**

Run:

```bash
python -m src.cli score --mode ontology_policy --out reports/scoring/score_ontology_policy.json
```

Expected: command exits 0 and writes score JSON with `"mode": "ontology_policy"`.

- [ ] **Step 4: Optionally run Claude fallback score**

Run only when `.env` has `ANTHROPIC_API_KEY`:

```bash
python scripts/score_ontology_policy.py
```

Expected: command exits 0 and writes `reports/scoring/score_ontology_policy_judge.json`.

- [ ] **Step 5: Update runbook**

In `docs/runbooks/reproduce-results.md`, add a subsection after current 3-condition comparison:

```markdown
## 7. Ontology Policy 비교

`ontology_policy`는 G1/G2/G3 이후 `ontology/field_policies.yaml` 기반 canonical comparison을 먼저 수행한다. 결정론으로 확정된 필드는 LLM을 호출하지 않는다.

```bash
python -m src.cli score --mode ontology_policy --out reports/scoring/score_ontology_policy.json
python scripts/score_ontology_policy.py
```

`ontology_policy_judge`는 canonical이 확정하지 못하고 field policy가 허용한 필드에만 Claude judge fallback을 적용한다. Claude normalization은 사용하지 않는다.
```
```

- [ ] **Step 6: Update status**

In `docs/STATUS.md`, add a brief next-work/current-work line:

```markdown
- ontology_policy 브랜치: field policy 기반 canonical comparison 설계/구현 중. 기존 3조건은 보존하고 `ontology_policy`/`ontology_policy_judge`를 추가 비교 조건으로 둔다.
```

- [ ] **Step 7: Commit docs and generated score only if desired**

Commit docs and source changes. Do not commit generated score JSON unless the user explicitly wants report artifacts included.

```bash
git add docs/runbooks/reproduce-results.md docs/STATUS.md
git commit -m "docs: document ontology policy scoring"
```
