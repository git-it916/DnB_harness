from pathlib import Path

from scripts.render_mermaid import render_mermaid


def test_render_mermaid_writes_schema_and_abox_diagrams(tmp_path):
    output_path = tmp_path / "ontology_mermaid.md"

    render_mermaid(
        ontology_path=Path("ontology/trust_fund.ttl"),
        abox_path=Path("reports/manual_extract/abox.ttl"),
        output_path=output_path,
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert "# Ontology Mermaid Diagrams" in markdown
    assert "```mermaid" in markdown
    assert "flowchart TD" in markdown
    assert "Fund -->|당사자 정보| Party" in markdown
    assert "FeeSchedule --> management_fee" in markdown
    assert "subgraph Contract" in markdown
    assert "fund_contract -->|has_party| party_contract" in markdown
    assert "subgraph IM" in markdown
    assert "fund_im -->|has_fee_schedule| fee_schedule_im" in markdown
