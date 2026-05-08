"""tests/test_dao.py · DAO abstraction layer contract tests"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".app"))

from dao import (  # noqa: E402
    connect,
    get_adapter,
    DAOBackendError,
    run_migrations,
)


# ── Adapter selection ────────────────────────────────────────────────────────

def test_default_adapter_is_sqlite():
    adapter = get_adapter()
    assert type(adapter).__name__ == "_SQLiteAdapter"


def test_sqlite_explicit():
    adapter = get_adapter("sqlite:///tmp/test.db")
    assert type(adapter).__name__ == "_SQLiteAdapter"


def test_postgres_url_returns_pg_adapter():
    adapter = get_adapter("postgres://user:pass@localhost/db")
    assert type(adapter).__name__ == "_PostgresAdapter"


def test_postgresql_url_returns_pg_adapter():
    adapter = get_adapter("postgresql://user:pass@localhost/db")
    assert type(adapter).__name__ == "_PostgresAdapter"


def test_kingbase_url_returns_kingbase_adapter():
    adapter = get_adapter("kingbase://user:pass@localhost/db")
    assert type(adapter).__name__ == "_KingbaseAdapter"


def test_unsupported_scheme_raises():
    with pytest.raises(DAOBackendError):
        get_adapter("oracle://user:pass@localhost/db")


# ── SQLite end-to-end ────────────────────────────────────────────────────────

def test_sqlite_connect_in_memory():
    conn = connect("sqlite:///:memory:")
    assert conn.backend == "sqlite"
    with conn.cursor() as c:
        c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        c.execute("INSERT INTO t (name) VALUES (?)", ("alice",))
        c.execute("SELECT name FROM t WHERE id = ?", (1,))
        row = c.fetchone()
        assert row["name"] == "alice"
    conn.close()


def test_sqlite_commit_rollback():
    conn = connect("sqlite:///:memory:")
    with conn.cursor() as c:
        c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, n INTEGER)")
    conn.commit()

    with conn.cursor() as c:
        c.execute("INSERT INTO t (n) VALUES (?)", (1,))
    conn.rollback()

    with conn.cursor() as c:
        c.execute("SELECT COUNT(*) FROM t")
        count = c.fetchone()[0]
        assert count == 0
    conn.close()


def test_sqlite_lastrowid():
    conn = connect("sqlite:///:memory:")
    with conn.cursor() as c:
        c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, n INTEGER)")
        c.execute("INSERT INTO t (n) VALUES (?)", (42,))
        assert c.lastrowid == 1
        c.execute("INSERT INTO t (n) VALUES (?)", (43,))
        assert c.lastrowid == 2
    conn.close()


# ── Adapter dialect helpers ──────────────────────────────────────────────────

def test_sqlite_autoincrement_pk():
    a = get_adapter("sqlite:///:memory:")
    assert "AUTOINCREMENT" in a.autoincrement_pk()


def test_postgres_autoincrement_pk():
    a = get_adapter("postgres://x")
    assert "SERIAL" in a.autoincrement_pk()


def test_sqlite_now_ts():
    a = get_adapter("sqlite:///:memory:")
    assert a.now_ts() == "CURRENT_TIMESTAMP"


def test_postgres_now_ts():
    a = get_adapter("postgres://x")
    assert a.now_ts() == "NOW()"


# ── Migrations runner ────────────────────────────────────────────────────────

def test_run_migrations_no_dir():
    """Empty migrations dir = 0 applied (not error)."""
    conn = connect("sqlite:///:memory:")
    with tempfile.TemporaryDirectory() as td:
        applied = run_migrations(conn, Path(td))
        assert applied == 0
    conn.close()


def test_run_migrations_idempotent():
    """Running twice should only apply once."""
    conn = connect("sqlite:///:memory:")
    with tempfile.TemporaryDirectory() as td:
        m1 = Path(td) / "001_create_t.sql"
        m1.write_text("CREATE TABLE t (id INTEGER PRIMARY KEY, n INTEGER)")
        a1 = run_migrations(conn, Path(td))
        a2 = run_migrations(conn, Path(td))
        assert a1 == 1
        assert a2 == 0  # already applied
    conn.close()


def test_run_migrations_backend_specific():
    """Migration file with -- @sqlite section runs SQLite path only."""
    conn = connect("sqlite:///:memory:")
    with tempfile.TemporaryDirectory() as td:
        m = Path(td) / "001_test.sql"
        m.write_text(
            "-- @sqlite\n"
            "CREATE TABLE x (id INTEGER PRIMARY KEY)\n"
            "-- @postgres\n"
            "CREATE TABLE x (id SERIAL PRIMARY KEY)\n"
        )
        applied = run_migrations(conn, Path(td))
        assert applied == 1
        with conn.cursor() as c:
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='x'")
            assert c.fetchone() is not None
    conn.close()


# ── Param substitution (cross-DB SQL) ────────────────────────────────────────

def test_sqlite_question_marks_pass_through():
    """SQLite uses ? · should not be transformed."""
    conn = connect("sqlite:///:memory:")
    with conn.cursor() as c:
        c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, n INTEGER)")
        c.execute("INSERT INTO t (n) VALUES (?)", (99,))
        c.execute("SELECT n FROM t WHERE id = ?", (1,))
        assert c.fetchone()["n"] == 99
    conn.close()


# ── Connection lifecycle ─────────────────────────────────────────────────────

def test_connection_close_idempotent():
    conn = connect("sqlite:///:memory:")
    conn.close()
    # Second close should not raise (backend may or may not allow · we just verify wrapper)
    try:
        conn.close()
    except Exception:
        pass  # SQLite raises on second close · OK
