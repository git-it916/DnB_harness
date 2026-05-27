from dataclasses import dataclass
from pathlib import Path

from pyshacl import validate
from rdflib import Graph


DEFAULT_ONTOLOGY_PATH = Path("ontology/trust_fund.ttl")
DEFAULT_SHAPES_PATH = Path("ontology/shapes.ttl")


@dataclass(frozen=True)
class ValidationResult:
    conforms: bool
    report_graph: Graph
    report_text: str


def validate_graph(
    data_graph: Graph,
    ontology_path: Path = DEFAULT_ONTOLOGY_PATH,
    shapes_path: Path = DEFAULT_SHAPES_PATH,
) -> ValidationResult:
    ontology_graph = Graph()
    ontology_graph.parse(ontology_path, format="turtle")

    shapes_graph = Graph()
    shapes_graph.parse(shapes_path, format="turtle")

    conforms, report_graph, report_text = validate(
        data_graph=data_graph,
        shacl_graph=shapes_graph,
        ont_graph=ontology_graph,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
    )

    return ValidationResult(
        conforms=bool(conforms),
        report_graph=report_graph,
        report_text=str(report_text),
    )
