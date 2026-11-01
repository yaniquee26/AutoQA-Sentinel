from app.runner import CaseResult, RunResult
from app.storage import get_flaky_verdicts, get_recent_runs, init_db, save_run, save_triage
from app.triage import TriageItem


def make_result(outcome: str) -> RunResult:
    failed = 1 if outcome == "failed" else 0
    return RunResult(
        total=2,
        passed=2 - failed,
        failed=failed,
        cases=[
            CaseResult("suite::always_ok", "passed"),
            CaseResult("suite::sometimes_bad", outcome),
        ],
    )


def triage_item(verdict: str) -> TriageItem:
    attempts = ["failed", "passed"] if verdict == "flaky" else ["failed", "failed", "failed"]
    return TriageItem("suite::sometimes_bad", attempts, verdict, "причина")


def test_save_and_read_last_run(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)

    run_id = save_run("checks/api", make_result("passed"), db)

    runs = get_recent_runs(5, db)
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["total"] == 2


def test_flaky_verdicts_count_failures_that_vanished_on_rerun(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)

    for verdict in ("flaky", "flaky", "bug"):
        run_id = save_run("checks/api", make_result("failed"), db)
        save_triage(run_id, [triage_item(verdict)], db)

    assert get_flaky_verdicts(10, db) == [{"test_name": "suite::sometimes_bad", "flaky": 2, "bug": 1}]


def test_changed_test_is_a_bug_not_flaky(tmp_path):
    """Проверка прошла, потом её изменили и она стабильно падает: это не нестабильность."""
    db = tmp_path / "test.db"
    init_db(db)

    save_run("checks/api", make_result("passed"), db)
    run_id = save_run("checks/api", make_result("failed"), db)
    save_triage(run_id, [triage_item("bug")], db)

    assert get_flaky_verdicts(10, db) == [{"test_name": "suite::sometimes_bad", "flaky": 0, "bug": 1}]


def test_window_is_counted_per_target(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)

    run_id = save_run("checks/api", make_result("failed"), db)
    save_triage(run_id, [triage_item("flaky")], db)
    save_run("checks/ui", make_result("passed"), db)  # прогон UI не вытесняет историю API

    assert [i["test_name"] for i in get_flaky_verdicts(1, db)] == ["suite::sometimes_bad"]


def test_old_triage_leaves_the_window(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)

    run_id = save_run("checks/api", make_result("failed"), db)
    save_triage(run_id, [triage_item("flaky")], db)
    save_run("checks/api", make_result("passed"), db)

    assert get_flaky_verdicts(1, db) == []


def test_no_triage_means_empty_list(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    save_run("checks/api", make_result("failed"), db)

    assert get_flaky_verdicts(10, db) == []