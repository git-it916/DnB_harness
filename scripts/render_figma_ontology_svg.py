import argparse
import html
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OUTPUT_PATH = Path("reports/manual_extract/figma_ontology_overview.svg")


@dataclass(frozen=True)
class Box:
    id: str
    title: str
    subtitle: str
    x: int
    y: int
    w: int
    h: int
    fill: str
    stroke: str


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str


def render_figma_svg(*, output_path: Path = DEFAULT_OUTPUT_PATH) -> None:
    boxes = _boxes()
    edges = _edges()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_svg_document(boxes, edges), encoding="utf-8")


def _boxes() -> list[Box]:
    return [
        Box("contract_pdf", "신탁계약서 PDF", "source document", 80, 170, 260, 86, "#F5F7FA", "#95A0B2"),
        Box("im_pdf", "IM PDF", "source document", 80, 300, 260, 86, "#F5F7FA", "#95A0B2"),
        Box("extraction", "LLM Extraction", "extraction.json", 430, 220, 290, 110, "#EAF2FF", "#3B6EA8"),
        Box("fund", "Fund", "name, type, dates", 840, 90, 260, 100, "#244A7F", "#173457"),
        Box("party", "Party", "asset_manager, trustee", 840, 230, 260, 100, "#3F6F5D", "#284B3F"),
        Box("fee", "FeeSchedule", "management/trust/sales fee", 840, 370, 260, 100, "#B7662A", "#7F431C"),
        Box("redemption", "RedemptionTerms", "redeemable, cycle, fee", 840, 510, 260, 100, "#6B5D86", "#4B405E"),
        Box("cross_check", "Cross Check", "raw status + final_status", 1230, 150, 330, 105, "#FFF6E8", "#C27A30"),
        Box("normalization", "AI Normalization", "normalized_value/unit", 1230, 315, 330, 105, "#F0F7F4", "#4E8A6D"),
        Box("judge", "LLM Judge", "same / different", 1230, 480, 330, 105, "#F4F0FA", "#7A67A8"),
        Box("abox", "RDF ABox", "abox.ttl raw_text graph", 1690, 220, 300, 105, "#EEF3F8", "#5E7694"),
        Box("shacl", "SHACL Validation", "shacl_validation.json", 1690, 405, 300, 105, "#EEF8F2", "#5B8A6C"),
    ]


def _edges() -> list[Edge]:
    return [
        Edge("contract_pdf", "extraction", "PDF input"),
        Edge("im_pdf", "extraction", "PDF input"),
        Edge("extraction", "fund", "concept group"),
        Edge("extraction", "party", "concept group"),
        Edge("extraction", "fee", "concept group"),
        Edge("extraction", "redemption", "concept group"),
        Edge("fund", "cross_check", "raw_text"),
        Edge("fee", "normalization", "date/fee fields"),
        Edge("fund", "normalization", "date fields"),
        Edge("party", "judge", "needs_review"),
        Edge("redemption", "judge", "needs_review"),
        Edge("extraction", "abox", "raw_text only"),
        Edge("abox", "shacl", "shape check"),
    ]


def _svg_document(boxes: list[Box], edges: list[Edge]) -> str:
    box_by_id = {box.id: box for box in boxes}
    edge_markup = "\n".join(_edge_svg(edge, box_by_id) for edge in edges)
    box_markup = "\n".join(_box_svg(box) for box in boxes)
    return f"""<svg data-figma-ready="true" xmlns="http://www.w3.org/2000/svg" width="2100" height="760" viewBox="0 0 2100 760">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#7A8494"/>
    </marker>
    <filter id="softShadow" x="-20%" y="-20%" width="140%" height="150%">
      <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#1E2433" flood-opacity="0.14"/>
    </filter>
  </defs>
  <rect width="2100" height="760" fill="#F7F8FB"/>
  <text x="80" y="70" font-family="Inter, Arial, sans-serif" font-size="34" font-weight="700" fill="#1E2433">DnB Harness Ontology</text>
  <text x="80" y="104" font-family="Inter, Arial, sans-serif" font-size="16" fill="#647085">W1 extraction, ontology mapping, normalization, and validation flow</text>
  {edge_markup}
  {box_markup}
  <g transform="translate(80 650)">
    <rect x="0" y="0" width="1940" height="54" rx="12" fill="#FFFFFF" stroke="#DFE3EB"/>
    <text x="22" y="33" font-family="Inter, Arial, sans-serif" font-size="15" fill="#374151">Trust boundary:</text>
    <text x="150" y="33" font-family="Inter, Arial, sans-serif" font-size="15" fill="#647085">extraction.value/unit are candidates. raw_text + citation drive evidence. normalization produces typed comparison values. RDF stores raw_text only.</text>
  </g>
</svg>
"""


def _box_svg(box: Box) -> str:
    title = html.escape(box.title)
    subtitle = html.escape(box.subtitle)
    text_fill = "#FFFFFF" if box.fill in {"#244A7F", "#3F6F5D", "#B7662A", "#6B5D86"} else "#1E2433"
    subtitle_fill = "#E8EEF7" if text_fill == "#FFFFFF" else "#647085"
    return f"""  <g id="{html.escape(box.id)}" filter="url(#softShadow)">
    <rect x="{box.x}" y="{box.y}" width="{box.w}" height="{box.h}" rx="14" fill="{box.fill}" stroke="{box.stroke}" stroke-width="2"/>
    <text x="{box.x + box.w / 2:.0f}" y="{box.y + 40}" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="700" fill="{text_fill}">{title}</text>
    <text x="{box.x + box.w / 2:.0f}" y="{box.y + 70}" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="14" fill="{subtitle_fill}">{subtitle}</text>
  </g>"""


def _edge_svg(edge: Edge, box_by_id: dict[str, Box]) -> str:
    source = box_by_id[edge.source]
    target = box_by_id[edge.target]
    x1, y1, x2, y2 = _edge_points(source, target)
    label_x = (x1 + x2) / 2
    label_y = (y1 + y2) / 2 - 8
    return f"""  <g>
    <line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#7A8494" stroke-width="2.2" marker-end="url(#arrow)"/>
    <rect x="{label_x - 58:.0f}" y="{label_y - 16:.0f}" width="116" height="24" rx="8" fill="#F7F8FB" opacity="0.96"/>
    <text x="{label_x:.0f}" y="{label_y:.0f}" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="12" fill="#536075">{html.escape(edge.label)}</text>
  </g>"""


def _edge_points(source: Box, target: Box) -> tuple[float, float, float, float]:
    source_cx = source.x + source.w / 2
    source_cy = source.y + source.h / 2
    target_cx = target.x + target.w / 2
    target_cy = target.y + target.h / 2
    dx = target_cx - source_cx
    dy = target_cy - source_cy
    if abs(dx) >= abs(dy):
        x1 = source.x + source.w if dx > 0 else source.x
        y1 = source_cy + dy * 0.12
        x2 = target.x if dx > 0 else target.x + target.w
        y2 = target_cy - dy * 0.12
    else:
        x1 = source_cx + dx * 0.12
        y1 = source.y + source.h if dy > 0 else source.y
        x2 = target_cx - dx * 0.12
        y2 = target.y if dy > 0 else target.y + target.h
    return x1, y1, x2, y2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Figma-ready ontology SVG.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    render_figma_svg(output_path=args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
