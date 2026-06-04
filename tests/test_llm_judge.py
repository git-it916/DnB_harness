import pytest
from pydantic import ValidationError

from src.pipelines.cross_check import (
    CrossCheckResult,
    CrossCheckStatus,
    CrossCheckValue,
    JudgeInput,
    MissingSide,
)
from src.pipelines.llm_judge import (
    JudgeStatus,
    judge_maturity,
    judge_needs_review,
    judge_redemption_fee,
    judge_prompt_for_input,
    judge_redeemability,
    resolve_maturity_judgement,
    resolve_redemption_fee_judgement,
    resolve_redeemability_judgement,
)
from src.schemas.extraction import Citation


def test_judge_prompt_contains_only_field_label_and_raw_text():
    judge_input = JudgeInput(
        field="fee_schedule.management_fee",
        label="운용보수",
        contract_raw_text="운용보수는 연 0.7%로 한다",
        im_raw_text="운용보수 연 0.7%",
    )

    prompt = judge_prompt_for_input(judge_input)

    assert "fee_schedule.management_fee" in prompt
    assert "운용보수" in prompt
    assert "운용보수는 연 0.7%로 한다" in prompt
    assert "운용보수 연 0.7%" in prompt
    assert "citation" not in prompt
    assert "page" not in prompt
    assert "신탁계약서" not in prompt
    assert "IM" not in prompt


def test_judge_needs_review_calls_model_only_for_needs_review_results():
    llm = FakeJudgeLLM(
        [
            {
                "field": "fee_schedule.management_fee",
                "reason": "두 문장 모두 운용보수를 연 0.7%로 설명한다.",
                "status": "same",
            }
        ]
    )

    judgements = judge_needs_review(
        [
            _cross_check_result(
                field="fund.name",
                status=CrossCheckStatus.EXACT_MATCH,
                contract_raw_text="이지스 블랙ON 일반사모투자신탁제1호",
                im_raw_text="이지스 블랙ON 일반사모투자신탁제1호",
            ),
            _cross_check_result(
                field="fee_schedule.management_fee",
                status=CrossCheckStatus.NEEDS_REVIEW,
                contract_raw_text="운용보수는 연 0.7%로 한다",
                im_raw_text="운용보수 연 0.7%",
            ),
        ],
        llm=llm,
    )

    assert len(llm.prompts) == 1
    assert len(judgements) == 1
    assert judgements[0].field == "fee_schedule.management_fee"
    assert judgements[0].reason == "두 문장 모두 운용보수를 연 0.7%로 설명한다."
    assert judgements[0].status == JudgeStatus.SAME


def test_judge_needs_review_rejects_wrong_field_in_model_response():
    llm = FakeJudgeLLM(
        [
            {
                "field": "fund.name",
                "reason": "다른 필드를 반환했다.",
                "status": "different",
            }
        ]
    )

    with pytest.raises(ValueError, match="field mismatch"):
        judge_needs_review(
            [
                _cross_check_result(
                    field="fee_schedule.management_fee",
                    status=CrossCheckStatus.NEEDS_REVIEW,
                    contract_raw_text="운용보수는 연 0.7%로 한다",
                    im_raw_text="운용보수 연 0.7%",
                )
            ],
            llm=llm,
        )


def test_judge_needs_review_rejects_status_outside_same_or_different():
    llm = FakeJudgeLLM(
        [
            {
                "field": "fee_schedule.management_fee",
                "reason": "판단을 보류했다.",
                "status": "unclear",
            }
        ]
    )

    with pytest.raises(ValidationError):
        judge_needs_review(
            [
                _cross_check_result(
                    field="fee_schedule.management_fee",
                    status=CrossCheckStatus.NEEDS_REVIEW,
                    contract_raw_text="운용보수는 연 0.7%로 한다",
                    im_raw_text="운용보수 연 0.7%",
                )
            ],
            llm=llm,
        )


def test_redeemability_judge_resolves_same_no_to_same():
    llm = FakeJudgeLLM(
        [
            {
                "field": "redemption_terms.is_redeemable",
                "contract_redeemable": "no",
                "im_redeemable": "no",
                "confidence": "high",
                "reason_code": "same_no",
                "contract_evidence": "환매를 청구할 수 없다",
                "im_evidence": "환매가 허용되지 않는 폐쇄형",
                "reason": "양쪽 모두 만기 전 환매 불가를 말한다.",
            }
        ]
    )
    result = _cross_check_result(
        field="redemption_terms.is_redeemable",
        status=CrossCheckStatus.NEEDS_REVIEW,
        contract_raw_text="수익자는 이 투자신탁 수익증권의 환매를 청구할 수 없다.",
        im_raw_text="본 투자신탁은 만기일 이전에는 환매가 허용되지 않는 폐쇄형 투자신탁입니다.",
    )

    judgement = judge_redeemability(result, llm=llm)

    assert judgement.contract_redeemable == "no"
    assert judgement.im_redeemable == "no"
    assert resolve_redeemability_judgement(judgement) == JudgeStatus.SAME


def test_redeemability_judge_resolves_no_yes_to_different():
    llm = FakeJudgeLLM(
        [
            {
                "field": "redemption_terms.is_redeemable",
                "contract_redeemable": "no",
                "im_redeemable": "yes",
                "confidence": "high",
                "reason_code": "different_yes_no",
                "contract_evidence": "환매를 청구할 수 없다",
                "im_evidence": "환매가 허용되는 개방형",
                "reason": "계약서는 환매 불가, IM은 환매 가능이다.",
            }
        ]
    )
    result = _cross_check_result(
        field="redemption_terms.is_redeemable",
        status=CrossCheckStatus.NEEDS_REVIEW,
        contract_raw_text="수익자는 이 투자신탁 수익증권의 환매를 청구할 수 없다.",
        im_raw_text="본 투자신탁은 만기일 이전에도 환매가 허용되는 개방형 투자신탁입니다.",
    )

    judgement = judge_redeemability(result, llm=llm)

    assert resolve_redeemability_judgement(judgement) == JudgeStatus.DIFFERENT


def test_redeemability_judge_low_confidence_stays_review():
    judgement = {
        "field": "redemption_terms.is_redeemable",
        "contract_redeemable": "no",
        "im_redeemable": "yes",
        "confidence": "medium",
        "reason_code": "conditional_unclear",
        "contract_evidence": "환매 제한",
        "im_evidence": "환매 제한",
        "reason": "조건부 표현이다.",
    }

    assert resolve_redeemability_judgement(judgement) is None


def test_maturity_judge_resolves_derived_same_date_to_same():
    llm = FakeJudgeLLM(
        [
            {
                "field": "fund.maturity_date",
                "contract_maturity_date": "2027-07-22",
                "im_maturity_date": "2027-07-22",
                "contract_basis": "absolute_date",
                "im_basis": "derived_from_inception_duration",
                "confidence": "high",
                "reason_code": "same_derived_date",
                "contract_evidence": "2027 년 7 월 22 일까지",
                "im_evidence": "펀드만기 2년",
                "reason": "설정일 2025-07-22에 2년을 더하면 2027-07-22다.",
            }
        ]
    )
    result = _cross_check_result(
        field="fund.maturity_date",
        status=CrossCheckStatus.NEEDS_REVIEW,
        contract_raw_text="최초설정일로부터 2027 년 7 월 22 일까지",
        im_raw_text="펀드만기 2년",
    )

    judgement = judge_maturity(
        result,
        contract_inception_raw="2025년 7월 22일",
        im_inception_raw="2025.07.22",
        llm=llm,
    )

    assert resolve_maturity_judgement(judgement) == JudgeStatus.SAME


def test_maturity_judge_unknown_stays_review():
    judgement = {
        "field": "fund.maturity_date",
        "contract_maturity_date": None,
        "im_maturity_date": "2027-07-22",
        "contract_basis": "unknown",
        "im_basis": "absolute_date",
        "confidence": "high",
        "reason_code": "missing_contract_date",
        "contract_evidence": "만기",
        "im_evidence": "2027-07-22",
        "reason": "계약서 만기일을 확정할 수 없다.",
    }

    assert resolve_maturity_judgement(judgement) is None


def test_redemption_fee_judge_resolves_no_fee_na_to_same():
    llm = FakeJudgeLLM(
        [
            {
                "field": "redemption_terms.redemption_fee",
                "contract_fee_status": "no_fee",
                "im_fee_status": "not_applicable_no_redemption",
                "contract_fee_value": None,
                "im_fee_value": None,
                "confidence": "high",
                "reason_code": "same_no_fee_na",
                "contract_evidence": "해당사항 없음",
                "im_evidence": "환매가 불가능한 폐쇄형",
                "reason": "수수료 부담 또는 적용 상황이 없다.",
            }
        ]
    )
    result = _cross_check_result(
        field="redemption_terms.redemption_fee",
        status=CrossCheckStatus.NEEDS_REVIEW,
        contract_raw_text="제36조(환매수수료) (해당사항 없음)",
        im_raw_text="환매수수료 본 상품은 환매가 불가능한 폐쇄형 상품임",
    )

    judgement = judge_redemption_fee(result, llm=llm)

    assert resolve_redemption_fee_judgement(judgement) == JudgeStatus.SAME


def test_redemption_fee_judge_specified_difference_to_different():
    judgement = {
        "field": "redemption_terms.redemption_fee",
        "contract_fee_status": "fee_specified",
        "im_fee_status": "fee_specified",
        "contract_fee_value": "1.0%",
        "im_fee_value": "2.0%",
        "confidence": "high",
        "reason_code": "different_fee_value",
        "contract_evidence": "1.0%",
        "im_evidence": "2.0%",
        "reason": "명시된 환매수수료가 다르다.",
    }

    assert resolve_redemption_fee_judgement(judgement) == JudgeStatus.DIFFERENT


def test_redemption_fee_judge_conditional_stays_review():
    judgement = {
        "field": "redemption_terms.redemption_fee",
        "contract_fee_status": "conditional_or_exception",
        "im_fee_status": "no_fee",
        "contract_fee_value": None,
        "im_fee_value": None,
        "confidence": "high",
        "reason_code": "conditional_fee",
        "contract_evidence": "특정 사유 시 면제",
        "im_evidence": "없음",
        "reason": "조건부 예외가 있어 자동 비교할 수 없다.",
    }

    assert resolve_redemption_fee_judgement(judgement) is None


class FakeJudgeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def complete_json(self, *, system_prompt: str, user_prompt: str):
        self.prompts.append((system_prompt, user_prompt))
        return self.responses.pop(0)


def _cross_check_result(
    *,
    field: str,
    status: CrossCheckStatus,
    contract_raw_text: str | None,
    im_raw_text: str | None,
) -> CrossCheckResult:
    return CrossCheckResult(
        field=field,
        label="운용보수" if field == "fee_schedule.management_fee" else "펀드명",
        status=status,
        missing_side=MissingSide.NONE,
        contract=CrossCheckValue(
            raw_text=contract_raw_text,
            citation=Citation(document="신탁계약서", page=1)
            if contract_raw_text is not None
            else None,
        ),
        im=CrossCheckValue(
            raw_text=im_raw_text,
            citation=Citation(document="IM", page=1) if im_raw_text is not None else None,
        ),
    )
