from pathlib import Path

from scripts.render_ontology_graph import render_graphs


def test_render_graphs_writes_schema_and_abox_html(tmp_path):
    schema_path = tmp_path / "schema.html"
    abox_path = tmp_path / "abox.html"
    schema_graph_path = tmp_path / "schema_graph.html"
    abox_graph_path = tmp_path / "abox_graph.html"

    render_graphs(
        ontology_path=Path("ontology/trust_fund.ttl"),
        abox_path=Path("reports/manual_extract/abox.ttl"),
        schema_output_path=schema_path,
        abox_output_path=abox_path,
        schema_graph_output_path=schema_graph_path,
        abox_graph_output_path=abox_graph_path,
    )

    schema_html = schema_path.read_text(encoding="utf-8")
    abox_html = abox_path.read_text(encoding="utf-8")
    schema_graph_html = schema_graph_path.read_text(encoding="utf-8")
    abox_graph_html = abox_graph_path.read_text(encoding="utf-8")
    assert "Ontology Schema Graph" in schema_html
    assert "Fund" in schema_html
    assert "FeeSchedule" in schema_html
    assert "management_fee" in schema_html
    assert "ABox Data Graph" in abox_html
    assert "fund_contract" in abox_html
    assert "schema-board" in schema_html
    assert "concept-panel" in schema_html
    assert "Contract Scope" in abox_html
    assert "IM Scope" in abox_html
    assert "data-section" in abox_html
    assert "Ontology Schema Graph View" in schema_graph_html
    assert "layoutMode = \"schema\"" in schema_graph_html
    assert "shortenEdge" in schema_graph_html
    assert "ABox Data Graph View" in abox_graph_html
    assert "layoutMode = \"force\"" in abox_graph_html
