"""Quick inspection of PDFs in database/ — digital vs scanned."""

from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber


def main() -> int:
    db = Path(__file__).resolve().parent.parent / "database" / "raw_data"
    pdfs = sorted(db.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found in database/")
        return 1

    for pdf in pdfs:
        print(f"\n=== {pdf.name} ===")
        with pdfplumber.open(pdf) as doc:
            n = len(doc.pages)
            print(f"pages: {n}")
            for i in range(min(3, n)):
                t = doc.pages[i].extract_text() or ""
                preview = t[:150].replace("\n", " ")
                print(f"  page{i+1}: len={len(t)} | {preview!r}")
            # last page check
            if n > 3:
                t = doc.pages[-1].extract_text() or ""
                print(f"  page{n} (last): len={len(t)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
