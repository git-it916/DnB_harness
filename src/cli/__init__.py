"""DnB Harness 명령줄 인터페이스 (Typer).

실행:
    python -m src.cli --help
    python -m src.cli score --mode guard --out reports/scoring/score_guard.json
    python -m src.cli compare reports/scoring/score_*.json --out reports/compare.md
    python -m src.cli run --seeds 42 --with-normalize
"""

from src.cli.main import app

__all__ = ["app"]
