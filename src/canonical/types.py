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
