import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


FEE_RANGES = {
    "management_fee": (0.0, 5.0),
    "trust_fee": (0.0, 2.0),
    "sales_fee": (0.0, 3.0),
}


def validate_abox(
    *,
    data_path: Path,
    shapes_path: Path,
    output_path: Path,
    allow_fallback: bool = False,
) -> dict[str, Any]:
    result = _validate_with_pyshacl(data_path, shapes_path)
    if result is None:
        if not allow_fallback:
            raise RuntimeError(
                "pyshacl is required for SHACL validation. "
                "Install it with `pip install pyshacl rdflib`, or pass --allow-fallback for W1 fallback checks."
            )
        result = _validate_w1_rules(data_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _validate_with_pyshacl(data_path: Path, shapes_path: Path) -> dict[str, Any] | None:
    try:
        from pyshacl import validate  # type: ignore
    except ImportError:
        return None

    conforms, _results_graph, results_text = validate(
        data_graph=str(data_path),
        shacl_graph=str(shapes_path),
        data_graph_format="turtle",
        shacl_graph_format="turtle",
    )
    return {
        "conforms": bool(conforms),
        "engine": "pyshacl",
        "violations": [] if conforms else [{"message": results_text}],
    }


def _validate_w1_rules(data_path: Path) -> dict[str, Any]:
    text = data_path.read_text(encoding="utf-8")
    subjects = _parse_turtle_subjects(text)
    violations: list[dict[str, Any]] = []

    for subject, predicates in subjects.items():
        if predicates.get("type") == "FeeSchedule":
            for field, (low, high) in FEE_RANGES.items():
                key = f"{field}_normalized_value"
                if key not in predicates:
                    continue
                value = _to_float(predicates[key])
                if value is None or not (low <= value <= high):
                    violations.append(
                        {
                            "subject": subject,
                            "field": key,
                            "message": f"{field} must be between {low} and {high} percent per year.",
                            "value": predicates[key],
                        }
                    )

    for side in ("contract", "im"):
        fund = subjects.get(f"data:fund_{side}", {})
        inception = _to_date(fund.get("inception_date_normalized_value"))
        maturity = _to_date(fund.get("maturity_date_normalized_value"))
        if inception and maturity and maturity <= inception:
            violations.append(
                {
                    "subject": f"data:fund_{side}",
                    "field": "maturity_date_normalized_value",
                    "message": "maturity_date must be after inception_date.",
                    "value": maturity.isoformat(),
                }
            )

    return {
        "conforms": not violations,
        "engine": "w1_fallback",
        "violations": violations,
    }


def _parse_turtle_subjects(text: str) -> dict[str, dict[str, str]]:
    subjects: dict[str, dict[str, str]] = {}
    blocks = re.findall(r"(data:[\w_]+)\s+(.*?)(?=\n\ndata:|\Z)", text, flags=re.DOTALL)
    for subject, body in blocks:
        predicates: dict[str, str] = {}
        type_match = re.search(r"a\s+dnb:([\w_]+)", body)
        if type_match:
            predicates["type"] = type_match.group(1)
        for key, value in re.findall(r"dnb:([\w_]+)\s+(\".*?\"(?:\^\^xsd:[\w_]+)?|[^;\.]+)", body):
            predicates[key] = _clean_literal(value)
        subjects[subject] = predicates
    return subjects


def _clean_literal(value: str) -> str:
    value = value.strip()
    match = re.match(r'"(.*)"(?:\^\^xsd:[\w_]+)?$', value)
    if match:
        return match.group(1)
    return value


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate W1 ABox with SHACL or fallback rules.")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--shapes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Use built-in W1 checks only when pyshacl is unavailable.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = validate_abox(
        data_path=args.data,
        shapes_path=args.shapes,
        output_path=args.output,
        allow_fallback=args.allow_fallback,
    )
    print(f"Wrote {args.output} (conforms={result['conforms']})")


if __name__ == "__main__":
    main()
