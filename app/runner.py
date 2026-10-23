import asyncio
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class RunResult:
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration: float = 0.0
    failures: list[str] = field(default_factory=list)
    crashed: bool = False
    crash_message: str = ""


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
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is not None:
            name = f"{case.get('classname')}::{case.get('name')}"
            lines = (problem.get("message") or "").splitlines()
            message = lines[0][:150] if lines else ""
            result.failures.append(f"{name}: {message}")
    return result


async def run_checks(target: str = "checks/api", timeout: int = 120) -> RunResult:
    with tempfile.TemporaryDirectory() as tmp:
        xml_path = Path(tmp) / "report.xml"
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pytest", target,
            f"--junitxml={xml_path}", "-q", "--tb=short",
            cwd=PROJECT_ROOT,
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
        return parse_junit(xml_path)


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