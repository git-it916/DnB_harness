from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator


DocumentRole = Literal["신탁계약서", "IM"]


class StrictSchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(StrictSchemaModel):
    document: DocumentRole
    page: PositiveInt = Field(description="PDF viewer page number, 1-based.")


class DocumentValue(StrictSchemaModel):
    value: str | None
    unit: str | None
    raw_text: str | None
    citation: Citation | None

    @model_validator(mode="after")
    def require_citation_for_evidence(self) -> "DocumentValue":
        if self.raw_text is not None and self.citation is None:
            raise ValueError("citation is required when raw_text exists")
        return self


class ComparableField(StrictSchemaModel):
    contract: DocumentValue
    im: DocumentValue


class FundExtraction(StrictSchemaModel):
    name: ComparableField
    type: ComparableField
    inception_date: ComparableField
    maturity_date: ComparableField


class PartyExtraction(StrictSchemaModel):
    asset_manager: ComparableField
    trustee: ComparableField
    distributor: ComparableField


class FeeScheduleExtraction(StrictSchemaModel):
    management_fee: ComparableField
    trust_fee: ComparableField
    sales_fee: ComparableField


class RedemptionTermsExtraction(StrictSchemaModel):
    is_redeemable: ComparableField
    lockup_period: ComparableField
    redemption_cycle: ComparableField
    redemption_fee: ComparableField


class ExtractionResult(StrictSchemaModel):
    schema_version: Literal["v0"]
    fund: FundExtraction
    party: PartyExtraction
    fee_schedule: FeeScheduleExtraction
    redemption_terms: RedemptionTermsExtraction
