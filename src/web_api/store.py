"""Durable local state for review runs, decisions, and approved aliases."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.application.review_models import HumanDecisionView, ReviewResult, summarize_fields


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    def __init__(self, database_path: Path, runs_root: Path):
        self.database_path = database_path
        self.runs_root = runs_root
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create_run(
        self,
        *,
        run_id: str,
        strategy: str,
        model: str,
        contract_name: str,
        im_name: str,
    ) -> dict[str, Any]:
        now = utc_now()
        run_dir = self.runs_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "input").mkdir()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs(
                    id, status, stage, strategy, model, contract_name, im_name,
                    run_dir, created_at, updated_at
                ) VALUES (?, 'queued', 'queued', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    strategy,
                    model,
                    contract_name,
                    im_name,
                    str(run_dir),
                    now,
                    now,
                ),
            )
        return self.get_run(run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return dict(row)

    def set_progress(self, run_id: str, *, status: str = "running", stage: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status = ?, stage = ?, updated_at = ? WHERE id = ?",
                (status, stage, utc_now(), run_id),
            )

    def complete(self, run_id: str, result: ReviewResult) -> None:
        run = self.get_run(run_id)
        result_path = Path(run["run_dir"]) / "review_result.json"
        result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        (Path(run["run_dir"]) / "abox.ttl").write_text(result.abox_ttl, encoding="utf-8")
        (Path(run["run_dir"]) / "shacl_report.txt").write_text(
            result.shacl_report_text, encoding="utf-8"
        )
        status = "awaiting_review" if result.summary.needs_human_review else "completed"
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs SET status = ?, stage = 'complete', result_path = ?,
                    updated_at = ?, error = NULL WHERE id = ?
                """,
                (status, str(result_path), utc_now(), run_id),
            )

    def fail(self, run_id: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs SET status = 'failed', stage = 'failed', error = ?, updated_at = ?
                WHERE id = ?
                """,
                (error[:1000], utc_now(), run_id),
            )

    def load_result(self, run_id: str) -> ReviewResult | None:
        run = self.get_run(run_id)
        if not run.get("result_path"):
            return None
        result = ReviewResult.model_validate_json(
            Path(run["result_path"]).read_text(encoding="utf-8")
        )
        decisions = self.decisions_for_run(run_id)
        if not decisions:
            return result
        fields = []
        for field in result.fields:
            decision = decisions.get(field.field)
            if decision is None:
                fields.append(field)
                continue
            if decision["decision"] == "same":
                effective, requires_review = "match", False
            elif decision["decision"] == "different":
                effective, requires_review = "mismatch", False
            else:
                effective, requires_review = "needs_human_review", True
            fields.append(
                field.model_copy(
                    update={
                        "effective_status": effective,
                        "resolution_source": "human",
                        "requires_human_review": requires_review,
                        "human_decision": HumanDecisionView.model_validate(decision),
                    }
                )
            )
        return result.model_copy(
            update={"fields": fields, "summary": summarize_fields(fields)}
        )

    def save_decision(
        self,
        *,
        run_id: str,
        field: str,
        decision: str,
        note: str,
        remember_alias: bool,
    ) -> dict[str, Any]:
        if decision not in ("same", "different", "unknown"):
            raise ValueError(f"unsupported decision: {decision}")
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO human_decisions(
                    run_id, field, decision, note, remember_alias, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, field) DO UPDATE SET
                    decision = excluded.decision,
                    note = excluded.note,
                    remember_alias = excluded.remember_alias,
                    decided_at = excluded.decided_at
                """,
                (run_id, field, decision, note, int(remember_alias), now),
            )
        return {
            "decision": decision,
            "note": note,
            "remember_alias": remember_alias,
            "decided_at": now,
        }

    def decisions_for_run(self, run_id: str) -> dict[str, dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM human_decisions WHERE run_id = ?", (run_id,)
            ).fetchall()
        return {
            row["field"]: {
                "decision": row["decision"],
                "note": row["note"],
                "remember_alias": bool(row["remember_alias"]),
                "decided_at": row["decided_at"],
            }
            for row in rows
        }

    def refresh_review_status(self, run_id: str) -> None:
        result = self.load_result(run_id)
        if result is None:
            return
        status = "awaiting_review" if result.summary.needs_human_review else "reviewed"
        self.set_progress(run_id, status=status, stage="complete")

    def input_path(self, run_id: str, role: str) -> Path:
        if role not in ("contract", "im"):
            raise ValueError(role)
        return Path(self.get_run(run_id)["run_dir"]) / "input" / f"{role}.pdf"

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs(
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    model TEXT NOT NULL,
                    contract_name TEXT NOT NULL,
                    im_name TEXT NOT NULL,
                    run_dir TEXT NOT NULL,
                    result_path TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS human_decisions(
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    field TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    remember_alias INTEGER NOT NULL DEFAULT 0,
                    decided_at TEXT NOT NULL,
                    PRIMARY KEY(run_id, field)
                );

                CREATE TABLE IF NOT EXISTS aliases(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field TEXT NOT NULL,
                    left_norm TEXT NOT NULL,
                    right_norm TEXT NOT NULL,
                    left_raw TEXT NOT NULL,
                    right_raw TEXT NOT NULL,
                    source_run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(field, left_norm, right_norm)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
