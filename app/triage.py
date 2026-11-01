"""Разбор падений — перезапуск упавших проверок, вердикт, причина-кандидат."""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from app.runner import ARTIFACTS_DIR, PROJECT_ROOT, RunResult, run_pytest

RERUNS = 2  # сколько раз перезапускаем упавшую проверку (всего попыток = 1 + RERUNS)
RERUN_TIMEOUT = 120
FAILED = ("failed", "error")

VERDICT_FLAKY = "flaky"
VERDICT_BUG = "bug"
VERDICT_UNKNOWN = "unknown"

VERDICT_TEXT = {
    VERDICT_FLAKY: "🔥 нестабильная",
    VERDICT_BUG: "🐞 похоже на баг",
    VERDICT_UNKNOWN: "❔ не удалось определить",
}

# Правила идут по порядку: первое совпавшее выигрывает.
CAUSE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"timeout|timed out", re.I), "таймаут: медленная сеть или страница"),
    (re.compile(r"connection|max retries|name resolution|ssl", re.I), "сервис недоступен или проблема сети"),
    (re.compile(r"assert\s+[45]\d\d\s*==", re.I), "сервер вернул код ошибки HTTP"),
    (re.compile(r"assert\s+\d+(\.\d+)?\s*<=?\s*\d+(\.\d+)?"), "превышен порог времени ответа"),
    (re.compile(r"locator|to_have|expected to have|strict mode", re.I), "UI: изменился контент или элемент не появился вовремя"),
    (re.compile(r"assert|AssertionError"), "ожидаемое и фактическое значения не совпали"),
]
CAUSE_UNKNOWN = "не определена, смотри текст ошибки и скриншот"


@dataclass
class TriageItem:
    name: str
    attempts: list[str]
    verdict: str = VERDICT_UNKNOWN
    cause: str = CAUSE_UNKNOWN
    history_failed: int = 0
    history_total: int = 0


def guess_cause(message: str) -> str:
    for pattern, cause in CAUSE_RULES:
        if pattern.search(message):
            return cause
    return CAUSE_UNKNOWN


def classify(attempts: list[str]) -> str:
    """Падала на всех попытках → баг; хотя бы раз прошла → нестабильная."""
    if len(attempts) < 2 or not any(a in FAILED for a in attempts):
        return VERDICT_UNKNOWN
    if all(a in FAILED for a in attempts):
        return VERDICT_BUG
    if "passed" in attempts:
        return VERDICT_FLAKY
    return VERDICT_UNKNOWN


def case_nodeid(name: str, root: Path = PROJECT_ROOT) -> str | None:
    """'checks.api.test_timing::test_x' -> 'checks/api/test_timing.py::test_x'."""
    classname, sep, test = name.partition("::")
    if not sep:
        return None
    parts = classname.split(".")
    for i in range(len(parts), 0, -1):
        module = root.joinpath(*parts[:i]).with_suffix(".py")
        if module.is_file():
            return "::".join([module.relative_to(root).as_posix(), *parts[i:], test])
    return None


RunFn = Callable[[list[str], Path, int], Awaitable[RunResult]]


async def triage_failures(result: RunResult, reruns: int = RERUNS, runner: RunFn = run_pytest) -> list[TriageItem]:
    items = {
        c.name: TriageItem(name=c.name, attempts=[c.outcome], cause=guess_cause(c.message))
        for c in result.cases if c.outcome in FAILED
    }
    pending = {n: node for n in items if (node := case_nodeid(n))}
    for attempt in range(1, reruns + 1):
        if not pending:
            break
        rerun = await runner(list(pending.values()), ARTIFACTS_DIR.parent / f"rerun_{attempt}", RERUN_TIMEOUT)
        if rerun.crashed:
            break
        outcomes = {c.name: c.outcome for c in rerun.cases}
        for name in list(pending):
            outcome = outcomes.get(name)
            if outcome is None:
                del pending[name]
                continue
            items[name].attempts.append(outcome)
            if outcome not in FAILED:  # уже ясно, что нестабильная
                del pending[name]
    for item in items.values():
        item.verdict = classify(item.attempts)
    return list(items.values())


def _icon(outcome: str) -> str:
    return "✅" if outcome == "passed" else "❌" if outcome in FAILED else "➖"


def format_triage(items: list[TriageItem], limit: int = 5) -> str:
    if not items:
        return ""
    lines = ["Разбор падений:"]
    for item in items[:limit]:
        lines += [
            "",
            item.name.split("::", 1)[-1],
            f"  Вердикт: {VERDICT_TEXT[item.verdict]}",
            f"  Попытки: {' '.join(_icon(a) for a in item.attempts)}",
            f"  Причина-кандидат: {item.cause}",
        ]
        if item.history_total:
            lines.append(f"  За последние {item.history_total} прогонов упала: {item.history_failed}")
    if len(items) > limit:
        lines += ["", f"…и ещё {len(items) - limit}"]
    return "\n".join(lines)


def format_flaky(items: list[dict], last_runs: int = 10) -> str:
    """Текст для /flaky: нестабильные (падение пропало при перезапуске) и стабильно падающие."""
    flaky = [i for i in items if i["flaky"] > 0]
    bugs = [i for i in items if i["flaky"] == 0 and i["bug"] > 0]
    if not flaky and not bugs:
        return f"Падений с разбором за последние {last_runs} прогонов не было."
    lines: list[str] = []
    if flaky:
        lines.append(f"🔥 Нестабильные (последние {last_runs} прогонов каждого типа):")
        for i in flaky:
            total = i["flaky"] + i["bug"]
            lines.append(f"- {i['test_name'].split('::')[-1]}: падение пропадало при перезапуске в {i['flaky']} из {total}")
    if bugs:
        if lines:
            lines.append("")
        lines.append("🐞 Стабильно падали (во всех попытках):")
        for i in bugs:
            lines.append(f"- {i['test_name'].split('::')[-1]}: случаев {i['bug']}")
    return "\n".join(lines)