"""CLI integration tests — --week threading and render/LLM isolation."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.orchestrator import RunStats


def test_week_override_threads_to_orchestrator(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path
) -> None:
    """--week 2026-W19 flows through the CLI to orchestrator.run_all."""
    captured: dict[str, str] = {}

    def _fake_run_all(week_id: str, **kwargs) -> RunStats:
        captured["week_id"] = week_id
        return RunStats(week_id=week_id, out_path=Path("out/digest-2026-W19.html"))

    monkeypatch.setattr("pipeline.orchestrator.run_all", _fake_run_all)

    from pipeline.run import main

    rc = main(["all", "--week", "2026-W19"])
    assert rc == 0
    assert captured["week_id"] == "2026-W19"


def test_bare_cli_aliases_all_with_week(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path
) -> None:
    """Bare python -m pipeline.run --week aliases all (D-19)."""
    captured: dict[str, str] = {}

    def _fake_run_all(week_id: str, **kwargs) -> RunStats:
        captured["week_id"] = week_id
        return RunStats(week_id=week_id)

    monkeypatch.setattr("pipeline.orchestrator.run_all", _fake_run_all)

    from pipeline.run import main

    rc = main(["--week", "2026-W19"])
    assert rc == 0
    assert captured["week_id"] == "2026-W19"


def test_render_does_not_call_llm(
    monkeypatch: pytest.MonkeyPatch, apply_schema: Path, tmp_path: Path
) -> None:
    """Render subcommand must not invoke summarize / LLM (D-20)."""
    def _summarize_must_not_run(*_args, **_kwargs):
        raise AssertionError("summarize must not run during render")

    monkeypatch.setattr(
        "pipeline.orchestrator._summarize_week_items",
        _summarize_must_not_run,
    )
    monkeypatch.setattr(
        "pipeline.orchestrator.run_render",
        lambda week_id, **kw: RunStats(
            week_id=week_id,
            out_path=tmp_path / f"digest-{week_id}.html",
        ),
    )

    from pipeline.run import main

    rc = main(["render", "--week", "2026-W19"])
    assert rc == 0


def test_render_import_does_not_load_adapters_or_llm() -> None:
    """Importing run_render in a fresh process must not pull adapters or LLM."""
    import subprocess
    import sys

    script = """
import sys
for name in list(sys.modules):
    if name.startswith("pipeline.") or name.startswith("google"):
        del sys.modules[name]
from pipeline.orchestrator import run_render  # noqa: F401
loaded = [
    m for m in sys.modules
    if m.startswith("pipeline.adapters")
    or m.startswith("pipeline.llm")
    or m.startswith("google.genai")
]
if loaded:
    raise SystemExit(f"unexpected imports: {loaded}")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 0, result.stderr or result.stdout
