"""2-pass extraction orchestration — Gemma 4 backend.

Pass 1: contract PDF → SideExtraction (vision 입력 또는 텍스트)
Pass 2: IM PDF → SideExtraction (텍스트 입력)
merge → ExtractionResult
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from src.client.ollama_client import OllamaClient, OllamaResult
from src.extraction.side_schemas import SideExtraction, merge_sides
from src.ingest.pdf_to_text import DocumentText, ingest_pdf
from src.schemas.extraction import DocumentRole, ExtractionResult

logger = logging.getLogger(__name__)


SYSTEM_RULES = """\
당신은 한국 사모펀드 신탁계약서·투자제안서 검토 전문가입니다.

다음 14개 필드를 추출하세요:

| 개념 | 필드 |
|---|---|
| fund | name, type, inception_date, maturity_date |
| party | asset_manager, trustee, distributor |
| fee_schedule | management_fee, trust_fee, sales_fee |
| redemption_terms | is_redeemable, lockup_period, redemption_cycle, redemption_fee |

규칙:
1. raw_text는 원문 그대로 (요약·바꿔 쓰기 금지).
2. citation.page는 PDF 뷰어 표시 페이지 (1-based 정수).
3. citation.document는 정확히 "{doc_role}" 로.
4. 본문에 없는 값: value=null, unit=null, raw_text=null, citation=null.
5. 추측 금지. 본문에 명시된 것만 추출.
6. unit 예시: "percent_per_year", "permille_per_year", "date", "boolean", "company_name", "fund_name", "fund_type", "fee_text", "months".

예시 (운용보수, 신탁계약서):
{{"raw_text": "집합투자업자보수율 : 연 1,000분의 8.9", "page": 15, "value": "1000분의 8.9", "unit": "permille_per_year", "citation": {{"document": "신탁계약서", "page": 15}}}}

JSON으로만 답하세요.
"""


@dataclass(frozen=True)
class SidePassResult:
    """한 면(side) 추출 패스의 결과."""
    side: Literal["contract", "im"]
    document_role: DocumentRole
    side_extraction: SideExtraction
    pdf_pages: int
    pdf_sha256: str
    ollama_meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractionRun:
    """전체 추출 1회의 모든 결과 + 메타."""
    extraction: ExtractionResult
    contract_pass: SidePassResult
    im_pass: SidePassResult
    model: str
    model_digest: str
    seed: int
    temperature: float
    total_eval_ms: int
    total_wall_ms: int


def extract_from_pdfs(
    contract_pdf: Path,
    im_pdf: Path,
    client: OllamaClient,
) -> ExtractionRun:
    """2-pass 추출. PDF 두 개 → ExtractionResult."""
    wall_start = time.time()

    # 1) PDF ingest
    contract_doc = ingest_pdf(contract_pdf)
    im_doc = ingest_pdf(im_pdf)
    logger.info(
        f"ingest done | contract={contract_doc.total_pages}p ({'vision' if contract_doc.is_vision() else 'text'}), "
        f"im={im_doc.total_pages}p ({'vision' if im_doc.is_vision() else 'text'})"
    )

    # 2) Pass 1 — contract side
    contract_pass = _extract_side(
        client=client,
        doc=contract_doc,
        side="contract",
        document_role="신탁계약서",
    )

    # 3) Pass 2 — IM side
    im_pass = _extract_side(
        client=client,
        doc=im_doc,
        side="im",
        document_role="IM",
    )

    # 4) Merge
    extraction = merge_sides(contract_pass.side_extraction, im_pass.side_extraction)

    total_eval_ms = (
        contract_pass.ollama_meta.get("eval_ms", 0) + im_pass.ollama_meta.get("eval_ms", 0)
    )
    total_wall_ms = int((time.time() - wall_start) * 1000)

    return ExtractionRun(
        extraction=extraction,
        contract_pass=contract_pass,
        im_pass=im_pass,
        model=client.model,
        model_digest=client.get_model_digest(),
        seed=client.seed,
        temperature=client.temperature,
        total_eval_ms=total_eval_ms,
        total_wall_ms=total_wall_ms,
    )


def _extract_side(
    client: OllamaClient,
    doc: DocumentText,
    side: Literal["contract", "im"],
    document_role: DocumentRole,
) -> SidePassResult:
    schema = SideExtraction.model_json_schema()

    prompt = SYSTEM_RULES.format(doc_role=document_role)
    images: list[str] | None = None

    if doc.is_vision():
        prompt += (
            f"\n\n[입력 문서: {document_role}, 이미지로 첨부, 총 {doc.total_pages} 페이지]\n"
            f"각 이미지가 1, 2, ..., {doc.total_pages} 페이지 순서입니다.\n"
        )
        images = doc.image_payload()
    else:
        prompt += f"\n\n[입력 문서: {document_role}, 텍스트, 총 {doc.total_pages} 페이지]\n\n{doc.text_only()}"

    result: OllamaResult = client.generate(
        prompt=prompt, json_schema=schema, images=images
    )

    parsed = SideExtraction.model_validate_json(result.response_text)

    return SidePassResult(
        side=side,
        document_role=document_role,
        side_extraction=parsed,
        pdf_pages=doc.total_pages,
        pdf_sha256=doc.pdf_sha256,
        ollama_meta={
            "model": result.model,
            "model_digest": result.model_digest,
            "prompt_eval_count": result.prompt_eval_count,
            "eval_count": result.eval_count,
            "eval_ms": result.eval_ms,
            "total_ms": result.total_ms,
        },
    )
