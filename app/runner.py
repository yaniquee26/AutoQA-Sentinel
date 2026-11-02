import asyncio
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "last_run"

SECRET_NAMES = {"BOT_TOKEN", "ALLOWED_USER_ID", "LLM_API_KEY"}


def clean_env() -> dict:
    return {k: v for k, v in os.environ.items() if k not in SECRET_NAMES}


@dataclass
class CaseResult:
    name: str
    outcome: str  # passed / failed / error / skipped
    message: str = ""


@dataclass
class RunResult:
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration: float = 0.0
    cases: list[CaseResult] = field(default_factory=list)
    screenshots: list[Path] = field(default_factory=list)
    traces: list[Path] = field(default_factory=list)
    crashed: bool = False
    crash_message: str = ""

    @property
    def failures(self) -> list[str]:
        return [f"{c.name}: {c.message}" for c in self.cases if c.outcome in ("failed", "error")]


def parse_junit(xml_path: Path) -> RunResult:
    root = ET.parse(xml_path).getroot()
    result = RunResult()
    for suite in root.iter("testsuite"):
        result.total += int(suite.get("tests", 0))
        result.failed += int(suite.get("failures", 0))
        result.errors += int(suite.get("errors", 0))
        result.skipped += int(suite.get("skipped", 0))
        result.duration += float(suite.get("time", 0))
    result.passed = result.total - result.failed - result.errors - result.skipped
    for case in root.iter("testcase"):
        name = f"{case.get('classname')}::{case.get('name')}"
        outcome, message = "passed", ""
        for tag, label in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
            node = case.find(tag)
            if node is not None:
                outcome = label
                lines = (node.get("message") or "").splitlines()
                message = lines[0][:150] if lines else ""
                break
        result.cases.append(CaseResult(name, outcome, message))
    return result


def collect_artifacts(out_dir: Path, limit: int = 3) -> tuple[list[Path], list[Path]]:
    """Скриншоты (*.png) и trace Playwright (trace.zip) упавших проверок."""
    return (
        sorted(out_dir.rglob("*.png"))[:limit],
        sorted(out_dir.rglob("trace.zip"))[:limit],
    )


async def run_pytest(targets: list[str], out_dir: Path, timeout: int = 120) -> RunResult:
    """Один запуск pytest в чистом окружении; out_dir очищается и получает скриншоты."""
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        xml_path = Path(tmp) / "report.xml"
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pytest", *targets,
            f"--junitxml={xml_path}", "-q", "--tb=short",
            "--screenshot", "only-on-failure",
            "--tracing", "retain-on-failure",
            "--output", str(out_dir),
            cwd=PROJECT_ROOT,
            env=clean_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return RunResult(crashed=True, crash_message=f"Прогон не уложился в {timeout} с")
        if not xml_path.exists():
            tail = output.decode(errors="replace")[-500:]
            return RunResult(crashed=True, crash_message=tail)
        result = parse_junit(xml_path)
        result.screenshots, result.traces = collect_artifacts(out_dir)
        return result


async def run_checks(target: str = "checks/api", timeout: int = 120) -> RunResult:
    return await run_pytest([target], ARTIFACTS_DIR, timeout)


def format_report(result: RunResult) -> str:
    if result.crashed:
        return f"Прогон не удался:\n{result.crash_message}"
    if result.total == 0:
        return "Проверки не найдены."
    ok = result.failed == 0 and result.errors == 0
    lines = [
        "✅ Все проверки прошли" if ok else "❌ Есть падения",
        f"Всего: {result.total}, прошло: {result.passed}, "
        f"упало: {result.failed}, ошибок: {result.errors}, пропущено: {result.skipped}",
        f"Время: {result.duration:.1f} с",
    ]
    if result.failures:
        lines.append("")
        lines.append("Упавшие проверки:")
        for item in result.failures[:10]:
            lines.append(f"- {item}")
    return "\n".join(lines)