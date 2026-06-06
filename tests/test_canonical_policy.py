from src.canonical.policy import load_field_policies


EXPECTED_FIELDS = {
    "fund.name",
    "fund.type",
    "fund.inception_date",
    "fund.maturity_date",
    "party.asset_manager",
    "party.trustee",
    "party.distributor",
    "fee_schedule.management_fee",
    "fee_schedule.trust_fee",
    "fee_schedule.sales_fee",
    "redemption_terms.is_redeemable",
    "redemption_terms.lockup_period",
    "redemption_terms.redemption_cycle",
    "redemption_terms.redemption_fee",
}


def test_field_policies_cover_all_extraction_fields():
    policies = load_field_policies()
    assert set(policies) == EXPECTED_FIELDS


def test_fee_policy_allows_judge_fallback_and_uses_percent_canonicalizer():
    policies = load_field_policies()
    sales_fee = policies["fee_schedule.sales_fee"]
    assert sales_fee.value_type == "percent_per_year"
    assert sales_fee.canonicalizer == "percent"
    assert sales_fee.compare_policy == "numeric_equal"
    assert sales_fee.judge_allowed is True


def test_entity_policy_routes_to_judge_fallback():
    policies = load_field_policies()
    trustee = policies["party.trustee"]
    assert trustee.canonicalizer == "none"
    assert trustee.compare_policy == "judge_fallback"
    assert trustee.judge_allowed is True
