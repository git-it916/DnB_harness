import json

from src.pipelines.extract import (
    DocumentInput,
    build_extraction_content,
    extract_from_documents,
)


def test_build_extraction_content_uses_pdf_document_blocks(tmp_path):
    contract_pdf = tmp_path / "contract.pdf"
    im_pdf = tmp_path / "im.pdf"
    contract_pdf.write_bytes(b"%PDF-contract")
    im_pdf.write_bytes(b"%PDF-im")

    content = build_extraction_content(
        [
            DocumentInput(role="신탁계약서", path=contract_pdf),
            DocumentInput(role="IM", path=im_pdf),
        ]
    )

    assert content[0]["type"] == "document"
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "application/pdf"
    assert content[0]["source"]["data"]
    assert content[1]["type"] == "text"
    assert "문서 역할: 신탁계약서" in content[1]["text"]
    assert content[2]["type"] == "document"
    assert content[3]["type"] == "text"
    assert "문서 역할: IM" in content[3]["text"]
    assert content[-1]["type"] == "text"
    assert "지정된 JSON 구조만 출력" in content[-1]["text"]


def test_extract_from_documents_validates_llm_json_response(tmp_path):
    contract_pdf = tmp_path / "contract.pdf"
    im_pdf = tmp_path / "im.pdf"
    contract_pdf.write_bytes(b"%PDF-contract")
    im_pdf.write_bytes(b"%PDF-im")
    llm = FakeExtractionLLM(_valid_extraction_payload())

    result = extract_from_documents(
        [
            DocumentInput(role="신탁계약서", path=contract_pdf),
            DocumentInput(role="IM", path=im_pdf),
        ],
        llm=llm,
    )

    assert result.schema_version == "v0"
    assert result.fund.name.contract.raw_text == "이지스 블랙ON 일반사모투자신탁제1호"
    assert llm.system_prompt.startswith("# 역할")
    assert isinstance(llm.content, list)


class FakeExtractionLLM:
    def __init__(self, response):
        self.response = response
        self.system_prompt = None
        self.content = None

    def complete_json_with_content(self, *, system_prompt: str, content: list[dict]):
        self.system_prompt = system_prompt
        self.content = content
        return self.response


def _valid_extraction_payload():
    missing = {"value": None, "unit": None, "raw_text": None, "citation": None}
    pair = {
        "contract": {
            "value": "이지스 블랙ON 일반사모투자신탁제1호",
            "unit": "fund_name",
            "raw_text": "이지스 블랙ON 일반사모투자신탁제1호",
            "citation": {"document": "신탁계약서", "page": 1},
        },
        "im": {
            "value": "이지스 블랙ON 일반사모투자신탁제1호",
            "unit": "fund_name",
            "raw_text": "이지스 블랙ON 일반사모투자신탁제1호",
            "citation": {"document": "IM", "page": 1},
        },
    }
    missing_pair = {"contract": missing, "im": missing}
    return json.loads(
        json.dumps(
            {
                "schema_version": "v0",
                "fund": {
                    "name": pair,
                    "type": missing_pair,
                    "inception_date": missing_pair,
                    "maturity_date": missing_pair,
                },
                "party": {
                    "asset_manager": missing_pair,
                    "trustee": missing_pair,
                    "distributor": missing_pair,
                },
                "fee_schedule": {
                    "management_fee": missing_pair,
                    "trust_fee": missing_pair,
                    "sales_fee": missing_pair,
                },
                "redemption_terms": {
                    "is_redeemable": missing_pair,
                    "lockup_period": missing_pair,
                    "redemption_cycle": missing_pair,
                    "redemption_fee": missing_pair,
                },
            }
        )
    )
