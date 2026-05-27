import argparse
import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DNB = Namespace("https://dnb-harness.local/ontology#")
DATA = Namespace("https://dnb-harness.local/data#")
DEFAULT_ONTOLOGY_PATH = Path("ontology/trust_fund.ttl")
DEFAULT_ABOX_PATH = Path("reports/manual_extract/abox.ttl")
DEFAULT_SCHEMA_OUTPUT_PATH = Path("reports/manual_extract/ontology_schema_graph.html")
DEFAULT_ABOX_OUTPUT_PATH = Path("reports/manual_extract/abox_graph.html")
DEFAULT_SCHEMA_GRAPH_OUTPUT_PATH = Path(
    "reports/manual_extract/ontology_schema_graph_view.html"
)
DEFAULT_ABOX_GRAPH_OUTPUT_PATH = Path("reports/manual_extract/abox_graph_view.html")


@dataclass(frozen=True)
class GraphNode:
    id: str
    label: str
    group: str


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    label: str


def render_graphs(
    *,
    ontology_path: Path = DEFAULT_ONTOLOGY_PATH,
    abox_path: Path = DEFAULT_ABOX_PATH,
    schema_output_path: Path = DEFAULT_SCHEMA_OUTPUT_PATH,
    abox_output_path: Path = DEFAULT_ABOX_OUTPUT_PATH,
    schema_graph_output_path: Path = DEFAULT_SCHEMA_GRAPH_OUTPUT_PATH,
    abox_graph_output_path: Path = DEFAULT_ABOX_GRAPH_OUTPUT_PATH,
) -> None:
    ontology_graph = Graph()
    ontology_graph.parse(ontology_path, format="turtle")
    schema_nodes, schema_edges = _schema_graph_data(ontology_graph)
    _write_schema_board_html(
        output_path=schema_output_path,
        title="Ontology Schema Graph",
        subtitle="Classes, object links, and data properties from ontology/trust_fund.ttl",
        nodes=schema_nodes,
        edges=schema_edges,
    )
    _write_graph_html(
        output_path=schema_graph_output_path,
        title="Ontology Schema Graph View",
        subtitle="Graph view for classes, object links, and data properties.",
        nodes=schema_nodes,
        edges=schema_edges,
        layout_mode="schema",
    )

    abox_graph = Graph()
    abox_graph.parse(abox_path, format="turtle")
    _write_abox_board_html(
        output_path=abox_output_path,
        title="ABox Data Graph",
        subtitle="Document-scoped data nodes and raw_text literals from reports/manual_extract/abox.ttl",
        graph=abox_graph,
    )
    abox_nodes, abox_edges = _abox_graph_data(abox_graph)
    _write_graph_html(
        output_path=abox_graph_output_path,
        title="ABox Data Graph View",
        subtitle="Graph view for document-scoped data nodes and raw_text literals.",
        nodes=abox_nodes,
        edges=abox_edges,
        layout_mode="force",
    )


def _schema_graph_data(graph: Graph) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    for cls in graph.subjects(RDF.type, RDFS.Class):
        cls_id = _local_name(cls)
        nodes[cls_id] = GraphNode(cls_id, _label_for(graph, cls), "class")

    for prop in graph.subjects(RDF.type, RDF.Property):
        prop_id = _local_name(prop)
        prop_label = _label_for(graph, prop)
        domain = graph.value(prop, RDFS.domain)
        range_ = graph.value(prop, RDFS.range)

        if isinstance(domain, URIRef) and _local_name(domain) in nodes:
            if isinstance(range_, URIRef) and _local_name(range_) in nodes:
                edges.append(
                    GraphEdge(_local_name(domain), _local_name(range_), prop_label)
                )
            else:
                nodes[prop_id] = GraphNode(prop_id, prop_label, "property")
                edges.append(GraphEdge(_local_name(domain), prop_id, "property"))

    return list(nodes.values()), edges


def _abox_graph_data(graph: Graph) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    literal_counts: dict[str, int] = {}

    for subject, predicate, object_ in graph:
        if predicate == RDF.type:
            subject_id = _local_name(subject)
            nodes.setdefault(
                subject_id,
                GraphNode(subject_id, subject_id, _class_group(_local_name(object_))),
            )
            continue

        source_id = _local_name(subject)
        nodes.setdefault(source_id, GraphNode(source_id, source_id, "data"))
        edge_label = _local_name(predicate)

        if isinstance(object_, Literal):
            literal_counts[source_id] = literal_counts.get(source_id, 0) + 1
            target_id = f"{source_id}_literal_{literal_counts[source_id]}"
            nodes[target_id] = GraphNode(
                target_id,
                _truncate(str(object_), 76),
                "literal",
            )
            edges.append(GraphEdge(source_id, target_id, edge_label))
        elif isinstance(object_, URIRef):
            target_id = _local_name(object_)
            nodes.setdefault(target_id, GraphNode(target_id, target_id, "data"))
            edges.append(GraphEdge(source_id, target_id, edge_label))

    return list(nodes.values()), edges


def _write_schema_board_html(
    *,
    output_path: Path,
    title: str,
    subtitle: str,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    class_labels = {
        node.id: node.label for node in nodes if node.group == "class"
    }
    properties_by_class: dict[str, list[GraphNode]] = {
        class_id: [] for class_id in class_labels
    }
    object_edges = []
    property_nodes = {node.id: node for node in nodes if node.group == "property"}
    for edge in edges:
        if edge.label == "property" and edge.target in property_nodes:
            properties_by_class.setdefault(edge.source, []).append(property_nodes[edge.target])
        elif edge.source in class_labels and edge.target in class_labels:
            object_edges.append(edge)

    panel_order = ["Fund", "Party", "FeeSchedule", "RedemptionTerms"]
    panels = []
    for class_id in panel_order:
        if class_id not in class_labels:
            continue
        props = "\n".join(
            f'<li><code>{html.escape(prop.id)}</code><span>{html.escape(prop.label)}</span></li>'
            for prop in properties_by_class.get(class_id, [])
        )
        linked_from_fund = next(
            (edge.label for edge in object_edges if edge.source == "Fund" and edge.target == class_id),
            None,
        )
        link_badge = (
            f'<div class="link-badge">Fund -> {html.escape(linked_from_fund)}</div>'
            if linked_from_fund
            else '<div class="link-badge root">root concept</div>'
        )
        panels.append(
            f"""
            <section class="concept-panel concept-{html.escape(class_id)}">
              {link_badge}
              <h2>{html.escape(class_labels[class_id])}</h2>
              <div class="concept-id">{html.escape(class_id)}</div>
              <ul>{props}</ul>
            </section>
            """
        )

    output_path.write_text(
        _board_html(
            title=title,
            subtitle=subtitle,
            body=f"""
            <main class="schema-board">
              <div class="schema-root">
                <div class="root-card">Fund</div>
                <div class="root-caption">central product concept</div>
              </div>
              <div class="schema-grid">{''.join(panels)}</div>
            </main>
            """,
        ),
        encoding="utf-8",
    )


def _write_abox_board_html(
    *,
    output_path: Path,
    title: str,
    subtitle: str,
    graph: Graph,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    contract_sections = _abox_sections(graph, "contract")
    im_sections = _abox_sections(graph, "im")
    output_path.write_text(
        _board_html(
            title=title,
            subtitle=subtitle,
            body=f"""
            <main class="abox-board">
              <section class="scope-column">
                <div class="scope-heading">Contract Scope</div>
                {contract_sections}
              </section>
              <section class="scope-column">
                <div class="scope-heading">IM Scope</div>
                {im_sections}
              </section>
            </main>
            """,
        ),
        encoding="utf-8",
    )


def _abox_sections(graph: Graph, scope: str) -> str:
    subjects = [
        DATA[f"fund_{scope}"],
        DATA[f"party_{scope}"],
        DATA[f"fee_schedule_{scope}"],
        DATA[f"redemption_terms_{scope}"],
    ]
    title_by_subject = {
        DATA[f"fund_{scope}"]: "Fund",
        DATA[f"party_{scope}"]: "Party",
        DATA[f"fee_schedule_{scope}"]: "FeeSchedule",
        DATA[f"redemption_terms_{scope}"]: "RedemptionTerms",
    }
    sections = []
    for subject in subjects:
        rows = []
        links = []
        for predicate, object_ in sorted(
            graph.predicate_objects(subject),
            key=lambda item: _local_name(item[0]),
        ):
            if predicate == RDF.type:
                continue
            if isinstance(object_, Literal):
                rows.append(
                    f"""
                    <div class="field-row">
                      <div class="field-name">{html.escape(_local_name(predicate))}</div>
                      <div class="field-value">{html.escape(str(object_))}</div>
                    </div>
                    """
                )
            elif isinstance(object_, URIRef):
                links.append(
                    f'<span class="link-chip">{html.escape(_local_name(predicate))} -> {html.escape(_local_name(object_))}</span>'
                )
        sections.append(
            f"""
            <section class="data-section">
              <div class="section-title">
                <span>{html.escape(title_by_subject[subject])}</span>
                <code>{html.escape(_local_name(subject))}</code>
              </div>
              <div class="link-row">{''.join(links)}</div>
              <div class="field-list">{''.join(rows) or '<div class="empty">No raw_text triples</div>'}</div>
            </section>
            """
        )
    return "\n".join(sections)


def _board_html(*, title: str, subtitle: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fb;
      --ink: #1f2633;
      --muted: #637085;
      --line: #d9dfeb;
      --fund: #244a7f;
      --party: #3f6f5d;
      --fee: #9b642f;
      --redemption: #6b5d86;
      --surface: #ffffff;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      padding: 22px 30px 14px;
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      position: sticky;
      top: 0;
      z-index: 5;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
    }}
    .subtitle {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 14px;
    }}
    .schema-board {{
      padding: 34px;
      max-width: 1440px;
      margin: 0 auto;
    }}
    .schema-root {{
      display: grid;
      justify-items: center;
      gap: 8px;
      margin-bottom: 28px;
    }}
    .root-card {{
      width: min(420px, 70vw);
      padding: 22px 28px;
      border-radius: 10px;
      background: var(--fund);
      color: #fff;
      text-align: center;
      font-weight: 800;
      font-size: 22px;
      box-shadow: 0 12px 26px rgba(28, 54, 92, 0.18);
    }}
    .root-caption {{
      color: var(--muted);
      font-size: 13px;
    }}
    .schema-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(220px, 1fr));
      gap: 18px;
      align-items: stretch;
    }}
    .concept-panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-top: 8px solid var(--fund);
      border-radius: 10px;
      padding: 18px;
      min-height: 360px;
      box-shadow: 0 8px 24px rgba(31, 38, 51, 0.08);
    }}
    .concept-Party {{ border-top-color: var(--party); }}
    .concept-FeeSchedule {{ border-top-color: var(--fee); }}
    .concept-RedemptionTerms {{ border-top-color: var(--redemption); }}
    .link-badge {{
      display: inline-flex;
      padding: 5px 9px;
      border-radius: 999px;
      background: #eef3fa;
      color: #42536d;
      font-size: 12px;
      margin-bottom: 12px;
    }}
    .link-badge.root {{
      background: #eaf0fa;
      color: var(--fund);
    }}
    .concept-panel h2 {{
      margin: 0;
      font-size: 21px;
    }}
    .concept-id {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }}
    .concept-panel ul {{
      list-style: none;
      padding: 0;
      margin: 18px 0 0;
      display: grid;
      gap: 10px;
    }}
    .concept-panel li {{
      display: grid;
      gap: 5px;
      padding: 12px;
      border: 1px solid #e0e5ee;
      border-radius: 8px;
      background: #fbfcfe;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      color: #43516a;
    }}
    .concept-panel li span {{
      font-weight: 700;
    }}
    .abox-board {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 22px;
      padding: 28px;
      max-width: 1600px;
      margin: 0 auto;
    }}
    .scope-column {{
      display: grid;
      gap: 16px;
      align-content: start;
    }}
    .scope-heading {{
      position: sticky;
      top: 83px;
      z-index: 4;
      padding: 14px 18px;
      border-radius: 10px;
      background: #202b43;
      color: #fff;
      font-size: 18px;
      font-weight: 800;
      box-shadow: 0 8px 18px rgba(32, 43, 67, 0.16);
    }}
    .data-section {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 8px 22px rgba(31, 38, 51, 0.07);
    }}
    .section-title {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      background: #edf2f8;
      border-bottom: 1px solid var(--line);
    }}
    .section-title span {{
      font-weight: 800;
    }}
    .link-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 10px 14px;
      border-bottom: 1px solid #edf0f6;
    }}
    .link-chip {{
      padding: 5px 8px;
      border-radius: 999px;
      background: #f2f5fa;
      color: #4a586e;
      font-size: 12px;
    }}
    .field-list {{
      display: grid;
      gap: 0;
    }}
    .field-row {{
      display: grid;
      grid-template-columns: 150px minmax(0, 1fr);
      gap: 14px;
      padding: 13px 15px;
      border-top: 1px solid #edf0f6;
    }}
    .field-row:first-child {{
      border-top: 0;
    }}
    .field-name {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      color: #3f5f8a;
      overflow-wrap: anywhere;
    }}
    .field-value {{
      font-size: 13px;
      line-height: 1.45;
      overflow-wrap: anywhere;
    }}
    .empty {{
      padding: 14px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 980px) {{
      .schema-grid,
      .abox-board {{
        grid-template-columns: 1fr;
      }}
      .field-row {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="subtitle">{html.escape(subtitle)}</div>
  </header>
  {body}
</body>
</html>
"""


def _write_graph_html(
    *,
    output_path: Path,
    title: str,
    subtitle: str,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    layout_mode: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "nodes": [node.__dict__ for node in nodes],
        "edges": [edge.__dict__ for edge in edges],
    }
    output_path.write_text(
        _html_document(
            title=title,
            subtitle=subtitle,
            payload=payload,
            layout_mode=layout_mode,
        ),
        encoding="utf-8",
    )


def _html_document(*, title: str, subtitle: str, payload: dict, layout_mode: str) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fb;
      --ink: #1e2433;
      --muted: #647085;
      --line: #a4adbd;
      --class: #244a7f;
      --property: #b7662a;
      --data: #3f6f5d;
      --literal: #6b5d86;
      --surface: #ffffff;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      padding: 22px 28px 12px;
      border-bottom: 1px solid #dfe3eb;
      background: var(--surface);
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
    }}
    .subtitle {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 14px;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 12px 28px;
      background: var(--surface);
      border-bottom: 1px solid #dfe3eb;
      color: var(--muted);
      font-size: 13px;
    }}
    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .swatch {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      display: inline-block;
    }}
    #canvas {{
      width: 100vw;
      height: calc(100vh - 116px);
      overflow: hidden;
      background: linear-gradient(#eef2f7 1px, transparent 1px),
        linear-gradient(90deg, #eef2f7 1px, transparent 1px);
      background-size: 32px 32px;
    }}
    svg {{
      width: 100%;
      height: 100%;
      cursor: grab;
    }}
    .edge {{
      stroke: var(--line);
      stroke-width: 1.45;
      marker-end: url(#arrow);
    }}
    .edge-label {{
      fill: #536075;
      font-size: 11px;
      paint-order: stroke;
      stroke: #f7f8fb;
      stroke-width: 4px;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
    .node rect {{
      stroke: #ffffff;
      stroke-width: 2;
      filter: drop-shadow(0 5px 12px rgba(32, 39, 55, 0.14));
    }}
    .node text {{
      font-size: 13px;
      font-weight: 650;
      fill: #ffffff;
      text-anchor: middle;
      dominant-baseline: middle;
      pointer-events: none;
    }}
    .node.literal text {{
      fill: var(--ink);
      font-size: 11px;
      font-weight: 500;
    }}
    .node.literal rect {{
      fill: #ffffff;
      stroke: #bfc6d4;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="subtitle">{html.escape(subtitle)}</div>
  </header>
  <div class="legend">
    <span><i class="swatch" style="background: var(--class)"></i>Class</span>
    <span><i class="swatch" style="background: var(--property)"></i>Property</span>
    <span><i class="swatch" style="background: var(--data)"></i>Data node</span>
    <span><i class="swatch" style="background: var(--literal)"></i>Raw text</span>
  </div>
  <div id="canvas">
    <svg id="graph" role="img" aria-label="{html.escape(title)}"></svg>
  </div>
  <script>
    const graphData = {payload_json};
    const layoutMode = "{layout_mode}";
    const colors = {{
      class: "#244a7f",
      property: "#b7662a",
      data: "#3f6f5d",
      literal: "#6b5d86",
      Fund: "#244a7f",
      Party: "#3f6f5d",
      FeeSchedule: "#b7662a",
      RedemptionTerms: "#6b5d86"
    }};
    const svg = document.getElementById("graph");
    const width = svg.clientWidth || window.innerWidth;
    const height = svg.clientHeight || Math.max(640, window.innerHeight - 116);
    const ns = "http://www.w3.org/2000/svg";
    svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);

    const defs = document.createElementNS(ns, "defs");
    defs.innerHTML = '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#a4adbd"/></marker>';
    svg.appendChild(defs);

    const layer = document.createElementNS(ns, "g");
    svg.appendChild(layer);

    const nodes = graphData.nodes.map((node, index) => ({{...node, index}}));
    const nodeById = new Map(nodes.map(node => [node.id, node]));
    const edges = graphData.edges.map(edge => ({{
      ...edge,
      sourceNode: nodeById.get(edge.source),
      targetNode: nodeById.get(edge.target)
    }})).filter(edge => edge.sourceNode && edge.targetNode);

    assignNodeSizes(nodes);
    if (layoutMode === "schema") {{
      layoutSchema(nodes, edges, width, height);
    }} else {{
      layoutForce(nodes, edges, width, height);
    }}
    render(layer, nodes, edges);
    enablePanZoom(svg, layer);

    function assignNodeSizes(nodes) {{
      for (const node of nodes) {{
        if (node.group === "literal") {{
          node.w = 260;
          node.h = 58;
        }} else if (node.group === "property") {{
          node.w = 156;
          node.h = 46;
        }} else if (node.group === "class") {{
          node.w = 178;
          node.h = 54;
        }} else {{
          node.w = 188;
          node.h = 50;
        }}
      }}
    }}

    function layoutSchema(nodes, edges, width, height) {{
      const topY = Math.max(90, height * 0.13);
      const classY = Math.max(235, height * 0.36);
      const propertyY = Math.max(405, height * 0.64);
      const fund = nodeById.get("Fund");
      if (fund) {{
        fund.x = width / 2;
        fund.y = topY;
      }}
      const classPositions = {{
        Party: [width * 0.24, classY],
        FeeSchedule: [width * 0.50, classY],
        RedemptionTerms: [width * 0.76, classY]
      }};
      for (const [id, point] of Object.entries(classPositions)) {{
        const node = nodeById.get(id);
        if (node) {{
          node.x = point[0];
          node.y = point[1];
        }}
      }}

      const childrenBySource = new Map();
      for (const edge of edges) {{
        if (edge.label !== "property") continue;
        if (!childrenBySource.has(edge.source)) childrenBySource.set(edge.source, []);
        childrenBySource.get(edge.source).push(edge.targetNode);
      }}
      const parentOrder = ["Fund", "Party", "FeeSchedule", "RedemptionTerms"];
      for (const parentId of parentOrder) {{
        const parent = nodeById.get(parentId);
        const children = childrenBySource.get(parentId) || [];
        if (!parent || children.length === 0) continue;
        const gap = parentId === "RedemptionTerms" ? 122 : 132;
        const startX = parent.x - ((children.length - 1) * gap) / 2;
        children.forEach((child, index) => {{
          child.x = startX + index * gap;
          child.y = propertyY + (parentId === "Fund" ? -80 : 0);
        }});
      }}

      nodes.forEach((node, index) => {{
        if (Number.isFinite(node.x) && Number.isFinite(node.y)) return;
        node.x = 120 + (index % 6) * 170;
        node.y = height - 90;
      }});
      resolveOverlaps(nodes, width, height, 18);
    }}

    function layoutForce(nodes, edges, width, height) {{
      const centerX = width / 2;
      const centerY = height / 2;
      const byGroup = new Map();
      for (const node of nodes) {{
        if (!byGroup.has(node.group)) byGroup.set(node.group, []);
        byGroup.get(node.group).push(node);
      }}
      const ring = Math.min(width, height) * 0.42;
      nodes.forEach((node, index) => {{
        const angle = (2 * Math.PI * index) / Math.max(nodes.length, 1);
        node.x = centerX + Math.cos(angle) * ring;
        node.y = centerY + Math.sin(angle) * ring;
      }});
      const fund = nodeById.get("Fund") || nodeById.get("fund_contract");
      if (fund) {{
        fund.x = centerX;
        fund.y = centerY;
      }}
      for (let step = 0; step < 360; step++) {{
        for (const a of nodes) {{
          for (const b of nodes) {{
            if (a === b) continue;
            const dx = a.x - b.x;
            const dy = a.y - b.y;
            const dist2 = Math.max(dx * dx + dy * dy, 160);
            const force = 1800 / dist2;
            a.x += dx * force;
            a.y += dy * force;
          }}
        }}
        for (const edge of edges) {{
          const source = edge.sourceNode;
          const target = edge.targetNode;
          const dx = target.x - source.x;
          const dy = target.y - source.y;
          const preferred = source.group === "literal" || target.group === "literal" ? 245 : 310;
          const dist = Math.max(Math.hypot(dx, dy), 1);
          const pull = (dist - preferred) * 0.006;
          source.x += (dx / dist) * pull;
          source.y += (dy / dist) * pull;
          target.x -= (dx / dist) * pull;
          target.y -= (dy / dist) * pull;
        }}
        for (const node of nodes) {{
          node.x += (centerX - node.x) * 0.004;
          node.y += (centerY - node.y) * 0.004;
          node.x = Math.max(node.w / 2 + 28, Math.min(width - node.w / 2 - 28, node.x));
          node.y = Math.max(node.h / 2 + 28, Math.min(height - node.h / 2 - 28, node.y));
        }}
        if (step % 30 === 0) resolveOverlaps(nodes, width, height, 10);
      }}
      resolveOverlaps(nodes, width, height, 28);
    }}

    function resolveOverlaps(nodes, width, height, rounds) {{
      for (let round = 0; round < rounds; round++) {{
        for (let i = 0; i < nodes.length; i++) {{
          for (let j = i + 1; j < nodes.length; j++) {{
            const a = nodes[i];
            const b = nodes[j];
            const minX = (a.w + b.w) / 2 + 24;
            const minY = (a.h + b.h) / 2 + 18;
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            if (Math.abs(dx) >= minX || Math.abs(dy) >= minY) continue;
            const pushX = (minX - Math.abs(dx)) * 0.42 * (dx >= 0 ? 1 : -1);
            const pushY = (minY - Math.abs(dy)) * 0.42 * (dy >= 0 ? 1 : -1);
            if (Math.abs(pushX) < Math.abs(pushY)) {{
              a.x -= pushX;
              b.x += pushX;
            }} else {{
              a.y -= pushY;
              b.y += pushY;
            }}
          }}
        }}
        for (const node of nodes) {{
          node.x = Math.max(node.w / 2 + 28, Math.min(width - node.w / 2 - 28, node.x));
          node.y = Math.max(node.h / 2 + 28, Math.min(height - node.h / 2 - 28, node.y));
        }}
      }}
    }}

    function render(layer, nodes, edges) {{
      for (const edge of edges) {{
        const points = shortenEdge(edge.sourceNode, edge.targetNode);
        const line = document.createElementNS(ns, "line");
        line.setAttribute("class", "edge");
        line.setAttribute("x1", points.x1);
        line.setAttribute("y1", points.y1);
        line.setAttribute("x2", points.x2);
        line.setAttribute("y2", points.y2);
        layer.appendChild(line);

        const text = document.createElementNS(ns, "text");
        text.setAttribute("class", "edge-label");
        text.setAttribute("x", (points.x1 + points.x2) / 2);
        text.setAttribute("y", (points.y1 + points.y2) / 2 - 10);
        text.textContent = edge.label;
        layer.appendChild(text);
      }}

      for (const node of nodes) {{
        const group = document.createElementNS(ns, "g");
        group.setAttribute("class", "node");
        if (node.group === "literal") group.classList.add("literal");
        group.setAttribute("transform", `translate(${{node.x}}, ${{node.y}})`);
        const rect = document.createElementNS(ns, "rect");
        rect.setAttribute("x", -node.w / 2);
        rect.setAttribute("y", -node.h / 2);
        rect.setAttribute("width", node.w);
        rect.setAttribute("height", node.h);
        rect.setAttribute("rx", node.group === "literal" ? 8 : 10);
        rect.setAttribute("fill", colors[node.group] || colors[node.label] || "#506176");
        group.appendChild(rect);

        const label = document.createElementNS(ns, "text");
        label.setAttribute("y", 1);
        label.textContent = node.label;
        group.appendChild(label);
        group.appendChild(document.createElementNS(ns, "title")).textContent = node.id;
        layer.appendChild(group);
      }}
    }}

    function shortenEdge(source, target) {{
      const start = boundaryPoint(source, target);
      const end = boundaryPoint(target, source);
      return {{x1: start.x, y1: start.y, x2: end.x, y2: end.y}};
    }}

    function boundaryPoint(from, to) {{
      const dx = to.x - from.x;
      const dy = to.y - from.y;
      const scale = 1 / Math.max(Math.abs(dx) / (from.w / 2 + 8), Math.abs(dy) / (from.h / 2 + 8), 1);
      return {{
        x: from.x + dx * scale,
        y: from.y + dy * scale
      }};
    }}

    function enablePanZoom(svg, layer) {{
      let scale = 1;
      let offsetX = 0;
      let offsetY = 0;
      let dragging = false;
      let lastX = 0;
      let lastY = 0;
      const apply = () => layer.setAttribute("transform", `translate(${{offsetX}} ${{offsetY}}) scale(${{scale}})`);
      svg.addEventListener("wheel", event => {{
        event.preventDefault();
        const delta = event.deltaY < 0 ? 1.08 : 0.92;
        scale = Math.max(0.35, Math.min(2.8, scale * delta));
        apply();
      }}, {{ passive: false }});
      svg.addEventListener("pointerdown", event => {{
        dragging = true;
        lastX = event.clientX;
        lastY = event.clientY;
        svg.setPointerCapture(event.pointerId);
      }});
      svg.addEventListener("pointermove", event => {{
        if (!dragging) return;
        offsetX += event.clientX - lastX;
        offsetY += event.clientY - lastY;
        lastX = event.clientX;
        lastY = event.clientY;
        apply();
      }});
      svg.addEventListener("pointerup", () => dragging = false);
    }}
  </script>
</body>
</html>
"""


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


def _class_group(class_name: str) -> str:
    return class_name if class_name in {"Fund", "Party", "FeeSchedule", "RedemptionTerms"} else "data"


def _truncate(value: str, max_length: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 1] + "…"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render ontology and ABox HTML graphs.")
    parser.add_argument("--ontology", type=Path, default=DEFAULT_ONTOLOGY_PATH)
    parser.add_argument("--abox", type=Path, default=DEFAULT_ABOX_PATH)
    parser.add_argument("--schema-output", type=Path, default=DEFAULT_SCHEMA_OUTPUT_PATH)
    parser.add_argument("--abox-output", type=Path, default=DEFAULT_ABOX_OUTPUT_PATH)
    parser.add_argument(
        "--schema-graph-output",
        type=Path,
        default=DEFAULT_SCHEMA_GRAPH_OUTPUT_PATH,
    )
    parser.add_argument(
        "--abox-graph-output",
        type=Path,
        default=DEFAULT_ABOX_GRAPH_OUTPUT_PATH,
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    render_graphs(
        ontology_path=args.ontology,
        abox_path=args.abox,
        schema_output_path=args.schema_output,
        abox_output_path=args.abox_output,
        schema_graph_output_path=args.schema_graph_output,
        abox_graph_output_path=args.abox_graph_output,
    )
    print(f"Wrote {args.schema_output}")
    print(f"Wrote {args.abox_output}")
    print(f"Wrote {args.schema_graph_output}")
    print(f"Wrote {args.abox_graph_output}")


if __name__ == "__main__":
    main()
