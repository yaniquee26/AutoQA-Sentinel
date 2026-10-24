import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.runner import RunResult

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


def get_flaky(last_runs: int = 10, db_path: Path = DB_PATH) -> list[dict]:
    query = """
        SELECT test_name,
               SUM(outcome = 'passed') AS passed,
               SUM(outcome IN ('failed', 'error')) AS failed
        FROM case_results
        WHERE run_id IN (SELECT id FROM runs ORDER BY id DESC LIMIT ?)
        GROUP BY test_name
        HAVING passed > 0 AND failed > 0
        ORDER BY failed DESC
    """
    with _connect(db_path) as conn:
        return [dict(row) for row in conn.execute(query, (last_runs,))]