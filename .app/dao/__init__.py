"""
ome365.dao · Database Abstraction Layer (v0.1)

Single goal: make Ome365 portable across SQLite (default OSS) → PostgreSQL
(Enterprise PG+RLS) → KingbaseES / 达梦 (信创·v1.0.x).

v3.6 §11.3 line 587 (信创 DAO 抽象 v3.5 P1) + §13.2 line 668 (信创替换 SOP).

Status: v0.1 stub · interface only · SQLite default impl wired ·
        PG impl in D+1 ~ D+3 (PG+RLS Ome365 启用 · v3.6 §10 2.4 line 532) ·
        KingbaseES impl on customer demand (v1.0.x · 1 week to switch).

Design rules:
  1. Never import sqlite3 / psycopg2 / dmPython directly in callers.
     Always go through Connection / Cursor abstractions in this package.
  2. SQL dialect differences (e.g. AUTOINCREMENT vs SERIAL) handled by
     adapter classes · never branched in business logic.
  3. Connection pooling is adapter-internal · callers see synchronous
     `with conn.cursor() as c:` API.
  4. Migrations live in `dao/migrations/` · numbered + idempotent.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Any


class DAOBackendError(Exception):
    """Raised when DAO backend setup or query fails."""


class Cursor:
    """Generic cursor wrapper · same interface across backends."""
    def __init__(self, raw_cursor: Any, backend: str):
        self._raw = raw_cursor
        self._backend = backend

    def execute(self, sql: str, params: tuple = ()) -> "Cursor":
        # Translate SQLite ? → PostgreSQL %s for cross-DB SQL
        if self._backend == "postgres" and "?" in sql:
            sql = sql.replace("?", "%s")
        self._raw.execute(sql, params)
        return self

    def executemany(self, sql: str, seq_of_params: list) -> "Cursor":
        if self._backend == "postgres" and "?" in sql:
            sql = sql.replace("?", "%s")
        self._raw.executemany(sql, seq_of_params)
        return self

    def fetchone(self) -> Optional[tuple]:
        return self._raw.fetchone()

    def fetchall(self) -> list:
        return self._raw.fetchall()

    @property
    def lastrowid(self) -> Optional[int]:
        return getattr(self._raw, "lastrowid", None)

    def close(self):
        self._raw.close()


class Connection:
    """Generic connection wrapper · same `with conn.cursor()` semantics."""
    def __init__(self, raw_conn: Any, backend: str):
        self._raw = raw_conn
        self._backend = backend
        self._lock = threading.Lock()

    @contextmanager
    def cursor(self) -> Iterator[Cursor]:
        with self._lock:
            cur = self._raw.cursor()
            try:
                yield Cursor(cur, self._backend)
            finally:
                cur.close()

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()

    @property
    def backend(self) -> str:
        return self._backend


class _SQLiteAdapter:
    """SQLite adapter (default · OSS · v0.1 ships with this)."""

    def connect(self, dsn: str) -> Connection:
        # dsn = "sqlite:///path/to/db.sqlite" or "sqlite:///:memory:"
        if dsn.startswith("sqlite:///"):
            path = dsn[len("sqlite:///"):]
        else:
            path = dsn
        # Python 3.6 sqlite3 needs str (not PosixPath)
        conn = sqlite3.connect(str(path), check_same_thread=False, timeout=5.0)
        conn.row_factory = sqlite3.Row
        # Enforce foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        # Reasonable performance defaults
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return Connection(conn, "sqlite")

    def autoincrement_pk(self) -> str:
        """Returns SQL fragment for auto-increment primary key."""
        return "INTEGER PRIMARY KEY AUTOINCREMENT"

    def now_ts(self) -> str:
        """Returns SQL expression for current timestamp."""
        return "CURRENT_TIMESTAMP"


class _PostgresAdapter:
    """PostgreSQL adapter (Enterprise · D+1 ~ D+3 alpha · imports ome-server schema)."""

    def connect(self, dsn: str) -> Connection:
        # dsn = "postgres://user:pass@host:5432/dbname"
        try:
            import psycopg2
        except ImportError:
            raise DAOBackendError(
                "psycopg2 not installed · run `pip install psycopg2-binary` "
                "or use SQLite backend (DATABASE_URL=sqlite:///...)"
            )
        try:
            conn = psycopg2.connect(dsn)
            conn.autocommit = False
            return Connection(conn, "postgres")
        except Exception as e:
            raise DAOBackendError(f"PostgreSQL connect failed: {e}")

    def autoincrement_pk(self) -> str:
        return "SERIAL PRIMARY KEY"

    def now_ts(self) -> str:
        return "NOW()"


class _KingbaseAdapter:
    """KingbaseES adapter (信创 · v1.0.x · activated by customer demand).

    Strategy: KingbaseES is PostgreSQL-compatible so we extend _PostgresAdapter.
    The dmPython driver is needed if 达梦 (DM8) is the target instead.
    """

    def connect(self, dsn: str) -> Connection:
        try:
            import psycopg2
        except ImportError:
            raise DAOBackendError(
                "psycopg2 not installed · KingbaseES uses PostgreSQL-compatible driver. "
                "Run `pip install psycopg2-binary`."
            )
        # KingbaseES dsn format same as PG. Connection params may differ slightly.
        try:
            conn = psycopg2.connect(dsn)
            conn.autocommit = False
            return Connection(conn, "kingbase")
        except Exception as e:
            raise DAOBackendError(f"KingbaseES connect failed: {e}")

    def autoincrement_pk(self) -> str:
        return "SERIAL PRIMARY KEY"

    def now_ts(self) -> str:
        return "NOW()"


# ── Public API ────────────────────────────────────────────────────────────────

def get_adapter(database_url: Optional[str] = None):
    """
    Returns adapter for the given DATABASE_URL.

    Default (no URL set): SQLite (file in $OME365_HOME/db.sqlite or :memory:).

    Examples:
      DATABASE_URL=sqlite:///var/lib/ome365/db.sqlite     → SQLite
      DATABASE_URL=postgres://user:pass@localhost/ome365  → PostgreSQL
      DATABASE_URL=kingbase://user:pass@localhost/ome365  → KingbaseES (信创)
    """
    url = database_url or os.environ.get("DATABASE_URL", "")
    if not url or url.startswith("sqlite"):
        return _SQLiteAdapter()
    if url.startswith("postgres") or url.startswith("postgresql"):
        return _PostgresAdapter()
    if url.startswith("kingbase") or url.startswith("dm:"):
        return _KingbaseAdapter()
    raise DAOBackendError(f"Unsupported DATABASE_URL scheme: {url[:20]!r}")


def connect(database_url: Optional[str] = None) -> Connection:
    """Convenience: get adapter + connect in one call."""
    adapter = get_adapter(database_url)
    url = database_url or os.environ.get("DATABASE_URL", "")
    if not url:
        # Default: SQLite in $OME365_HOME/db.sqlite (or :memory: for tests)
        home = Path(os.environ.get("OME365_HOME", Path.home() / ".ome365"))
        home.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{home / 'db.sqlite'}"
    return adapter.connect(url)


# ── Migrations runner (v0.1 stub) ─────────────────────────────────────────────

def run_migrations(conn: Connection, migrations_dir: Optional[Path] = None) -> int:
    """
    Apply numbered migrations from `dao/migrations/`.
    Each migration file: NNN_name.sql with backend-prefixed sections:
      -- @sqlite ...
      -- @postgres ...
      -- @kingbase ...
    Returns: number of migrations applied.

    v0.1 stub · D+1~D+3 alpha will populate migrations/ for PG schema import.
    """
    migrations_dir = migrations_dir or Path(__file__).parent / "migrations"
    if not migrations_dir.is_dir():
        return 0

    # Track applied migrations
    with conn.cursor() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            f"  id {get_adapter().autoincrement_pk()},"
            "   name TEXT NOT NULL UNIQUE,"
            f"  applied_at TIMESTAMP DEFAULT {get_adapter().now_ts()}"
            ")"
        )
    conn.commit()

    applied = 0
    for f in sorted(migrations_dir.glob("*.sql")):
        with conn.cursor() as c:
            c.execute("SELECT 1 FROM schema_migrations WHERE name = ?", (f.name,))
            if c.fetchone():
                continue
        sql = f.read_text("utf-8")
        # Extract backend-specific section
        section = _extract_section(sql, conn.backend)
        with conn.cursor() as c:
            for stmt in _split_sql(section):
                c.execute(stmt)
            c.execute("INSERT INTO schema_migrations (name) VALUES (?)", (f.name,))
        conn.commit()
        applied += 1
    return applied


def _extract_section(sql: str, backend: str) -> str:
    """Extract `-- @<backend>` section · or whole file if no markers."""
    marker = f"-- @{backend}"
    if marker not in sql:
        return sql
    parts = sql.split("-- @")
    for p in parts:
        if p.startswith(backend):
            # strip backend tag line
            return p.split("\n", 1)[1] if "\n" in p else ""
    return ""


def _split_sql(sql: str) -> list[str]:
    """Naive split on `;` · OK for migration files (no procedures)."""
    return [s.strip() for s in sql.split(";") if s.strip()]


__all__ = [
    "Connection",
    "Cursor",
    "DAOBackendError",
    "get_adapter",
    "connect",
    "run_migrations",
]
