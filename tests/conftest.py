import os

import psycopg
import pytest

from secondloop.workflow.db import connect, migrate


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def dev_employee(monkeypatch):
    """In-memory clients have no token: act as Ben."""
    monkeypatch.setenv("SECONDLOOP_ENV", "dev")
    monkeypatch.setenv("SECONDLOOP_DEV_SUBJECT", "ben")


TEST_DB = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres@localhost:5432/secondloop_test",
)


@pytest.fixture
def db(monkeypatch):
    """A clean workflow schema in a test database."""
    try:
        conn = connect(TEST_DB)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL not available")
    conn.execute(
        "DROP TABLE IF EXISTS outbox, operations, "
        "approvals, proposals CASCADE"
    )
    migrate(conn)
    monkeypatch.setenv("DATABASE_URL", TEST_DB)
    yield conn
    conn.close()
