"""PDF -> page-level content (text for digital, base64 PNG for scanned).

자동 분기:
- 첫 N 페이지의 임베디드 텍스트가 threshold 이상이면 digital → pdfplumber
- 미만이면 scanned → pdf2image → base64 PNG (Gemma 4 vision 입력)
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pdfplumber
from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)

SCANNED_TEXT_THRESHOLD_CHARS = 50  # 페이지당 임베디드 텍스트 < 50자면 스캔으로 간주
SCAN_PROBE_PAGES = 3                # 첫 3페이지로 스캔/디지털 판정
IMAGE_DPI = 200                     # vision 입력용 PNG 해상도 (V2 실험으로 150→200 채택, §13.5)
IMAGE_MAX_DIMENSION = 1600          # 너무 큰 이미지는 다운스케일 (Ollama base64 부담)


def _find_poppler_path() -> str | None:
    """Conda env 의 Library/bin (Windows) 또는 시스템 PATH 에서 poppler 탐색."""
    # 1) Conda env Library/bin (Windows 표준 위치)
    env_prefix = Path(sys.executable).resolve().parent
    candidate = env_prefix / "Library" / "bin"
    if (candidate / "pdfinfo.exe").exists() or (candidate / "pdfinfo").exists():
        return str(candidate)
    # 2) 환경변수 POPPLER_PATH
    pp = os.environ.get("POPPLER_PATH")
    if pp and Path(pp).exists():
        return pp
    return None


_POPPLER_PATH = _find_poppler_path()
if _POPPLER_PATH:
    logger.info(f"poppler 경로 발견: {_POPPLER_PATH}")


@dataclass(frozen=True)
class PageContent:
    """한 페이지의 내용. text 또는 image_b64 둘 중 하나가 채워짐."""
    page: int                                # 1-based PDF 뷰어 페이지
    source: Literal["embedded", "vision"]    # 어떻게 추출했나
    text: str | None = None                  # source == "embedded"
    image_b64: str | None = None             # source == "vision"


@dataclass(frozen=True)
class DocumentText:
    pdf_path: Path
    pdf_sha256: str
    total_pages: int
    pages: list[PageContent] = field(default_factory=list)

    def is_vision(self) -> bool:
        return any(p.source == "vision" for p in self.pages)

    def text_only(self) -> str:
        """모든 페이지를 [Page N]\n<text>\n 형식으로 결합 (digital PDF용)."""
        if self.is_vision():
            raise ValueError("text_only() called on vision document — use pages directly")
        chunks = [f"[Page {p.page}]\n{p.text or ''}" for p in self.pages]
        return "\n\n".join(chunks)

    def image_payload(self) -> list[str]:
        """Ollama generate API의 images 인자용 base64 PNG 리스트."""
        return [p.image_b64 for p in self.pages if p.image_b64 is not None]


def ingest_pdf(pdf_path: Path) -> DocumentText:
    """디지털 vs 스캔 자동 판정 후 적절한 방식으로 PageContent[] 생성."""
    pdf_path = Path(pdf_path).resolve()
    sha = _hash_file(pdf_path)
    if _is_scanned(pdf_path):
        logger.info(f"{pdf_path.name}: scanned → vision mode")
        return _ingest_as_images(pdf_path, sha)
    logger.info(f"{pdf_path.name}: digital → pdfplumber")
    return _ingest_as_text(pdf_path, sha)


def _is_scanned(pdf_path: Path) -> bool:
    with pdfplumber.open(pdf_path) as doc:
        probe_n = min(SCAN_PROBE_PAGES, len(doc.pages))
        for i in range(probe_n):
            t = doc.pages[i].extract_text() or ""
            if len(t.strip()) >= SCANNED_TEXT_THRESHOLD_CHARS:
                return False
        return True


def _ingest_as_text(pdf_path: Path, sha: str) -> DocumentText:
    pages: list[PageContent] = []
    with pdfplumber.open(pdf_path) as doc:
        total = len(doc.pages)
        for i, page in enumerate(doc.pages, start=1):
            t = (page.extract_text() or "").strip()
            pages.append(PageContent(page=i, source="embedded", text=t))
    return DocumentText(pdf_path=pdf_path, pdf_sha256=sha, total_pages=total, pages=pages)


def _ingest_as_images(pdf_path: Path, sha: str) -> DocumentText:
    kwargs: dict = {"dpi": IMAGE_DPI}
    if _POPPLER_PATH:
        kwargs["poppler_path"] = _POPPLER_PATH
    images = convert_from_path(str(pdf_path), **kwargs)
    pages: list[PageContent] = []
    for i, img in enumerate(images, start=1):
        b64 = _image_to_base64_png(img)
        pages.append(PageContent(page=i, source="vision", image_b64=b64))
    return DocumentText(pdf_path=pdf_path, pdf_sha256=sha, total_pages=len(images), pages=pages)


def _image_to_base64_png(img: Image.Image) -> str:
    if max(img.size) > IMAGE_MAX_DIMENSION:
        ratio = IMAGE_MAX_DIMENSION / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
