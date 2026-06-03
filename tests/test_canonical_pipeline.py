from src.canonical.pipeline import cross_check_with_policy
from src.schemas.extraction import (
    Citation,
    ComparableField,
    DocumentValue,
    ExtractionResult,
    FeeScheduleExtraction,
    FundExtraction,
    PartyExtraction,
    RedemptionTermsExtraction,
)


def _dv(raw: str | None, document: str = "신탁계약서") -> DocumentValue:
    if raw is None:
        return DocumentValue(value=None, unit=None, raw_text=None, citation=None)
    return DocumentValue(
        value=None,
        unit=None,
        raw_text=raw,
        citation=Citation(document=document, page=1),
    )


def _field(contract: str | None, im: str | None) -> ComparableField:
    return ComparableField(contract=_dv(contract), im=_dv(im, "IM"))


def _empty_field() -> ComparableField:
    return _field(None, None)


def _extraction(**fields) -> ExtractionResult:
    return ExtractionResult(
        schema_version="v0",
        fund=FundExtraction(
            name=fields.get("fund_name", _empty_field()),
            type=fields.get("fund_type", _empty_field()),
            inception_date=fields.get("inception_date", _empty_field()),
            maturity_date=fields.get("maturity_date", _empty_field()),
        ),
        party=PartyExtraction(
            asset_manager=_empty_field(),
            trustee=_empty_field(),
            distributor=_empty_field(),
        ),
        fee_schedule=FeeScheduleExtraction(
            management_fee=fields.get("management_fee", _empty_field()),
            trust_fee=_empty_field(),
            sales_fee=fields.get("sales_fee", _empty_field()),
        ),
        redemption_terms=RedemptionTermsExtraction(
            is_redeemable=fields.get("is_redeemable", _empty_field()),
            lockup_period=fields.get("lockup_period", _empty_field()),
            redemption_cycle=_empty_field(),
            redemption_fee=fields.get("redemption_fee", _empty_field()),
        ),
    )


def test_policy_cross_check_adds_canonical_metadata_for_percent_match():
    extraction = _extraction(
        management_fee=_field("연 1,000분의 8.9", "[운용] 연[ 0.89 ] %")
    )
    result = next(
        r for r in cross_check_with_policy(extraction)
        if r.field == "fee_schedule.management_fee"
    )
    assert result.final_status == "same_after_normalization"
    assert result.canonical_status == "decisive"
    assert result.canonical["contract"]["method"] == "permille"


def test_policy_cross_check_derives_maturity_from_same_side_inception():
    extraction = _extraction(
        inception_date=_field("2025년 7월 22일", "2025.07.22"),
        maturity_date=_field("설정일로부터 3년", "2028-07-22"),
    )
    result = next(
        r for r in cross_check_with_policy(extraction)
        if r.field == "fund.maturity_date"
    )
    assert result.final_status == "same_after_normalization"
    assert result.canonical["contract"]["value"] == "2028-07-22"


def test_policy_cross_check_maturity_standalone_duration_is_not_decisive():
    extraction = _extraction(
        inception_date=_field("2025년 7월 22일", "2025.07.22"),
        maturity_date=_field("3년", "2028-07-22"),
    )
    result = next(
        r for r in cross_check_with_policy(extraction)
        if r.field == "fund.maturity_date"
    )
    assert result.final_status == "needs_review"
    assert result.canonical_status == "non_decisive"
