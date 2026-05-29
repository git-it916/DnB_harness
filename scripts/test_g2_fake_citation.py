"""골든셋 C029 (fake_citation) 시뮬레이션 — G2 가드가 페이지 999를 잡는지 확인.

기존 extraction.json 을 base 로:
1. fund.name.im.citation.page 를 999 로 변조 (C029)
2. fund.name.im.citation.document 를 "신탁계약서" 로 변조 (라벨 mismatch)
3. 한쪽만 잘 잡는지 G2 결과 확인
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.guards.base import GuardConfig, GuardContext  # noqa: E402
from src.guards.g2_citation import check_citations  # noqa: E402
from src.schemas.extraction import ExtractionResult  # noqa: E402

BASE = PROJECT_ROOT / "database" / "gemma4" / "run_01_seed42" / "extraction.json"


def main() -> int:
    if not BASE.exists():
        print(f"[FAIL] 베이스 추출 없음: {BASE}")
        return 1
    raw = json.loads(BASE.read_text(encoding="utf-8"))

    # ===== 변조 1: page=999 (C029 fake_citation) =====
    raw["fund"]["name"]["im"]["citation"]["page"] = 999

    # ===== 변조 2: side와 document 라벨 불일치 =====
    # party.asset_manager.contract.citation.document 를 "IM" 으로 (실제는 contract 측)
    if raw["party"]["asset_manager"]["contract"]["citation"] is not None:
        raw["party"]["asset_manager"]["contract"]["citation"]["document"] = "IM"

    # Pydantic 재검증 — DocumentValue 의 require_citation_for_evidence 통과해야 함
    extraction = ExtractionResult.model_validate(raw)

    ctx = GuardContext(
        contract_pdf=Path("dummy_contract.pdf"),
        im_pdf=Path("dummy_im.pdf"),
        contract_pages=22,
        im_pages=32,
        config=GuardConfig(g1_format=False, g2_citation=True, g3_constraint=False),
    )

    guarded, events = check_citations(extraction, ctx)

    print("=" * 70)
    print("G2 시뮬레이션 결과")
    print("=" * 70)

    rejects = [ev for ev in events if ev.decision.value == "reject"]
    passes = [ev for ev in events if ev.decision.value == "pass"]
    print(f"\n총 G2 이벤트: {len(events)} (pass={len(passes)}, reject={len(rejects)})")

    print("\n--- REJECT 이벤트 ---")
    for ev in rejects:
        print(f"  {ev.field_path}")
        print(f"    reason_code: {ev.reason_code}")
        print(f"    reason: {ev.reason}")
        print(f"    metadata: {ev.metadata}")

    # 검증
    expected_rejects = {
        ("fund.name.im", "page_out_of_range"),
        ("party.asset_manager.contract", "citation_document_mismatch"),
    }
    actual_rejects = {(ev.field_path, ev.reason_code) for ev in rejects}

    print("\n--- 검증 ---")
    if expected_rejects.issubset(actual_rejects):
        print("[PASS] 예상 reject 모두 발생")
    else:
        missing = expected_rejects - actual_rejects
        print(f"[FAIL] 누락: {missing}")
        return 1

    # 변조된 필드가 null화 됐는지
    print("\n--- 변조 필드 null화 확인 ---")
    fund_name_im = guarded.fund.name.im
    asset_mgr_c = guarded.party.asset_manager.contract
    print(f"  fund.name.im.raw_text after G2: {fund_name_im.raw_text!r}")
    print(f"  party.asset_manager.contract.raw_text after G2: {asset_mgr_c.raw_text!r}")
    if fund_name_im.raw_text is None and asset_mgr_c.raw_text is None:
        print("[PASS] 두 필드 모두 null화됨")
    else:
        print("[FAIL] null화 안 됨")
        return 1

    print("\n" + "=" * 70)
    print("G2 가드 골든셋 C029 시뮬레이션 — 전부 통과")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
