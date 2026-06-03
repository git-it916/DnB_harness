"""결정적 골든 평가기 — golden 케이스를 하네스 로직에 통과시켜 예측 레코드 생성.

LLM 호출 없이(=Ollama/Claude 불필요) 동작한다. golden CSV 의 raw_text 를
'추출 결과'로 보고 cross_check(+가드)를 돌려 final_status 와 가드 reject 를 얻는다.

지원 모드:
    - "ontology" : cross_check 만 (가드 OFF, 진단). normalization/judge 는 미적용.
    - "guard"    : G1/G2/G3 가드 적용 후 cross_check. 가드 reject 를 기록.

미지원:
    - "baseline" : LLM 자유 추출이 필요 → src/harness 러너(Stage C)에서 처리.
"""

from __future__ import annotations

from pathlib import Path

from src.guards.base import GuardConfig, GuardContext, GuardDecision
from src.guards.registry import apply_guards
from src.pipelines.cross_check import cross_check_extraction
from src.schemas.extraction import (
    Citation,
    ComparableField,
    DocumentRole,
    DocumentValue,
    ExtractionResult,
    FeeScheduleExtraction,
    FundExtraction,
    PartyExtraction,
    RedemptionTermsExtraction,
)
from src.scoring.golden import GoldenCase
from src.scoring.scorer import CaseRecord

SUPPORTED_MODES = ("ontology", "guard")

# field_path 의 첫 마디 -> (그룹 모델, 그 그룹의 필드명들)
_GROUPS: dict[str, tuple[type, tuple[str, ...]]] = {
    "fund": (FundExtraction, ("name", "type", "inception_date", "maturity_date")),
    "party": (PartyExtraction, ("asset_manager", "trustee", "distributor")),
    "fee_schedule": (FeeScheduleExtraction, ("management_fee", "trust_fee", "sales_fee")),
    "redemption_terms": (
        RedemptionTermsExtraction,
        ("is_redeemable", "lockup_period", "redemption_cycle", "redemption_fee"),
    ),
}


def _empty_value() -> DocumentValue:
    return DocumentValue(value=None, unit=None, raw_text=None, citation=None)


def _empty_field() -> ComparableField:
    return ComparableField(contract=_empty_value(), im=_empty_value())


def _doc_value(raw: str | None, page: int | None, role: DocumentRole) -> DocumentValue:
    if raw is None:
        return _empty_value()
    # raw_text 가 있으면 citation 필수 (DocumentValue 검증). page 없으면 1 로 폴백.
    page_num = page if (page is not None and page > 0) else 1
    return DocumentValue(
        value=None,
        unit=None,
        raw_text=raw,
        citation=Citation(document=role, page=page_num),
    )


def _field_from_case(case: GoldenCase) -> ComparableField:
    return ComparableField(
        contract=_doc_value(case.contract_raw, case.contract_page, "신탁계약서"),
        im=_doc_value(case.im_raw, case.im_page, "IM"),
    )


def _build_extraction(field_path: str, comparable: ComparableField) -> ExtractionResult:
    """해당 field 만 채우고 나머지 13개는 빈 값으로 둔 ExtractionResult."""
    group_name, attr = field_path.split(".", 1)

    def _kwargs(name: str) -> dict[str, ComparableField]:
        _model_cls, attrs = _GROUPS[name]
        return {
            a: (comparable if (name == group_name and a == attr) else _empty_field())
            for a in attrs
        }

    # 그룹별로 명시적 생성 — 정적 타입 보존 (dict[str, object] 우회 금지).
    return ExtractionResult(
        schema_version="v0",
        fund=FundExtraction(**_kwargs("fund")),
        party=PartyExtraction(**_kwargs("party")),
        fee_schedule=FeeScheduleExtraction(**_kwargs("fee_schedule")),
        redemption_terms=RedemptionTermsExtraction(**_kwargs("redemption_terms")),
    )


def _rejections_for_field(events, field_path: str) -> list[str]:
    out: list[str] = []
    for event in events:
        if event.decision != GuardDecision.REJECT:
            continue
        path = event.field_path or ""
        if path == field_path or path.startswith(field_path + "."):
            out.append(f"{event.guard}:{event.reason_code}")
    return out


def evaluate_golden(
    cases: list[GoldenCase],
    *,
    mode: str,
    contract_pages: int,
    im_pages: int,
) -> list[CaseRecord]:
    """골든 케이스 → 케이스별 CaseRecord (결정적, LLM 없음).

    Args:
        cases: load_golden_master() 결과.
        mode: "ontology" | "guard".
        contract_pages / im_pages: 실제 PDF 페이지 수 (G2 출처 범위 검증 기준).

    Raises:
        ValueError: mode 가 SUPPORTED_MODES 가 아닐 때 ('baseline' 은 LLM 러너 필요).
    """
    if mode not in SUPPORTED_MODES:
        raise ValueError(
            f"unsupported mode '{mode}' for deterministic evaluator "
            f"(supported: {SUPPORTED_MODES}; 'baseline' needs the LLM runner)"
        )

    records: list[CaseRecord] = []
    for case in cases:
        comparable = _field_from_case(case)
        extraction = _build_extraction(case.field, comparable)
        guard_rejections: list[str] = []

        if mode == "guard":
            # G2 는 ctx.contract_pages/im_pages(정수)만 사용하고 PDF 파일을 직접
            # 열지 않는다 → placeholder 경로로 충분 (결정적 평가, 파일 IO 없음).
            ctx = GuardContext(
                contract_pdf=Path("contract.pdf"),
                im_pdf=Path("im.pdf"),
                contract_pages=contract_pages,
                im_pages=im_pages,
                config=GuardConfig(g1_format=True, g2_citation=True, g3_constraint=True),
            )
            guarded, events = apply_guards(
                raw_extraction_json=extraction.model_dump_json(), ctx=ctx
            )
            if guarded is not None:
                extraction = guarded
            guard_rejections = _rejections_for_field(events, case.field)

        result = next(
            r for r in cross_check_extraction(extraction) if r.field == case.field
        )
        records.append(
            CaseRecord(
                case_id=case.case_id,
                field=case.field,
                gold_label=case.gold_label,
                difficulty=case.difficulty,
                mutation_type=case.mutation_type,
                harness_signal=case.harness_signal,
                final_status=str(result.final_status),
                final_reason_code=result.final_reason_code,
                guard_rejections=guard_rejections,
            )
        )
    return records
