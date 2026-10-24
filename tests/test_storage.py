from app.runner import CaseResult, RunResult
from app.storage import get_flaky, get_recent_runs, init_db, save_run


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


def test_save_and_read_last_run(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)

    run_id = save_run("checks/api", make_result("passed"), db)

    runs = get_recent_runs(5, db)
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["total"] == 2


def test_flaky_detects_mixed_outcomes(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)

    save_run("checks/api", make_result("passed"), db)
    save_run("checks/api", make_result("failed"), db)

    flaky = get_flaky(10, db)
    names = [item["test_name"] for item in flaky]
    assert names == ["suite::sometimes_bad"]


def test_stable_failure_is_not_flaky(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)

    save_run("checks/api", make_result("failed"), db)
    save_run("checks/api", make_result("failed"), db)

    assert get_flaky(10, db) == []