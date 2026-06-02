from rdflib import Graph, Literal, Namespace

from src.ontology.mapping import extraction_to_graph
from src.ontology.validate import validate_graph
from src.schemas.extraction import ExtractionResult


DNB = Namespace("https://dnb-harness.local/ontology#")
DATA = Namespace("https://dnb-harness.local/data#")


def test_trust_fund_ttl_parses():
    graph = Graph()
    graph.parse("ontology/trust_fund.ttl", format="turtle")

    assert len(graph) > 0


def test_validate_graph_conforms_for_minimum_required_w1_values():
    result = validate_graph(extraction_to_graph(_valid_minimum_extraction()))

    assert result.conforms is True
    assert result.report_text


def test_validate_graph_reports_missing_required_w1_value():
    result = validate_graph(extraction_to_graph(_missing_management_fee_extraction()))

    assert result.conforms is False
    assert "management_fee" in result.report_text


def test_validate_graph_allows_missing_im_trustee_company_name():
    result = validate_graph(extraction_to_graph(_missing_im_trustee_extraction()))

    assert result.conforms is True


def test_validate_graph_requires_contract_trustee_company_name():
    result = validate_graph(extraction_to_graph(_missing_contract_trustee_extraction()))

    assert result.conforms is False
    assert "party_contract" in result.report_text
    assert "trustee" in result.report_text


def test_validate_graph_reports_management_fee_above_business_range():
    result = validate_graph(extraction_to_graph(_high_management_fee_extraction()))

    assert result.conforms is False
    assert "management_fee" in result.report_text
    assert "5.0%" in result.report_text


def test_validate_graph_reports_maturity_date_not_after_inception_date():
    result = validate_graph(extraction_to_graph(_maturity_before_inception_extraction()))

    assert result.conforms is False
    assert "maturity_date" in result.report_text
    assert "inception_date" in result.report_text


def test_validate_graph_reports_more_than_one_contract_trustee():
    graph = extraction_to_graph(_valid_minimum_extraction())
    graph.add(
        (
            DATA.party_contract,
            DNB.trustee,
            Literal("신탁업자: 하나은행"),
        )
    )

    result = validate_graph(graph)

    assert result.conforms is False
    assert "party_contract" in result.report_text
    assert "trustee" in result.report_text
    assert "exactly one" in result.report_text


def _valid_minimum_extraction() -> ExtractionResult:
    return ExtractionResult.model_validate(
        {
            "schema_version": "v0",
            "fund": {
                "name": _pair("이지스 블랙ON 일반사모투자신탁제1호", "이지스 블랙ON 일반사모투자신탁제1호"),
                "type": _missing_pair(),
                "inception_date": _missing_pair(),
                "maturity_date": _missing_pair(),
            },
            "party": {
                "asset_manager": _pair("집합투자업자: 이지스자산운용", "운용회사: 이지스자산운용"),
                "trustee": _pair("신탁업자: 국민은행", "수탁회사: 국민은행"),
                "distributor": _missing_pair(),
            },
            "fee_schedule": {
                "management_fee": _pair("운용보수는 연 0.7%로 한다", "운용보수 연 0.7%"),
                "trust_fee": _missing_pair(),
                "sales_fee": _missing_pair(),
            },
            "redemption_terms": {
                "is_redeemable": _missing_pair(),
                "lockup_period": _missing_pair(),
                "redemption_cycle": _missing_pair(),
                "redemption_fee": _missing_pair(),
            },
        }
    )


def _missing_management_fee_extraction() -> ExtractionResult:
    extraction = _valid_minimum_extraction().model_dump()
    extraction["fee_schedule"]["management_fee"] = _missing_pair()
    return ExtractionResult.model_validate(extraction)


def _missing_im_trustee_extraction() -> ExtractionResult:
    extraction = _valid_minimum_extraction().model_dump()
    extraction["party"]["trustee"]["im"] = {
        "value": None,
        "unit": None,
        "raw_text": None,
        "citation": None,
    }
    return ExtractionResult.model_validate(extraction)


def _missing_contract_trustee_extraction() -> ExtractionResult:
    extraction = _valid_minimum_extraction().model_dump()
    extraction["party"]["trustee"]["contract"] = {
        "value": None,
        "unit": None,
        "raw_text": None,
        "citation": None,
    }
    return ExtractionResult.model_validate(extraction)


def _high_management_fee_extraction() -> ExtractionResult:
    extraction = _valid_minimum_extraction().model_dump()
    extraction["fee_schedule"]["management_fee"]["im"] = {
        "value": "8.9",
        "unit": "percent_per_year",
        "raw_text": "[운용] 연[ 8.9 ] %",
        "citation": {"document": "IM", "page": 9},
    }
    return ExtractionResult.model_validate(extraction)


def _maturity_before_inception_extraction() -> ExtractionResult:
    extraction = _valid_minimum_extraction().model_dump()
    extraction["fund"]["inception_date"]["contract"] = {
        "value": "2025-07-22",
        "unit": "date",
        "raw_text": "설정일은 2025년 7월 22일",
        "citation": {"document": "신탁계약서", "page": 1},
    }
    extraction["fund"]["maturity_date"]["contract"] = {
        "value": "2025-07-21",
        "unit": "date",
        "raw_text": "만기일은 2025년 7월 21일",
        "citation": {"document": "신탁계약서", "page": 2},
    }
    return ExtractionResult.model_validate(extraction)


def _pair(contract_raw_text: str, im_raw_text: str):
    return {
        "contract": {
            "value": None,
            "unit": None,
            "raw_text": contract_raw_text,
            "citation": {"document": "신탁계약서", "page": 1},
        },
        "im": {
            "value": None,
            "unit": None,
            "raw_text": im_raw_text,
            "citation": {"document": "IM", "page": 1},
        },
    }


def _missing_pair():
    missing = {"value": None, "unit": None, "raw_text": None, "citation": None}
    return {"contract": missing, "im": missing}
