import json
import sys
import types
import unittest

from dnb_harness.ontology.mapping import build_abox
from dnb_harness.ontology.validate import validate_abox


class W1OntologyPipelineTest(unittest.TestCase):
    def test_build_abox_merges_extraction_and_normalization(self):
        tmp_path = self.tmp_path
        extraction_path = tmp_path / "extraction_after_guards.json"
        normalization_path = tmp_path / "normalization.json"
        output_path = tmp_path / "abox.ttl"

        extraction_path.write_text(
            json.dumps(
                {
                    "schema_version": "v0",
                    "fund": {
                        "inception_date": {
                            "contract": {
                                "value": "2025년 7월 22일",
                                "unit": "date",
                                "raw_text": "2025년 7월 22일",
                                "citation": {"document": "신탁계약서", "page": 4},
                            },
                            "im": {
                                "value": "2025-07-22",
                                "unit": "date",
                                "raw_text": "2025년7월22일",
                                "citation": {"document": "IM", "page": 9},
                            },
                        }
                    },
                    "fee_schedule": {
                        "management_fee": {
                            "contract": {
                                "value": "1000분의 8.9",
                                "unit": "permille_per_year",
                                "raw_text": "집합투자업자보수율 : 연 1,000분의 8.9",
                                "citation": {"document": "신탁계약서", "page": 15},
                            },
                            "im": {
                                "value": "0.89",
                                "unit": "percent_per_year",
                                "raw_text": "[운용]연[ 0.89 ] %",
                                "citation": {"document": "IM", "page": 9},
                            },
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        normalization_path.write_text(
            json.dumps(
                [
                    {
                        "field": "fund.inception_date",
                        "contract": {
                            "normalized_value": "2025-07-22",
                            "normalized_unit": "date",
                        },
                        "im": {
                            "normalized_value": "2025-07-22",
                            "normalized_unit": "date",
                        },
                    },
                    {
                        "field": "fee_schedule.management_fee",
                        "contract": {
                            "normalized_value": 0.89,
                            "normalized_unit": "percent_per_year",
                        },
                        "im": {
                            "normalized_value": 0.89,
                            "normalized_unit": "percent_per_year",
                        },
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        build_abox(
            extraction_path=extraction_path,
            normalization_path=normalization_path,
            output_path=output_path,
        )

        ttl = output_path.read_text(encoding="utf-8")

        self.assertIn("data:fund_contract a dnb:Fund", ttl)
        self.assertIn('dnb:inception_date_value "2025년 7월 22일"', ttl)
        self.assertIn("data:fund_im a dnb:Fund", ttl)
        self.assertIn('dnb:inception_date_document "IM"', ttl)
        self.assertIn("data:fee_schedule_contract a dnb:FeeSchedule", ttl)
        self.assertIn('dnb:management_fee_normalized_value "0.89"^^xsd:decimal', ttl)
        self.assertIn("data:fee_schedule_im a dnb:FeeSchedule", ttl)
        self.assertIn('dnb:management_fee_normalized_unit "percent_per_year"', ttl)

    def test_validate_abox_uses_pyshacl_and_writes_json_result(self):
        tmp_path = self.tmp_path
        data_path = tmp_path / "abox.ttl"
        shapes_path = tmp_path / "shapes.ttl"
        output_path = tmp_path / "shacl_validation.json"

        data_path.write_text(
            """
@prefix data: <https://dnb-harness.local/data#> .
@prefix dnb: <https://dnb-harness.local/ontology#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

data:fee_schedule_contract a dnb:FeeSchedule ;
  dnb:management_fee_normalized_value 0.89 ;
  dnb:management_fee_normalized_unit "percent_per_year" .
""".strip(),
            encoding="utf-8",
        )
        shapes_path.write_text(
            """
@prefix dnb: <https://dnb-harness.local/ontology#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

dnb:FeeScheduleShape a sh:NodeShape ;
  sh:targetClass dnb:FeeSchedule ;
  sh:property [
    sh:path dnb:management_fee_normalized_value ;
    sh:minInclusive 0 ;
    sh:maxInclusive 5 ;
    sh:datatype xsd:decimal ;
  ] .
""".strip(),
            encoding="utf-8",
        )

        calls = []

        def fake_validate(**kwargs):
            calls.append(kwargs)
            return True, None, "Conforms"

        fake_pyshacl = types.SimpleNamespace(validate=fake_validate)
        original_pyshacl = sys.modules.get("pyshacl")
        sys.modules["pyshacl"] = fake_pyshacl
        try:
            result = validate_abox(
                data_path=data_path,
                shapes_path=shapes_path,
                output_path=output_path,
            )
        finally:
            if original_pyshacl is None:
                sys.modules.pop("pyshacl", None)
            else:
                sys.modules["pyshacl"] = original_pyshacl

        saved = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(calls[0]["data_graph"], str(data_path))
        self.assertEqual(calls[0]["shacl_graph"], str(shapes_path))
        self.assertIs(result["conforms"], True)
        self.assertEqual(result["engine"], "pyshacl")
        self.assertIs(saved["conforms"], True)
        self.assertEqual(saved["violations"], [])

    def test_validate_abox_requires_pyshacl_by_default(self):
        tmp_path = self.tmp_path
        data_path = tmp_path / "abox.ttl"
        shapes_path = tmp_path / "shapes.ttl"
        output_path = tmp_path / "shacl_validation.json"
        data_path.write_text("@prefix data: <https://dnb-harness.local/data#> .", encoding="utf-8")
        shapes_path.write_text("@prefix sh: <http://www.w3.org/ns/shacl#> .", encoding="utf-8")

        original_pyshacl = sys.modules.pop("pyshacl", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "pyshacl is required"):
                validate_abox(
                    data_path=data_path,
                    shapes_path=shapes_path,
                    output_path=output_path,
                )
        finally:
            if original_pyshacl is not None:
                sys.modules["pyshacl"] = original_pyshacl

    def setUp(self):
        import tempfile
        from pathlib import Path

        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()


if __name__ == "__main__":
    unittest.main()
