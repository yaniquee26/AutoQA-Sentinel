from app.runner import CaseResult, RunResult, clean_env, collect_artifacts, format_report, parse_junit

XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="0" tests="3" time="1.5">
    <testcase classname="checks.api.test_a" name="test_ok" time="0.1"/>
    <testcase classname="checks.api.test_a" name="test_ok_too" time="0.1"/>
    <testcase classname="checks.api.test_a" name="test_bad" time="0.1">
      <failure message="assert 404 == 200">trace</failure>
    </testcase>
  </testsuite>
</testsuites>
"""


def test_clean_env_removes_secrets_and_keeps_the_rest(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "secret")
    monkeypatch.setenv("ALLOWED_USER_ID", "42")
    monkeypatch.setenv("SOME_SETTING", "keep")

    env = clean_env()

    assert "BOT_TOKEN" not in env
    assert "ALLOWED_USER_ID" not in env
    assert env["SOME_SETTING"] == "keep"


def test_parse_junit_counts_and_failures(tmp_path):
    xml_file = tmp_path / "report.xml"
    xml_file.write_text(XML, encoding="utf-8")

    result = parse_junit(xml_file)

    assert result.total == 3
    assert result.passed == 2
    assert result.failed == 1
    assert result.failures == ["checks.api.test_a::test_bad: assert 404 == 200"]


def test_format_report_for_failed_run():
    result = RunResult(
        total=2,
        passed=1,
        failed=1,
        duration=1.0,
        cases=[CaseResult("suite::bad", "failed", "boom")],
    )

    text = format_report(result)

    assert "Есть падения" in text
    assert "suite::bad: boom" in text


def test_collect_artifacts_finds_screenshots_and_traces(tmp_path):
    test_dir = tmp_path / "checks-ui-test-x-chromium"
    test_dir.mkdir()
    (test_dir / "test-failed-1.png").write_bytes(b"png")
    (test_dir / "trace.zip").write_bytes(b"zip")
    (test_dir / "notes.txt").write_text("ignore me")

    screenshots, traces = collect_artifacts(tmp_path)

    assert [p.name for p in screenshots] == ["test-failed-1.png"]
    assert [p.name for p in traces] == ["trace.zip"]


def test_collect_artifacts_respects_limit(tmp_path):
    for i in range(5):
        folder = tmp_path / f"case{i}"
        folder.mkdir()
        (folder / "trace.zip").write_bytes(b"zip")

    _, traces = collect_artifacts(tmp_path, limit=3)

    assert len(traces) == 3