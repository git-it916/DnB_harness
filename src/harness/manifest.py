"""manifest.json 생성 (docs/INTERFACES.md §5) — 1회 실행의 모든 메타."""

from __future__ import annotations

from src.guards.base import GuardConfig

MANIFEST_SCHEMA_VERSION = "v0"


def build_manifest(
    *,
    run_id: str,
    mode: str,
    guard_config: GuardConfig,
    backend: dict,
    inputs: dict,
    started_at: str,
    ended_at: str,
    total_latency_s: float,
    llm_call_count: int,
    llm_total_tokens: int,
    cost_usd: float = 0.0,
    golden_version: str = "v0.1",
) -> dict:
    """실행 메타를 INTERFACES §5 manifest.json 스키마로 조립."""
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "mode": mode,
        "guards": {
            "g1_format": guard_config.g1_format,
            "g2_citation": guard_config.g2_citation,
            "g3_constraint": guard_config.g3_constraint,
        },
        "backend": backend,
        "inputs": inputs,
        "golden_version": golden_version,
        "started_at": started_at,
        "ended_at": ended_at,
        "total_latency_s": round(total_latency_s, 3),
        "llm_call_count": llm_call_count,
        "llm_total_tokens": llm_total_tokens,
        "cost_usd": round(cost_usd, 6),
    }
