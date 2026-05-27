from pathlib import Path

from scripts.render_figma_ontology_svg import render_figma_svg


def test_render_figma_svg_writes_importable_svg(tmp_path):
    output_path = tmp_path / "figma_ontology.svg"

    render_figma_svg(output_path=output_path)

    svg = output_path.read_text(encoding="utf-8")
    assert svg.startswith("<svg")
    assert "DnB Harness Ontology" in svg
    assert "Fund" in svg
    assert "FeeSchedule" in svg
    assert "Cross Check" in svg
    assert "<marker" in svg
    assert "data-figma-ready" in svg
