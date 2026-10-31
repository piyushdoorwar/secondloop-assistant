"""PostgreSQL connections for workflow state."""

import os
import pathlib

import psycopg
from psycopg.rows import dict_row

SCHEMA = (
    pathlib.Path(__file__).parents[3] / "db/schema.sql"
)
DEFAULT_URL = (
    "postgresql://postgres@localhost:5432/secondloop"
)


def connect(url=None) -> psycopg.Connection:
    return psycopg.connect(
        url
        or os.environ.get("DATABASE_URL", DEFAULT_URL),
        row_factory=dict_row,
    )


def migrate(conn) -> None:
    conn.execute(SCHEMA.read_text())
    conn.commit()
