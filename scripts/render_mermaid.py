import argparse
import sys
from pathlib import Path

from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DNB = Namespace("https://dnb-harness.local/ontology#")
DATA = Namespace("https://dnb-harness.local/data#")
DEFAULT_ONTOLOGY_PATH = Path("ontology/trust_fund.ttl")
DEFAULT_ABOX_PATH = Path("reports/manual_extract/abox.ttl")
DEFAULT_OUTPUT_PATH = Path("reports/manual_extract/ontology_mermaid.md")


def render_mermaid(
    *,
    ontology_path: Path = DEFAULT_ONTOLOGY_PATH,
    abox_path: Path = DEFAULT_ABOX_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> None:
    ontology_graph = Graph()
    ontology_graph.parse(ontology_path, format="turtle")

    abox_graph = Graph()
    abox_graph.parse(abox_path, format="turtle")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            [
                "# Ontology Mermaid Diagrams",
                "",
                "## Schema",
                "",
                "```mermaid",
                _schema_mermaid(ontology_graph),
                "```",
                "",
                "## ABox",
                "",
                "```mermaid",
                _abox_mermaid(abox_graph),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _schema_mermaid(graph: Graph) -> str:
    lines = [
        "flowchart TD",
        "  Fund[Fund<br/>펀드]",
        "  Party[Party<br/>당사자]",
        "  FeeSchedule[FeeSchedule<br/>보수]",
        "  RedemptionTerms[RedemptionTerms<br/>환매 조건]",
    ]
    property_lines: list[str] = []
    relation_lines: list[str] = []

    for prop in sorted(graph.subjects(RDF.type, RDF.Property), key=_local_name):
        domain = graph.value(prop, RDFS.domain)
        range_ = graph.value(prop, RDFS.range)
        if not isinstance(domain, URIRef):
            continue
        domain_id = _local_name(domain)
        prop_id = _local_name(prop)
        prop_label = _label_for(graph, prop)
        if isinstance(range_, URIRef) and _local_name(range_) in {
            "Party",
            "FeeSchedule",
            "RedemptionTerms",
        }:
            relation_lines.append(
                f"  {domain_id} -->|{_escape_mermaid_label(prop_label)}| {_local_name(range_)}"
            )
        else:
            property_lines.append(
                f"  {domain_id} --> {prop_id}[{prop_id}<br/>{_escape_mermaid_label(prop_label)}]"
            )

    lines.extend(relation_lines)
    lines.extend(property_lines)
    lines.extend(
        [
            "  classDef classNode fill:#244a7f,color:#fff,stroke:#18365e,stroke-width:1px",
            "  classDef propertyNode fill:#f2f5fa,color:#1f2633,stroke:#c7d0de,stroke-width:1px",
            "  class Fund,Party,FeeSchedule,RedemptionTerms classNode",
        ]
    )
    property_ids = [
        _local_name(prop)
        for prop in graph.subjects(RDF.type, RDF.Property)
        if _local_name(prop).startswith("has_") is False
    ]
    if property_ids:
        lines.append(f"  class {','.join(sorted(property_ids))} propertyNode")
    return "\n".join(lines)


def _abox_mermaid(graph: Graph) -> str:
    lines = [
        "flowchart LR",
        "  subgraph Contract[Contract]",
        "    fund_contract[Fund]",
        "    party_contract[Party]",
        "    fee_schedule_contract[FeeSchedule]",
        "    redemption_terms_contract[RedemptionTerms]",
        "  end",
        "  subgraph IM[IM]",
        "    fund_im[Fund]",
        "    party_im[Party]",
        "    fee_schedule_im[FeeSchedule]",
        "    redemption_terms_im[RedemptionTerms]",
        "  end",
    ]

    for scope in ["contract", "im"]:
        fund = f"fund_{scope}"
        lines.extend(
            [
                f"  {fund} -->|has_party| party_{scope}",
                f"  {fund} -->|has_fee_schedule| fee_schedule_{scope}",
                f"  {fund} -->|has_redemption_terms| redemption_terms_{scope}",
            ]
        )

    for scope in ["contract", "im"]:
        for subject in [
            DATA[f"fund_{scope}"],
            DATA[f"party_{scope}"],
            DATA[f"fee_schedule_{scope}"],
            DATA[f"redemption_terms_{scope}"],
        ]:
            subject_id = _local_name(subject)
            field_names = [
                _local_name(predicate)
                for predicate, object_ in graph.predicate_objects(subject)
                if predicate != RDF.type and isinstance(object_, Literal)
            ]
            if not field_names:
                continue
            fields_id = f"{subject_id}_fields"
            fields_label = "<br/>".join(sorted(field_names))
            lines.append(f"  {subject_id} -. raw_text .-> {fields_id}[{fields_label}]")

    lines.extend(
        [
            "  classDef contract fill:#eaf2ee,color:#1f3f34,stroke:#8bb3a2,stroke-width:1px",
            "  classDef im fill:#eef2fb,color:#253c69,stroke:#9aaeda,stroke-width:1px",
            "  classDef fields fill:#fffaf2,color:#3f3326,stroke:#dbc39c,stroke-width:1px",
            "  class fund_contract,party_contract,fee_schedule_contract,redemption_terms_contract contract",
            "  class fund_im,party_im,fee_schedule_im,redemption_terms_im im",
        ]
    )
    field_nodes = [
        f"{_local_name(subject)}_fields"
        for subject in graph.subjects()
        if str(subject).startswith(str(DATA))
    ]
    if field_nodes:
        lines.append(f"  class {','.join(sorted(set(field_nodes)))} fields")
    return "\n".join(lines)


def _label_for(graph: Graph, subject: URIRef) -> str:
    label = graph.value(subject, RDFS.label)
    if isinstance(label, Literal):
        return str(label)
    return _local_name(subject)


def _local_name(value) -> str:
    text = str(value)
    if "#" in text:
        return text.rsplit("#", 1)[1]
    if "/" in text:
        return text.rstrip("/").rsplit("/", 1)[1]
    return text


def _escape_mermaid_label(value: str) -> str:
    return value.replace("|", "/").replace("[", "(").replace("]", ")")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render ontology Mermaid diagrams.")
    parser.add_argument("--ontology", type=Path, default=DEFAULT_ONTOLOGY_PATH)
    parser.add_argument("--abox", type=Path, default=DEFAULT_ABOX_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    render_mermaid(
        ontology_path=args.ontology,
        abox_path=args.abox,
        output_path=args.output,
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
