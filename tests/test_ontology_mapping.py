from rdflib import RDF, Graph, Literal, Namespace

from src.ontology.mapping import extraction_to_graph
from src.schemas.extraction import ExtractionResult


DNB = Namespace("https://dnb-harness.local/ontology#")
DATA = Namespace("https://dnb-harness.local/data#")


def test_extraction_to_graph_creates_document_scoped_nodes():
    graph = extraction_to_graph(_sample_extraction())

    assert (DATA.fund_contract, RDF.type, DNB.Fund) in graph
    assert (DATA.fund_im, RDF.type, DNB.Fund) in graph
    assert (DATA.party_contract, RDF.type, DNB.Party) in graph
    assert (DATA.fee_schedule_im, RDF.type, DNB.FeeSchedule) in graph
    assert (
        DATA.fund_contract,
        DNB.has_fee_schedule,
        DATA.fee_schedule_contract,
    ) in graph


def test_extraction_to_graph_uses_raw_text_as_rdf_value():
    graph = extraction_to_graph(_sample_extraction())

    assert (
        DATA.fee_schedule_contract,
        DNB.management_fee,
        Literal("운용보수는 연 0.7%로 한다"),
    ) in graph
    assert (
        DATA.fee_schedule_contract,
        DNB.management_fee,
        Literal("0.7"),
    ) not in graph


def test_extraction_to_graph_skips_missing_raw_text():
    graph = extraction_to_graph(_sample_extraction())

    assert (DATA.fee_schedule_contract, DNB.sales_fee, None) not in graph
    assert (DATA.fee_schedule_im, DNB.sales_fee, None) not in graph


def test_extraction_to_graph_does_not_include_citation_values():
    graph = extraction_to_graph(_sample_extraction())
    serialized = graph.serialize(format="turtle")

    assert "citation" not in serialized
    assert "page" not in serialized
    assert "신탁계약서" not in serialized
    assert "IM" not in serialized


def _sample_extraction() -> ExtractionResult:
    missing = {"value": None, "unit": None, "raw_text": None, "citation": None}

    payload = {
        "schema_version": "v0",
        "fund": {
            "name": {
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
            },
            "type": _pair("일반사모투자신탁", "일반사모투자신탁"),
            "inception_date": _pair("설정일은 2024년 5월 31일", "설정일: 2024년 5월 31일"),
            "maturity_date": _pair("만기일은 2029년 5월 31일", "만기일: 2029년 5월 31일"),
        },
        "party": {
            "asset_manager": _pair("집합투자업자: 이지스자산운용", "운용회사: 이지스자산운용"),
            "trustee": _pair("신탁업자: 국민은행", "수탁회사: 국민은행"),
            "distributor": _pair("판매회사: 하나증권", "판매회사: 하나증권"),
        },
        "fee_schedule": {
            "management_fee": {
                "contract": {
                    "value": "0.7",
                    "unit": "percent_per_year",
                    "raw_text": "운용보수는 연 0.7%로 한다",
                    "citation": {"document": "신탁계약서", "page": 12},
                },
                "im": {
                    "value": "0.7",
                    "unit": "percent_per_year",
                    "raw_text": "운용보수 연 0.7%",
                    "citation": {"document": "IM", "page": 8},
                },
            },
            "trust_fee": _pair("신탁보수는 연 0.03%로 한다", "신탁보수 연 0.03%"),
            "sales_fee": {"contract": missing, "im": missing},
        },
        "redemption_terms": {
            "is_redeemable": _pair("수익자는 환매를 청구할 수 있다", "환매 가능"),
            "lockup_period": _pair("설정일로부터 1년간 환매 제한", "1년 락업"),
            "redemption_cycle": _pair("매월 15일 환매청구 가능", "월 1회 환매 가능"),
            "redemption_fee": _pair("환매수수료 없음", "환매수수료 없음"),
        },
    }
    return ExtractionResult.model_validate(payload)


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
