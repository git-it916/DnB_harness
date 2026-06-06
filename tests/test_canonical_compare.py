from src.canonical.compare import compare_values
from src.canonical.policy import load_field_policies


def test_percent_explicit_units_compare_same():
    policy = load_field_policies()["fee_schedule.management_fee"]
    result = compare_values(
        "fee_schedule.management_fee",
        policy,
        "연 1,000분의 8.9",
        "[운용] 연[ 0.89 ] %",
    )
    assert result.status == "decisive"
    assert result.final_status == "same_after_normalization"
    assert result.reason_code == "canonical_numeric_equal"


def test_percent_explicit_units_compare_different():
    policy = load_field_policies()["fee_schedule.sales_fee"]
    result = compare_values("fee_schedule.sales_fee", policy, "0.3%", "0.03%")
    assert result.status == "decisive"
    assert result.final_status == "different_after_normalization"
    assert result.reason_code == "canonical_numeric_difference"


def test_percent_unitless_value_is_not_decisive():
    policy = load_field_policies()["fee_schedule.sales_fee"]
    result = compare_values("fee_schedule.sales_fee", policy, "0.003", "0.3%")
    assert result.status == "non_decisive"
    assert result.final_status == "needs_review"


def test_duration_values_compare_same():
    policy = load_field_policies()["redemption_terms.lockup_period"]
    result = compare_values("redemption_terms.lockup_period", policy, "3년", "36개월")
    assert result.status == "decisive"
    assert result.final_status == "same_after_normalization"


def test_boolean_values_compare_different():
    policy = load_field_policies()["redemption_terms.is_redeemable"]
    result = compare_values("redemption_terms.is_redeemable", policy, "환매 가능", "환매 불가")
    assert result.status == "decisive"
    assert result.final_status == "different_after_normalization"
