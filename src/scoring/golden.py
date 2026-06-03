"""golden_master.csv 로더 (docs/GOLDENSET.md §2/§3/§8).

- 인코딩은 반드시 utf-8-sig (BOM) — Excel 친화 + 한글 보존.
- 빈 셀은 None (절대 'null'/'-' 문자열 아님).
- field 는 cross_check.FIELD_LABELS 의 14개 키만 허용.
"""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from src.pipelines.cross_check import FIELD_LABELS
from src.scoring.labels import GoldLabel

DEFAULT_GOLDEN_PATH = Path("tests/golden/golden_master.csv")

REQUIRED_COLUMNS = (
    "case_id",
    "category",
    "field",
    "label",
    "gold_label",
    "mutation_type",
    "difficulty",
    "contract_raw",
    "contract_page",
    "im_raw",
    "im_page",
    "harness_signal",
    "weak_model_pitfall",
    "note",
)


class GoldenCase(BaseModel):
    """golden_master.csv 한 행 (14컬럼)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    category: str
    field: str
    label: str
    gold_label: GoldLabel
    mutation_type: str
    difficulty: str
    contract_raw: str | None
    contract_page: int | None
    im_raw: str | None
    im_page: int | None
    harness_signal: str
    weak_model_pitfall: str
    note: str = ""


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _page(value: str | None) -> int | None:
    text = _blank_to_none(value)
    return int(text) if text is not None else None


def load_golden_master(path: Path | str = DEFAULT_GOLDEN_PATH) -> list[GoldenCase]:
    """golden_master.csv 를 읽어 GoldenCase 리스트로 반환.

    Raises:
        FileNotFoundError: 파일이 없을 때.
        ValueError: 필수 컬럼 누락 또는 field 가 14개 허용 키가 아닐 때.
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"golden master not found: {csv_path}")

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
        if missing:
            raise ValueError(f"golden master missing columns: {missing}")
        rows = list(reader)

    cases: list[GoldenCase] = []
    for index, row in enumerate(rows, start=2):  # 2 = 헤더 다음 첫 데이터 행
        field = (row["field"] or "").strip()
        if field not in FIELD_LABELS:
            raise ValueError(
                f"golden master row {index}: unknown field '{field}' "
                f"(must be one of cross_check.FIELD_LABELS)"
            )
        try:
            case = GoldenCase(
                case_id=(row["case_id"] or "").strip(),
                category=(row["category"] or "").strip(),
                field=field,
                label=(row["label"] or "").strip(),
                gold_label=GoldLabel((row["gold_label"] or "").strip()),
                mutation_type=(row["mutation_type"] or "").strip(),
                difficulty=(row["difficulty"] or "").strip(),
                contract_raw=_blank_to_none(row["contract_raw"]),
                contract_page=_page(row["contract_page"]),
                im_raw=_blank_to_none(row["im_raw"]),
                im_page=_page(row["im_page"]),
                harness_signal=(row["harness_signal"] or "").strip(),
                weak_model_pitfall=(row["weak_model_pitfall"] or "").strip(),
                note=_blank_to_none(row.get("note")) or "",
            )
        except (ValueError, TypeError) as exc:
            raise ValueError(f"golden master row {index}: {exc}") from exc
        cases.append(case)
    return cases
