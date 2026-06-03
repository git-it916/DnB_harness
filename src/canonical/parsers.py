from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

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
        return _parsed(
            match.group(1),
            "percent_per_year",
            "percent",
            "percent_unit",
            "Explicit percent unit.",
        )

    match = _PERMILLE_RE.search(text)
    if match:
        value = Decimal(match.group(1)) / Decimal("10")
        return _parsed(
            _decimal_text(value),
            "percent_per_year",
            "permille",
            "permille_unit",
            "Explicit permille expression.",
        )

    match = _BP_RE.search(text)
    if match:
        value = Decimal(match.group(1)) / Decimal("100")
        return _parsed(
            _decimal_text(value),
            "percent_per_year",
            "basis_point",
            "basis_point_unit",
            "Explicit basis point unit.",
        )

    if re.fullmatch(r"\s*[0-9]+(?:\.[0-9]+)?\s*", text):
        return _non_decisive(
            "percent_unit_missing",
            "Unitless numeric percent evidence is ambiguous.",
        )
    return _non_decisive(
        "percent_unparseable",
        "No explicit percent, permille, or basis point unit was found.",
    )


def parse_date(raw: str | None) -> CanonicalValue:
    if raw is None or not raw.strip():
        return _non_decisive("missing_raw_text", "Raw text is missing.")
    text = raw.strip()
    for pattern in (
        r"(\d{4})-(\d{1,2})-(\d{1,2})",
        r"(\d{4})\.(\d{1,2})\.(\d{1,2})",
        r"(\d{4})/(\d{1,2})/(\d{1,2})",
    ):
        match = re.search(pattern, text)
        if match:
            return _date_from_parts(match.groups(), "absolute_date")
    match = _KR_DATE_RE.search(text)
    if match:
        return _date_from_parts(match.groups(), "korean_date")
    return _non_decisive(
        "date_unparseable",
        "No supported absolute date expression was found.",
    )


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
        return _non_decisive(
            "duration_unparseable",
            "No supported duration expression was found.",
        )
    return _parsed(
        str(total),
        "months",
        "duration",
        "duration_parsed",
        "Duration parsed as months.",
    )


def parse_boolean(raw: str | None) -> CanonicalValue:
    if raw is None or not raw.strip():
        return _non_decisive("missing_raw_text", "Raw text is missing.")
    text = re.sub(r"\s+", "", raw)
    if any(token in text for token in ("불가", "불가능", "없음", "아니", "제한")):
        return _parsed(
            "false",
            "boolean",
            "boolean",
            "boolean_false",
            "Negative boolean expression.",
        )
    if any(token in text for token in ("가능", "허용", "할수있")):
        return _parsed(
            "true",
            "boolean",
            "boolean",
            "boolean_true",
            "Positive boolean expression.",
        )
    return _non_decisive(
        "boolean_unparseable",
        "No supported boolean expression was found.",
    )
