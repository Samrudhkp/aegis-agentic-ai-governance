"""Dataset loading helpers."""

from __future__ import annotations

from pathlib import Path

import yaml

from aegis.models import AttackType, EvalCase, ExpectedBehavior

ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = ROOT / "configs" / "eval_datasets"


def load_dataset(name: str) -> list[EvalCase]:
    path = DATASETS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    raw = yaml.safe_load(path.read_text())
    cases: list[EvalCase] = []
    for item in raw.get("cases", []):
        expected = ExpectedBehavior(**(item.get("expected") or {}))
        attack = item.get("attack_type") or AttackType.NONE
        cases.append(
            EvalCase(
                id=item["id"],
                category=item["category"],
                prompt=item["prompt"],
                expected=expected,
                rubrics=item.get("rubrics") or {},
                attack_type=AttackType(attack) if not isinstance(attack, AttackType) else attack,
            )
        )
    return cases


def load_thresholds(path: Path) -> dict:
    return yaml.safe_load(path.read_text())
