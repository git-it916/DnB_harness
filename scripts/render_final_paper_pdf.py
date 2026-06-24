from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
from pathlib import Path


DEFAULT_CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
DEFAULT_FIGURE = Path("docs/paper/figures/figure1-harness-flow.svg")


def _inline(text: str) -> str:
    text = html.escape(text.strip())
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text


def _parse_table(lines: list[str], start: int) -> tuple[str, int]:
    rows: list[list[str]] = []
    i = start
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
        if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            rows.append(cells)
        i += 1
    if not rows:
        return "", i

    head, body = rows[0], rows[1:]
    chunks = ["<table>", "<thead><tr>"]
    chunks.extend(f"<th>{_inline(cell)}</th>" for cell in head)
    chunks.append("</tr></thead>")
    if body:
        chunks.append("<tbody>")
        for row in body:
            chunks.append("<tr>")
            chunks.extend(f"<td>{_inline(cell)}</td>" for cell in row)
            chunks.append("</tr>")
        chunks.append("</tbody>")
    chunks.append("</table>")
    return "\n".join(chunks), i


def _render_harness_flow_figure() -> str:
    return """
<figure class="flow-figure">
  <figcaption>Figure 1. 하네스의 전체 처리 흐름</figcaption>
  <div class="flow-image-wrap">
    <img class="flow-image" src="figure1-harness-flow.svg" alt="PDF 문서 추출부터 선택적 LLM Judge까지 이어지는 하네스 처리 흐름" />
    <span class="edge-label edge-label-left">결정 가능</span>
    <span class="edge-label edge-label-right">미해결 + Judge 요청</span>
  </div>
  <p class="figure-note">실제 운용 경로는 PDF 문서에서 시작한다. 본 성능 비교에서는 세 Tier에 동일한 원문 근거와 출처 정보를 입력하여, 추출 이후 각 아키텍처가 정합성 여부를 어떻게 판정하는지를 비교하였다.</p>
</figure>
""".strip()


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    chunks: list[str] = []
    i = 0
    in_code = False
    code_lines: list[str] = []

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        if stripped.startswith("```"):
            if in_code:
                chunks.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_lines.append(raw)
            i += 1
            continue

        if not stripped:
            i += 1
            continue

        if stripped == "::figure-harness-flow":
            chunks.append(_render_harness_flow_figure())
            i += 1
            continue

        if stripped == "::page-break":
            chunks.append('<div class="page-break"></div>')
            i += 1
            continue

        if stripped.startswith("|"):
            table_html, i = _parse_table(lines, i)
            if table_html:
                chunks.append(table_html)
            continue

        if stripped.startswith("#"):
            level = min(3, len(stripped) - len(stripped.lstrip("#")))
            text = stripped.lstrip("#").strip()
            chunks.append(f"<h{level}>{_inline(text)}</h{level}>")
            i += 1
            continue

        if stripped.startswith(">"):
            chunks.append(f"<blockquote>{_inline(stripped.lstrip('> '))}</blockquote>")
            i += 1
            continue

        if stripped.startswith("- "):
            items: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(f"<li>{_inline(lines[i].strip()[2:])}</li>")
                i += 1
            chunks.append("<ul>" + "\n".join(items) + "</ul>")
            continue

        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines):
                match = re.match(r"^\d+\.\s+(.*)$", lines[i].strip())
                if not match:
                    break
                items.append(f"<li>{_inline(match.group(1))}</li>")
                i += 1
            chunks.append("<ol>" + "\n".join(items) + "</ol>")
            continue

        paragraph = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or nxt.startswith(("#", "|", ">", "```", "- ")) or re.match(r"^\d+\.\s+", nxt):
                break
            paragraph.append(nxt)
            i += 1
        chunks.append(f"<p>{_inline(' '.join(paragraph))}</p>")

    return "\n".join(chunks)


def wrap_document(body: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>신탁계약서-투자제안서 정합성 검증 논문 수정본</title>
<style>
@page {{
  size: Letter;
  margin: 18mm 18mm 16mm 18mm;
}}
html {{
  font-family: "Apple SD Gothic Neo", "AppleGothic", "Noto Sans CJK KR", "Malgun Gothic", Arial, sans-serif;
  color: #141414;
  font-size: 10.5pt;
  line-height: 1.62;
}}
body {{
  margin: 0;
}}
h1 {{
  color: #0b1e3a;
  font-size: 18.5pt;
  line-height: 1.22;
  margin: 0 0 12pt 0;
  page-break-after: avoid;
}}
h2 {{
  color: #0b1e3a;
  font-size: 15pt;
  line-height: 1.28;
  margin: 18pt 0 7pt 0;
  page-break-after: avoid;
}}
h3 {{
  color: #222;
  font-size: 11.5pt;
  margin: 12pt 0 5pt 0;
  page-break-after: avoid;
}}
p {{
  margin: 0 0 8pt 0;
  text-align: justify;
}}
ul, ol {{
  margin: 0 0 8pt 18pt;
  padding: 0;
}}
li {{
  margin: 0 0 3pt 0;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  margin: 5pt 0 8pt 0;
  page-break-inside: avoid;
  font-size: 7.7pt;
  line-height: 1.25;
}}
th, td {{
  border: 0.6pt solid #bcc3cc;
  padding: 2.5pt 3.5pt;
  vertical-align: top;
}}
th {{
  background: #eaf0f7;
  font-weight: 700;
}}
tr:nth-child(even) td {{
  background: #fafafa;
}}
pre {{
  background: #f5f5f1;
  border: 0.6pt solid #d8d8d0;
  padding: 8pt;
  margin: 8pt 0 10pt 0;
  white-space: pre-wrap;
  page-break-inside: avoid;
}}
code {{
  font-family: Menlo, Consolas, monospace;
  font-size: 0.92em;
}}
blockquote {{
  margin: 8pt 0 10pt 0;
  padding: 7pt 10pt;
  border-left: 3pt solid #9fb0c2;
  background: #f6f8fa;
}}
figure {{
  margin: 10pt 0 12pt 0;
}}
.page-break {{
  break-before: page;
  page-break-before: always;
}}
figcaption {{
  font-weight: 700;
  color: #0b1e3a;
  margin: 0 0 6pt 0;
}}
.flow-figure {{
  border: 0.7pt solid #c9d0d8;
  background: #fbfcfd;
  padding: 7pt 9pt;
  page-break-inside: avoid;
}}
.flow-image-wrap {{
  position: relative;
  width: 28%;
  min-width: 112pt;
  margin: 2pt auto 0 auto;
}}
.flow-image {{
  display: block;
  width: 100%;
  height: auto;
}}
.edge-label {{
  position: absolute;
  background: #fbfcfd;
  color: #222;
  font-size: 5.4pt;
  font-weight: 700;
  line-height: 1.2;
  padding: 0.8pt 1.2pt;
  white-space: nowrap;
}}
.edge-label-left {{
  left: 18.5%;
  top: 66%;
}}
.edge-label-right {{
  right: 3%;
  top: 66%;
}}
.figure-note {{
  color: #333;
  font-size: 8.5pt;
  line-height: 1.42;
  margin: 5pt 0 0 0;
  text-align: left;
}}
strong {{
  font-weight: 700;
}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def render_pdf(source: Path, output: Path, html_output: Path, chrome: Path) -> None:
    markdown = source.read_text(encoding="utf-8")
    html_output.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    if DEFAULT_FIGURE.exists():
        shutil.copyfile(DEFAULT_FIGURE, html_output.parent / DEFAULT_FIGURE.name)
    html_output.write_text(wrap_document(markdown_to_html(markdown)), encoding="utf-8")

    if not chrome.exists():
        raise FileNotFoundError(f"Chrome executable not found: {chrome}")

    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--print-to-pdf={output.resolve()}",
            "--no-pdf-header-footer",
            str(html_output.resolve().as_uri()),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("docs/paper/final-paper-source.md"))
    parser.add_argument("--output", type=Path, default=Path("output/pdf/하네스_정합성검증_논문_수정본.pdf"))
    parser.add_argument("--html-output", type=Path, default=Path("output/pdf/하네스_정합성검증_논문_수정본.html"))
    parser.add_argument("--chrome", type=Path, default=DEFAULT_CHROME)
    args = parser.parse_args()
    render_pdf(args.source, args.output, args.html_output, args.chrome)
    print(args.output)


if __name__ == "__main__":
    main()
