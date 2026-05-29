"""한 문서(side) 측 추출 스키마.

2-pass 추출 전략에서 한 번에 한 문서만 처리하기 위한 평탄한 구조.
contract / im 정보가 빠져있고, 호출 후 merge_sides() 로 ExtractionResult 합성.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.schemas.extraction import (
    ComparableField,
    DocumentValue,
    ExtractionResult,
    FeeScheduleExtraction,
    FundExtraction,
    PartyExtraction,
    RedemptionTermsExtraction,
)


class StrictSideModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FundSide(StrictSideModel):
    name: DocumentValue
    type: DocumentValue
    inception_date: DocumentValue
    maturity_date: DocumentValue


class PartySide(StrictSideModel):
    asset_manager: DocumentValue
    trustee: DocumentValue
    distributor: DocumentValue


class FeeScheduleSide(StrictSideModel):
    management_fee: DocumentValue
    trust_fee: DocumentValue
    sales_fee: DocumentValue


class RedemptionTermsSide(StrictSideModel):
    is_redeemable: DocumentValue
    lockup_period: DocumentValue
    redemption_cycle: DocumentValue
    redemption_fee: DocumentValue


class SideExtraction(StrictSideModel):
    fund: FundSide
    party: PartySide
    fee_schedule: FeeScheduleSide
    redemption_terms: RedemptionTermsSide


def merge_sides(contract_side: SideExtraction, im_side: SideExtraction) -> ExtractionResult:
    """contract + im SideExtraction → ExtractionResult.

    각 필드를 ComparableField(contract=..., im=...) 형태로 묶어준다.
    """
    return ExtractionResult(
        schema_version="v0",
        fund=FundExtraction(
            name=ComparableField(contract=contract_side.fund.name, im=im_side.fund.name),
            type=ComparableField(contract=contract_side.fund.type, im=im_side.fund.type),
            inception_date=ComparableField(
                contract=contract_side.fund.inception_date, im=im_side.fund.inception_date
            ),
            maturity_date=ComparableField(
                contract=contract_side.fund.maturity_date, im=im_side.fund.maturity_date
            ),
        ),
        party=PartyExtraction(
            asset_manager=ComparableField(
                contract=contract_side.party.asset_manager, im=im_side.party.asset_manager
            ),
            trustee=ComparableField(contract=contract_side.party.trustee, im=im_side.party.trustee),
            distributor=ComparableField(
                contract=contract_side.party.distributor, im=im_side.party.distributor
            ),
        ),
        fee_schedule=FeeScheduleExtraction(
            management_fee=ComparableField(
                contract=contract_side.fee_schedule.management_fee,
                im=im_side.fee_schedule.management_fee,
            ),
            trust_fee=ComparableField(
                contract=contract_side.fee_schedule.trust_fee, im=im_side.fee_schedule.trust_fee
            ),
            sales_fee=ComparableField(
                contract=contract_side.fee_schedule.sales_fee, im=im_side.fee_schedule.sales_fee
            ),
        ),
        redemption_terms=RedemptionTermsExtraction(
            is_redeemable=ComparableField(
                contract=contract_side.redemption_terms.is_redeemable,
                im=im_side.redemption_terms.is_redeemable,
            ),
            lockup_period=ComparableField(
                contract=contract_side.redemption_terms.lockup_period,
                im=im_side.redemption_terms.lockup_period,
            ),
            redemption_cycle=ComparableField(
                contract=contract_side.redemption_terms.redemption_cycle,
                im=im_side.redemption_terms.redemption_cycle,
            ),
            redemption_fee=ComparableField(
                contract=contract_side.redemption_terms.redemption_fee,
                im=im_side.redemption_terms.redemption_fee,
            ),
        ),
    )
