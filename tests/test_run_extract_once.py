import json

from scripts.run_extract_once import write_run_outputs
from src.pipelines.cross_check import cross_check_extraction
from src.pipelines.normalize import NormalizationStatus, NormalizationResult
from src.schemas.extraction import ExtractionResult


def test_write_run_outputs_writes_extraction_and_cross_check(tmp_path):
    extraction = _valid_extraction()
    cross_check_results = cross_check_extraction(extraction)

    write_run_outputs(
        output_dir=tmp_path,
        extraction=extraction,
        cross_check_results=cross_check_results,
        judgements=[],
    )

    extraction_path = tmp_path / "extraction.json"
    cross_check_path = tmp_path / "cross_check.json"
    judgements_path = tmp_path / "llm_judgements.json"

    assert extraction_path.exists()
    assert cross_check_path.exists()
    assert judgements_path.exists()
    assert json.loads(extraction_path.read_text(encoding="utf-8"))["schema_version"] == "v0"
    assert len(json.loads(cross_check_path.read_text(encoding="utf-8"))) == 14
    assert json.loads(judgements_path.read_text(encoding="utf-8")) == []


def test_write_run_outputs_writes_normalization_when_provided(tmp_path):
    extraction = _valid_extraction()
    cross_check_results = cross_check_extraction(extraction)
    normalization_results = [
        NormalizationResult(
            field="fund.name",
            label="펀드명",
            status=NormalizationStatus.NOT_NORMALIZED,
            reason_code="field_not_in_scope",
            reason="The field is outside W1 normalization scope.",
            contract={
                "raw_text": "이지스 블랙ON 일반사모투자신탁제1호",
                "normalized_text": None,
                "normalized_value": None,
                "normalized_unit": None,
                "method": "not_normalized",
                "reason_code": "field_not_in_scope",
                "reason": "The field is outside W1 normalization scope.",
            },
            im={
                "raw_text": "이지스 블랙ON 일반사모투자신탁제1호",
                "normalized_text": None,
                "normalized_value": None,
                "normalized_unit": None,
                "method": "not_normalized",
                "reason_code": "field_not_in_scope",
                "reason": "The field is outside W1 normalization scope.",
            },
        )
    ]

    write_run_outputs(
        output_dir=tmp_path,
        extraction=extraction,
        cross_check_results=cross_check_results,
        judgements=[],
        normalization_results=normalization_results,
    )

    normalization_path = tmp_path / "normalization.json"
    assert normalization_path.exists()
    assert json.loads(normalization_path.read_text(encoding="utf-8"))[0]["field"] == "fund.name"


def test_write_run_outputs_writes_rdf_and_shacl_outputs(tmp_path):
    extraction = _valid_extraction()
    cross_check_results = cross_check_extraction(extraction)

    write_run_outputs(
        output_dir=tmp_path,
        extraction=extraction,
        cross_check_results=cross_check_results,
        judgements=[],
        include_ontology_outputs=True,
    )

    abox_path = tmp_path / "abox.ttl"
    shacl_report_path = tmp_path / "shacl_report.txt"
    shacl_validation_path = tmp_path / "shacl_validation.json"

    assert abox_path.exists()
    assert "data:fund_contract" in abox_path.read_text(encoding="utf-8")
    assert shacl_report_path.exists()
    validation = json.loads(shacl_validation_path.read_text(encoding="utf-8"))
    assert validation["conforms"] is False


def _valid_extraction() -> ExtractionResult:
    missing = {"value": None, "unit": None, "raw_text": None, "citation": None}
    pair = {
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
    }
    missing_pair = {"contract": missing, "im": missing}
    return ExtractionResult.model_validate(
        {
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
    )
