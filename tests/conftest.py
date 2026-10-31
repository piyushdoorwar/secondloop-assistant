import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def dev_employee(monkeypatch):
    """In-memory clients have no token: act as Ben."""
    monkeypatch.setenv("SECONDLOOP_ENV", "dev")
    monkeypatch.setenv("SECONDLOOP_DEV_SUBJECT", "ben")
