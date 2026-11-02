import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.runner import RunResult
from app.triage import TriageItem

DB_PATH = Path(__file__).resolve().parent.parent / "sentinel.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    target TEXT NOT NULL,
    total INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    failed INTEGER NOT NULL,
    errors INTEGER NOT NULL,
    duration REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS case_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    test_name TEXT NOT NULL,
    outcome TEXT NOT NULL,
    message TEXT
);
CREATE TABLE IF NOT EXISTS triage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    test_name TEXT NOT NULL,
    verdict TEXT NOT NULL,
    cause TEXT,
    attempts TEXT NOT NULL
);
"""


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def save_run(target: str, result: RunResult, db_path: Path = DB_PATH) -> int:
    created_at = datetime.now().isoformat(timespec="seconds")
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO runs (created_at, target, total, passed, failed, errors, duration) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (created_at, target, result.total, result.passed,
             result.failed, result.errors, result.duration),
        )
        run_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO case_results (run_id, test_name, outcome, message) VALUES (?, ?, ?, ?)",
            [(run_id, c.name, c.outcome, c.message) for c in result.cases],
        )
    return run_id


def get_recent_runs(limit: int = 5, db_path: Path = DB_PATH) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in rows]


def get_flaky_verdicts(last_runs: int = 10, db_path: Path = DB_PATH) -> list[dict]:
    """Итоги разбора падений за последние last_runs прогонов каждого target.

    flaky: сколько раз падение исчезло при перезапуске;
    bug: сколько раз проверка упала во всех попытках.
    """
    query = """
        SELECT t.test_name,
               SUM(t.verdict = 'flaky') AS flaky,
               SUM(t.verdict = 'bug') AS bug
        FROM triage t
        WHERE t.run_id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY target ORDER BY id DESC) AS rn
                FROM runs
            ) WHERE rn <= ?
        )
        GROUP BY t.test_name
        HAVING flaky > 0 OR bug > 0
        ORDER BY flaky DESC, bug DESC, t.test_name
    """
    with _connect(db_path) as conn:
        return [dict(row) for row in conn.execute(query, (last_runs,))]


def save_triage(run_id: int, items: list[TriageItem], db_path: Path = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.executemany(
            "INSERT INTO triage (run_id, test_name, verdict, cause, attempts) VALUES (?, ?, ?, ?, ?)",
            [(run_id, i.name, i.verdict, i.cause, ",".join(i.attempts)) for i in items],
        )


def get_fail_rate(test_name: str, target: str, last_runs: int = 10, db_path: Path = DB_PATH) -> tuple[int, int]:
    """(упала раз, всего раз) за последние last_runs прогонов этого target."""
    query = """
        SELECT COUNT(*) AS total,
               COALESCE(SUM(outcome IN ('failed', 'error')), 0) AS failed
        FROM case_results
        WHERE test_name = ?
          AND run_id IN (SELECT id FROM runs WHERE target = ? ORDER BY id DESC LIMIT ?)
    """
    with _connect(db_path) as conn:
        row = conn.execute(query, (test_name, target, last_runs)).fetchone()
    return int(row["failed"]), int(row["total"])


def get_last_triage(db_path: Path = DB_PATH) -> list[dict]:
    """Результаты разбора последнего прогона, в котором были падения (с текстом ошибки)."""
    query = """
        SELECT t.test_name, t.verdict, t.cause, t.attempts, r.target, c.message
        FROM triage t
        JOIN runs r ON r.id = t.run_id
        LEFT JOIN case_results c ON c.run_id = t.run_id AND c.test_name = t.test_name
        WHERE t.run_id = (SELECT MAX(run_id) FROM triage)
        ORDER BY t.id
    """
    with _connect(db_path) as conn:
        return [dict(row) for row in conn.execute(query)]
