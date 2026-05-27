import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.pipelines.cross_check import (
    CrossCheckResult,
    apply_normalization_to_cross_check,
    cross_check_extraction,
)
from src.pipelines.extract import DocumentInput, extract_from_documents
from src.pipelines.llm_judge import LLMJudgement, judge_needs_review
from src.pipelines.normalize import NormalizationResult, normalize_extraction
from src.ontology.mapping import extraction_to_graph
from src.ontology.validate import validate_graph
from src.schemas.extraction import ExtractionResult


DEFAULT_CONTRACT_PATH = Path(
    "database/제정신탁계약서_날인본_이지스블랙ON1호_20250722_최종버전.pdf"
)
DEFAULT_IM_PATH = Path("database/이지스 블랙ON 1호_준감필.pdf")
DEFAULT_OUTPUT_DIR = Path("reports/manual_extract")


def main() -> None:
    args = _parse_args()
    if args.from_existing_extraction:
        extraction = _read_existing_extraction(args.output_dir / "extraction.json")
    else:
        try:
            extraction = extract_from_documents(
                [
                    DocumentInput(role="신탁계약서", path=args.contract_pdf),
                    DocumentInput(role="IM", path=args.im_pdf),
                ]
            )
        except Exception as exc:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            (args.output_dir / "extraction_error.txt").write_text(
                str(exc), encoding="utf-8"
            )
            raise
    cross_check_results = cross_check_extraction(extraction)
    normalization_results = normalize_extraction(extraction) if args.normalize else None
    if normalization_results is not None:
        cross_check_results = apply_normalization_to_cross_check(
            cross_check_results,
            normalization_results,
        )
    judgements = judge_needs_review(cross_check_results) if args.judge else []
    write_run_outputs(
        output_dir=args.output_dir,
        extraction=extraction,
        cross_check_results=cross_check_results,
        judgements=judgements,
        normalization_results=normalization_results,
        include_ontology_outputs=not args.skip_ontology,
    )
    print(f"Wrote extraction outputs to {args.output_dir}")


def write_run_outputs(
    *,
    output_dir: Path,
    extraction: ExtractionResult,
    cross_check_results: list[CrossCheckResult],
    judgements: list[LLMJudgement],
    normalization_results: list[NormalizationResult] | None = None,
    include_ontology_outputs: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "extraction.json", extraction.model_dump(mode="json"))
    _write_json(
        output_dir / "cross_check.json",
        [result.model_dump(mode="json") for result in cross_check_results],
    )
    _write_json(
        output_dir / "llm_judgements.json",
        [judgement.model_dump(mode="json") for judgement in judgements],
    )
    if normalization_results is not None:
        _write_json(
            output_dir / "normalization.json",
            [result.model_dump(mode="json") for result in normalization_results],
        )
    if include_ontology_outputs:
        _write_ontology_outputs(output_dir=output_dir, extraction=extraction)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_ontology_outputs(*, output_dir: Path, extraction: ExtractionResult) -> None:
    graph = extraction_to_graph(extraction)
    (output_dir / "abox.ttl").write_text(
        graph.serialize(format="turtle"),
        encoding="utf-8",
    )
    validation = validate_graph(graph)
    (output_dir / "shacl_report.txt").write_text(
        validation.report_text,
        encoding="utf-8",
    )
    _write_json(
        output_dir / "shacl_validation.json",
        {"conforms": validation.conforms},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one manual extraction for the W1 ontology pipeline."
    )
    parser.add_argument(
        "--contract-pdf",
        type=Path,
        default=DEFAULT_CONTRACT_PATH,
        help="Path to the trust contract PDF.",
    )
    parser.add_argument(
        "--im-pdf",
        type=Path,
        default=DEFAULT_IM_PATH,
        help="Path to the investment memo PDF.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where extraction outputs will be written.",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Also run LLM Judge for needs_review cross-check results.",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Also run AI normalization and write normalization.json.",
    )
    parser.add_argument(
        "--from-existing-extraction",
        action="store_true",
        help="Reuse output-dir/extraction.json instead of running PDF extraction.",
    )
    parser.add_argument(
        "--skip-ontology",
        action="store_true",
        help="Do not write RDF/ABox and SHACL validation outputs.",
    )
    return parser.parse_args()


def _read_existing_extraction(path: Path) -> ExtractionResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ExtractionResult.model_validate(payload)


if __name__ == "__main__":
    main()
