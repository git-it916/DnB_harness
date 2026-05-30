import argparse
import json
from pathlib import Path
from typing import Any


SIDES = ("contract", "im")
CATEGORY_CLASSES = {
    "fund": "Fund",
    "party": "Party",
    "fee_schedule": "FeeSchedule",
    "redemption_terms": "RedemptionTerms",
}


def build_abox(
    *,
    extraction_path: Path,
    normalization_path: Path | None,
    output_path: Path,
) -> None:
    extraction = _read_json(extraction_path)
    normalizations = _read_normalizations(normalization_path)

    lines = [
        "@prefix data: <https://dnb-harness.local/data#> .",
        "@prefix dnb: <https://dnb-harness.local/ontology#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
    ]

    for category, class_name in CATEGORY_CLASSES.items():
        category_data = extraction.get(category, {})
        for side in SIDES:
            subject = f"data:{category}_{side}"
            predicates = [f"a dnb:{class_name}"]

            for field_name, field_payload in category_data.items():
                side_payload = field_payload.get(side)
                if not isinstance(side_payload, dict):
                    continue
                field_path = f"{category}.{field_name}"
                predicates.extend(_field_predicates(field_name, side_payload))
                normalized = normalizations.get((field_path, side), {})
                predicates.extend(_normalization_predicates(field_name, normalized))

            if len(predicates) == 1:
                lines.append(f"{subject} {predicates[0]} .")
            else:
                lines.append(f"{subject} {predicates[0]} ;")
                for predicate in predicates[1:-1]:
                    lines.append(f"  {predicate} ;")
                lines.append(f"  {predicates[-1]} .")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _field_predicates(field_name: str, payload: dict[str, Any]) -> list[str]:
    predicates = []
    for suffix in ("value", "unit", "raw_text"):
        value = payload.get(suffix)
        if value is not None:
            predicates.append(f"dnb:{field_name}_{suffix} {_literal(value)}")

    citation = payload.get("citation")
    if isinstance(citation, dict):
        document = citation.get("document")
        page = citation.get("page")
        if document is not None:
            predicates.append(f"dnb:{field_name}_document {_literal(document)}")
        if page is not None:
            predicates.append(f"dnb:{field_name}_page {_literal(page, datatype='xsd:integer')}")
    return predicates


def _normalization_predicates(field_name: str, normalized: dict[str, Any]) -> list[str]:
    predicates = []
    value = normalized.get("normalized_value")
    unit = normalized.get("normalized_unit")
    if value is not None:
        datatype = "xsd:decimal" if isinstance(value, (int, float)) else None
        predicates.append(f"dnb:{field_name}_normalized_value {_literal(value, datatype=datatype)}")
    if unit is not None:
        predicates.append(f"dnb:{field_name}_normalized_unit {_literal(unit)}")
    return predicates


def _read_normalizations(path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None or not path.exists():
        return {}

    payload = _read_json(path)
    result: dict[tuple[str, str], dict[str, Any]] = {}
    if not isinstance(payload, list):
        return result

    for item in payload:
        if not isinstance(item, dict) or not item.get("field"):
            continue
        field = item["field"]
        for side in SIDES:
            side_payload = item.get(side)
            if isinstance(side_payload, dict):
                result[(field, side)] = side_payload
    return result


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _literal(value: Any, *, datatype: str | None = None) -> str:
    if datatype:
        return f'"{_escape(str(value))}"^^{datatype}'
    return f'"{_escape(str(value))}"'


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build W1 RDF ABox from guarded extraction JSON.")
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--normalization", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_abox(
        extraction_path=args.extraction,
        normalization_path=args.normalization,
        output_path=args.output,
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
