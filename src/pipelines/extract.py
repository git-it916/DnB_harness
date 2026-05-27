import base64
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from src.client.anthropic_client import AnthropicJSONClient
from src.schemas.extraction import DocumentRole, ExtractionResult


DEFAULT_EXTRACT_PROMPT_PATH = Path("prompts/v0/extract/system.md")


class ExtractionLLM(Protocol):
    def complete_json_with_content(
        self,
        *,
        system_prompt: str,
        content: list[dict],
    ) -> dict:
        ...

    def complete_text_with_content(
        self,
        *,
        system_prompt: str,
        content: list[dict],
    ) -> str:
        ...


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: DocumentRole
    path: Path


def extract_from_documents(
    documents: list[DocumentInput],
    *,
    llm: ExtractionLLM | None = None,
    system_prompt_path: Path = DEFAULT_EXTRACT_PROMPT_PATH,
) -> ExtractionResult:
    _require_w1_documents(documents)
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    extraction_llm = llm or AnthropicJSONClient(max_tokens=8192)
    content = build_extraction_content(documents)
    if hasattr(extraction_llm, "complete_text_with_content"):
        from src.client.anthropic_client import _parse_json_response

        response_text = extraction_llm.complete_text_with_content(
            system_prompt=system_prompt,
            content=content,
        )
        payload = _parse_json_response(response_text)
    else:
        payload = extraction_llm.complete_json_with_content(
            system_prompt=system_prompt,
            content=content,
        )
    return ExtractionResult.model_validate(payload)


def build_extraction_content(documents: list[DocumentInput]) -> list[dict]:
    _require_w1_documents(documents)
    content: list[dict] = []
    for document in _ordered_documents(documents):
        content.append(_pdf_document_block(document.path))
        content.append(
            {
                "type": "text",
                "text": f"위 PDF의 문서 역할: {document.role}",
            }
        )
    content.append(
        {
            "type": "text",
            "text": (
                "두 PDF를 모두 읽고 prompts/v0/extract/system.md의 규칙에 따라 "
                "지정된 JSON 구조만 출력하라."
            ),
        }
    )
    return content


def _pdf_document_block(path: Path) -> dict:
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"document must be a PDF: {path}")
    if not path.exists():
        raise FileNotFoundError(path)
    encoded_pdf = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": encoded_pdf,
        },
    }


def _require_w1_documents(documents: list[DocumentInput]) -> None:
    roles = {document.role for document in documents}
    if roles != {"신탁계약서", "IM"}:
        raise ValueError("W1 extraction requires exactly 신탁계약서 and IM documents")
    if len(documents) != 2:
        raise ValueError("W1 extraction requires exactly two documents")


def _ordered_documents(documents: list[DocumentInput]) -> list[DocumentInput]:
    order: dict[DocumentRole, int] = {"신탁계약서": 0, "IM": 1}
    return sorted(documents, key=lambda document: order[document.role])
