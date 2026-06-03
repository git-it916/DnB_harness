from __future__ import annotations

from pathlib import Path

import yaml

from src.canonical.types import FieldPolicy

DEFAULT_POLICY_PATH = Path("ontology/field_policies.yaml")


def load_field_policies(path: Path = DEFAULT_POLICY_PATH) -> dict[str, FieldPolicy]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"field policy file must contain a mapping: {path}")
    return {
        str(field): FieldPolicy.model_validate(payload)
        for field, payload in data.items()
    }
