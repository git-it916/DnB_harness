"""SQLite-backed, explicitly approved alias pairs for operational reviews."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ALIAS_FIELDS = {
    "fund.name",
    "party.asset_manager",
    "party.trustee",
    "party.distributor",
}


def normalize_alias_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(ch for ch in normalized if ch.isalnum())


def _fund_series(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", value)
    return set(re.findall(r"(?:제\s*)?(\d+)\s*호", normalized))


class AliasRegistry:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def matches(self, field: str, left: str | None, right: str | None) -> bool:
        if field not in ALIAS_FIELDS or not left or not right:
            return False
        left_norm, right_norm = _ordered_pair(left, right)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM aliases
                WHERE field = ? AND left_norm = ? AND right_norm = ? AND status = 'approved'
                """,
                (field, left_norm, right_norm),
            ).fetchone()
        return row is not None

    def remember(
        self,
        *,
        field: str,
        left: str,
        right: str,
        source_run_id: str,
    ) -> None:
        if field not in ALIAS_FIELDS:
            raise ValueError(f"aliases are not supported for field: {field}")
        if field == "fund.name":
            left_series, right_series = _fund_series(left), _fund_series(right)
            if left_series and right_series and left_series != right_series:
                raise ValueError("conflicting fund series numbers cannot be stored as aliases")
        left_norm, right_norm = _ordered_pair(left, right)
        if left_norm == right_norm:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO aliases(
                    field, left_norm, right_norm, left_raw, right_raw,
                    source_run_id, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'approved', ?)
                ON CONFLICT(field, left_norm, right_norm)
                DO UPDATE SET status = 'approved', source_run_id = excluded.source_run_id
                """,
                (field, left_norm, right_norm, left, right, source_run_id, now),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def _ordered_pair(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((normalize_alias_text(left), normalize_alias_text(right))))  # type: ignore[return-value]
