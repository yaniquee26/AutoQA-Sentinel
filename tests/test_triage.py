import asyncio
from pathlib import Path

import pytest

from app import triage
from app.runner import CaseResult, RunResult
from app.storage import get_fail_rate, init_db, save_run, save_triage
from app.triage import (
    VERDICT_BUG, VERDICT_FLAKY, VERDICT_UNKNOWN,
    TriageItem, case_nodeid, classify, format_triage, guess_cause, triage_failures,
)


@pytest.mark.parametrize("attempts, expected", [
    (["failed", "failed", "failed"], VERDICT_BUG),
    (["failed", "passed"], VERDICT_FLAKY),
    (["error", "failed", "passed"], VERDICT_FLAKY),
    (["failed"], VERDICT_UNKNOWN),          # перезапуск не удался
    (["failed", "skipped"], VERDICT_UNKNOWN),
])
def test_classify(attempts, expected):
    assert classify(attempts) == expected


@pytest.mark.parametrize("message, fragment", [
    ("assert 0.490978 < 0.3", "порог времени"),
    ("assert 500 == 200", "код ошибки HTTP"),
    ("requests.exceptions.ConnectionError: Max retries exceeded", "недоступен"),
    ("Locator expected to have count '7'", "UI"),
    ("AssertionError: boom", "не совпали"),
])
def test_guess_cause(message, fragment):
    assert fragment in guess_cause(message)


def test_guess_cause_unknown():
    assert "не определена" in guess_cause("что-то странное")


def test_case_nodeid(tmp_path: Path):
    (tmp_path / "checks" / "ui").mkdir(parents=True)
    (tmp_path / "checks" / "ui" / "test_inventory.py").write_text("")
    name = "checks.ui.test_inventory::test_shows_six[chromium]"
    assert case_nodeid(name, tmp_path) == "checks/ui/test_inventory.py::test_shows_six[chromium]"
    assert case_nodeid("checks.ui.test_inventory.TestCart::test_x", tmp_path) == \
        "checks/ui/test_inventory.py::TestCart::test_x"
    assert case_nodeid("nope.module::test_x", tmp_path) is None


def _result(*cases: tuple[str, str, str]) -> RunResult:
    return RunResult(total=len(cases), cases=[CaseResult(*c) for c in cases])


def test_triage_flaky_then_stop_rerunning(monkeypatch):
    monkeypatch.setattr(triage, "case_nodeid", lambda name: name.split("::")[-1])
    calls: list[list[str]] = []

    async def fake_runner(nodeids, out_dir, timeout):
        calls.append(nodeids)
        # test_a проходит со второй попытки, test_b падает всегда
        return _result(("m::test_a", "passed", ""), ("m::test_b", "failed", "assert 500 == 200"))

    first = _result(("m::test_a", "failed", "assert 0.49 < 0.3"), ("m::test_b", "failed", "assert 500 == 200"), ("m::test_c", "passed", ""))
    items = {i.name: i for i in asyncio.run(triage_failures(first, reruns=2, runner=fake_runner))}

    assert items["m::test_a"].verdict == VERDICT_FLAKY
    assert items["m::test_a"].attempts == ["failed", "passed"]
    assert items["m::test_b"].verdict == VERDICT_BUG
    assert items["m::test_b"].attempts == ["failed", "failed", "failed"]
    assert "m::test_c" not in items
    assert calls == [["test_a", "test_b"], ["test_b"]]  # прошедшую больше не гоняем


def test_triage_runner_crash_gives_unknown(monkeypatch):
    monkeypatch.setattr(triage, "case_nodeid", lambda name: "x")

    async def crashing_runner(nodeids, out_dir, timeout):
        return RunResult(crashed=True, crash_message="boom")

    first = _result(("m::test_a", "failed", "assert 1 == 2"))
    [item] = asyncio.run(triage_failures(first, runner=crashing_runner))
    assert item.verdict == VERDICT_UNKNOWN


def test_format_triage():
    item = TriageItem("m::test_a", ["failed", "passed"], VERDICT_FLAKY, "превышен порог времени ответа", 4, 10)
    text = format_triage([item])
    assert "test_a" in text and "нестабильная" in text and "❌ ✅" in text and "упала: 4" in text
    assert format_triage([]) == ""


def test_save_triage_and_fail_rate(tmp_path: Path):
    db = tmp_path / "t.db"
    init_db(db)
    for outcome in ("failed", "passed", "failed"):
        run_id = save_run("checks/api", _result(("m::test_a", outcome, "")), db)
    save_triage(run_id, [TriageItem("m::test_a", ["failed", "passed"], VERDICT_FLAKY, "x")], db)
    assert get_fail_rate("m::test_a", "checks/api", 10, db) == (2, 3)
    assert get_fail_rate("m::test_a", "checks/ui", 10, db) == (0, 0)