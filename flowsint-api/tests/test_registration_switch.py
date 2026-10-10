"""OSINT Brasil Flow: FLOWSINT_ALLOW_REGISTRATION closes public sign-up."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from flowsint_core.core.models import Base, Profile
from flowsint_core.core.postgre_db import get_db

PAYLOAD = {"email": "new@example.com", "password": "uma-senha-longa-123"}


# Sync endpoints run in a worker thread; StaticPool shares one in-memory
# SQLite connection across threads (the shared conftest fixture does not,
# because no earlier test wrote through the HTTP client).
@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_registration_open_by_default_keeps_upstream_behaviour(
    client, db_session, monkeypatch
):
    monkeypatch.delenv("FLOWSINT_ALLOW_REGISTRATION", raising=False)
    res = client.post("/api/auth/register", json=PAYLOAD)
    assert res.status_code == 201
    assert db_session.query(Profile).count() == 1


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "on", " true "])
def test_registration_open_when_explicitly_enabled(client, monkeypatch, value):
    monkeypatch.setenv("FLOWSINT_ALLOW_REGISTRATION", value)
    assert client.post("/api/auth/register", json=PAYLOAD).status_code == 201


@pytest.mark.parametrize("value", ["false", "0", "no", "off", "", "flase", "nao"])
def test_registration_closed_returns_403_and_creates_nothing(
    client, db_session, monkeypatch, value
):
    monkeypatch.setenv("FLOWSINT_ALLOW_REGISTRATION", value)
    res = client.post("/api/auth/register", json=PAYLOAD)
    assert res.status_code == 403
    assert "desativado" in res.json()["detail"]
    assert db_session.query(Profile).count() == 0


def test_closed_registration_does_not_block_login(client, monkeypatch):
    monkeypatch.setenv("FLOWSINT_ALLOW_REGISTRATION", "true")
    assert client.post("/api/auth/register", json=PAYLOAD).status_code == 201
    monkeypatch.setenv("FLOWSINT_ALLOW_REGISTRATION", "false")
    res = client.post(
        "/api/auth/token",
        data={"username": PAYLOAD["email"], "password": PAYLOAD["password"]},
    )
    assert res.status_code == 200
    assert res.json()["access_token"]
