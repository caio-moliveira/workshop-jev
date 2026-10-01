"""Execuções concluídas, uma por linha em runs/runs.jsonl, e relatórios de lote em
runs/batches/<batch_id>.json (PRD 7.1)."""

import json
from pathlib import Path

from pydantic import BaseModel

from app.graph import RunResult

RUNS_DIR = Path(__file__).resolve().parents[2] / "runs"


class RunStore:
    def __init__(self, runs_dir: Path = RUNS_DIR):
        self.path = runs_dir / "runs.jsonl"
        self.batches_dir = runs_dir / "batches"

    def save_run(self, result: RunResult, batch_id: str | None = None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = result.model_dump(mode="json") | {"batch_id": batch_id}
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")

    def get_run(self, run_id: str) -> RunResult | None:
        for line in self._lines(f'"run_id":"{run_id}"'):
            return RunResult.model_validate_json(line)
        return None

    def runs_for_batch(self, batch_id: str) -> list[RunResult]:
        return [
            RunResult.model_validate_json(line) for line in self._lines(f'"batch_id":"{batch_id}"')
        ]

    def save_report(self, report: BaseModel, batch_id: str) -> None:
        path = self.batches_dir / f"{batch_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    def load_report(self, batch_id: str) -> str | None:
        path = self.batches_dir / f"{batch_id}.json"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def _lines(self, needle: str):
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as file:
            yield from (line for line in file if needle in line)
