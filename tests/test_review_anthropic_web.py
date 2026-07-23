from pypdf import PdfWriter

from src.application.review_service import ReviewService
from src.schemas.extraction import ExtractionResult


def test_web_review_uses_anthropic_extraction_provider(tmp_path):
    contract_pdf = tmp_path / "contract.pdf"
    im_pdf = tmp_path / "im.pdf"
    for path in (contract_pdf, im_pdf):
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with path.open("wb") as handle:
            writer.write(handle)

    client = FakeAnthropicExtractionClient(_extraction_payload())
    result = ReviewService(extraction_client=client).run(
        run_id="review_provider_test",
        contract_pdf=contract_pdf,
        im_pdf=im_pdf,
        strategy="ontology_policy",
    )

    assert result.model == "claude-sonnet-4-6"
    assert result.llm_total_tokens == 30
    assert result.total_latency_ms >= 0
    assert [item["type"] for item in client.content].count("document") == 2


def test_generic_judge_result_resolves_field_without_human_review(tmp_path):
    contract_pdf, im_pdf = _blank_pdfs(tmp_path)
    payload = _extraction_payload()
    payload["fund"]["name"]["im"]["raw_text"] = "테스트 펀드 약칭"
    payload["fund"]["name"]["im"]["value"] = "테스트 펀드 약칭"

    result = ReviewService(judge_client=FakeJudgeClient()).review_extraction(
        run_id="review_judge_resolution_test",
        extraction=ExtractionResult.model_validate(payload),
        contract_pdf=contract_pdf,
        im_pdf=im_pdf,
        contract_pages=1,
        im_pages=1,
        strategy="ontology_policy_judge",
    )

    field = next(item for item in result.fields if item.field == "fund.name")
    assert field.effective_status == "match"
    assert field.resolution_source == "llm_judge"
    assert field.requires_human_review is False


def _blank_pdfs(tmp_path):
    paths = (tmp_path / "contract.pdf", tmp_path / "im.pdf")
    for path in paths:
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with path.open("wb") as handle:
            writer.write(handle)
    return paths


class FakeAnthropicExtractionClient:
    model = "claude-sonnet-4-6"

    def __init__(self, response):
        self.response = response
        self.content = []
        self.last_usage = {"input_tokens": 12, "output_tokens": 18}

    def complete_json_with_content(self, *, system_prompt, content):
        self.content = content
        return self.response


class FakeJudgeClient:
    def complete_json(self, *, system_prompt, user_prompt):
        import json

        payload = json.loads(user_prompt)
        return {
            "field": payload["field"],
            "reason": "두 표현은 같은 테스트 펀드를 가리키는 약칭이다.",
            "status": "same",
        }


def _extraction_payload():
    empty = {"value": None, "unit": None, "raw_text": None, "citation": None}
    name = {
        "value": "테스트 펀드",
        "unit": "fund_name",
        "raw_text": "테스트 펀드",
        "citation": {"document": "신탁계약서", "page": 1},
    }
    name_im = {**name, "citation": {"document": "IM", "page": 1}}
    pair = {"contract": name, "im": name_im}
    missing_pair = {"contract": empty, "im": empty}
    return {
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
