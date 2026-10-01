"""Execuções concluídas, uma por linha em runs/runs.jsonl (PRD 7.1)."""

from pathlib import Path

from app.graph import RunResult

RUNS_DIR = Path(__file__).resolve().parents[2] / "runs"


class RunStore:
    def __init__(self, runs_dir: Path = RUNS_DIR):
        self.path = runs_dir / "runs.jsonl"

    def save_run(self, result: RunResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(result.model_dump_json() + "\n")

    def get_run(self, run_id: str) -> RunResult | None:
        if not self.path.exists():
            return None
        with self.path.open(encoding="utf-8") as file:
            for line in file:
                if f'"run_id":"{run_id}"' in line:
                    return RunResult.model_validate_json(line)
        return None
