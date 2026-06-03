from src.canonical.parsers import (
    parse_boolean,
    parse_date,
    parse_duration_months,
    parse_percent,
)


def test_parse_percent_explicit_units():
    assert parse_percent("연 0.89%").value == "0.89"
    assert parse_percent("[운용] 연[ 0.89 ] %").value == "0.89"
    assert parse_percent("연 1,000분의 8.9").value == "0.89"
    assert parse_percent("연 1000분의 8.9").value == "0.89"
    assert parse_percent("연 1천분의 8.9").value == "0.89"
    assert parse_percent("89bp").value == "0.89"


def test_parse_percent_unitless_decimal_is_ambiguous():
    result = parse_percent("0.0089")
    assert result.status == "non_decisive"
    assert result.reason_code == "percent_unit_missing"


def test_parse_date_common_formats():
    assert parse_date("2025-07-22").value == "2025-07-22"
    assert parse_date("2025.07.22").value == "2025-07-22"
    assert parse_date("2025/07/22").value == "2025-07-22"
    assert parse_date("2025년 7월 22일").value == "2025-07-22"


def test_parse_duration_months_years_and_months():
    assert parse_duration_months("3년").value == "36"
    assert parse_duration_months("36개월").value == "36"
    assert parse_duration_months("1년 6개월").value == "18"


def test_parse_boolean_korean_expressions():
    assert parse_boolean("환매 가능").value == "true"
    assert parse_boolean("환매 불가").value == "false"
    assert parse_boolean("환매할 수 없음").value == "false"
