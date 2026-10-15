import json
import subprocess
import sys
from pathlib import Path

from tests.conftest import ROOT


def _run(args: list[str], env: dict[str, str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "lead_pipeline", *args],
        cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )


def test_generate_then_run_end_to_end(tmp_path: Path, project_env: dict[str, str]) -> None:
    sample = tmp_path / "sample.jsonl"
    labels = tmp_path / "labels.jsonl"
    gen = _run(["generate", "--n", "12", "--seed", "1", "--out", str(sample), "--labels", str(labels)], project_env)
    assert gen.returncode == 0, gen.stderr
    assert sum(1 for _ in sample.open(encoding="utf-8")) == 12

    out_dir = tmp_path / "out"
    run = _run(["run", "--input", str(sample), "--out", str(out_dir), "--provider", "fake", "--no-notify"], project_env)
    assert run.returncode == 0, run.stderr
    assert "Итого: 12 заявок, обработано 12, ошибок 0" in run.stdout
    assert (out_dir / "leads.csv").exists() and (out_dir / "leads.xlsx").exists()
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["total"] == 12 and summary["ok"] == 12


def test_eval_and_prompts_commands(project_env: dict[str, str]) -> None:
    ev = _run(["eval", "--provider", "fake"], project_env)
    assert ev.returncode == 0, ev.stderr
    assert "Золотой набор: 30 примеров" in ev.stdout
    assert "Матрица ошибок" in ev.stdout

    prompts = _run(["prompts"], project_env)
    assert prompts.returncode == 0
    assert "v1" in prompts.stdout and "v2" in prompts.stdout
