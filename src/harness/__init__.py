"""하네스 러너 — 3조건(baseline/ontology/guard) 실행 오케스트레이션.

docs/INTERFACES.md §4(HarnessResult) · §5(manifest.json) 구현.
"""

from src.harness.manifest import build_manifest
from src.harness.pipeline import build_harness_result, run_harness
from src.harness.result import HarnessMode, HarnessResult

__all__ = [
    "HarnessMode",
    "HarnessResult",
    "build_harness_result",
    "run_harness",
    "build_manifest",
]
