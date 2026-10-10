"""Access boundary and executable notebook contracts (no Google account needed)."""

import ast
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from osintbr.lab import create_app

ORIGIN = "https://example-colab.googleusercontent.com"
TOKEN = "test-session-token-" + "x" * 32


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("OSINTBR_PROXY_ORIGIN", raising=False)
    monkeypatch.delenv("OSINTBR_COLAB_TOKEN", raising=False)
    monkeypatch.setenv("OSINTBR_DB", str(tmp_path / "cases.sqlite3"))
    monkeypatch.setenv("OSINTBR_FRONTEND", str(tmp_path / "missing"))


def proxy_client(monkeypatch):
    monkeypatch.setenv("OSINTBR_PROXY_ORIGIN", ORIGIN)
    monkeypatch.setenv("OSINTBR_COLAB_TOKEN", TOKEN)
    return TestClient(create_app(), base_url=ORIGIN)


def test_local_access_stays_local():
    client = TestClient(create_app(), base_url="http://localhost:8000")
    assert client.get("/api/brasil/cases").status_code == 200
    assert client.get("/health").json()["mode"] == "local-only"
    assert client.get("/health", headers={"Host": "attacker.test"}).status_code == 403
    assert client.post("/api/brasil/cases", headers={"Origin": "https://attacker.test"}, json={}).status_code == 403
    assert client.post("/api/brasil/cases", content="{}").status_code == 415
    assert client.get("/health", headers={"Host": "[::1]:8000"}).status_code == 200


@pytest.mark.parametrize("origin,token", [
    (ORIGIN, ""), ("", TOKEN), ("http://example.test", TOKEN),
    (ORIGIN + "/path", TOKEN), (ORIGIN + "?query", TOKEN),
    ("https://user:pass@example.test", TOKEN), (ORIGIN, "short"),
    (ORIGIN, "á" * 40), (ORIGIN + ":1234", TOKEN),
])
def test_proxy_rejects_incomplete_or_unsafe_configuration(monkeypatch, origin, token):
    monkeypatch.setenv("OSINTBR_PROXY_ORIGIN", origin)
    monkeypatch.setenv("OSINTBR_COLAB_TOKEN", token)
    with pytest.raises(ValueError):
        create_app()


def test_proxy_requires_token_on_reads_and_writes(monkeypatch):
    client = proxy_client(monkeypatch)
    assert client.get("/health").json()["mode"] == "colab-proxy"
    assert client.get("/api/brasil/cases").status_code == 401
    assert client.get("/api/brasil/sources").status_code == 401
    assert client.post("/api/brasil/cases", json={}).status_code == 401
    assert client.get("/api/brasil/cases", headers={"Authorization": "Bearer wrong"}).status_code == 401
    client.headers["Authorization"] = "Bearer " + TOKEN
    response = client.post("/api/brasil/cases", json={"title": "Colab test", "purpose": "Testar o notebook"}, headers={"Origin": ORIGIN})
    assert response.status_code == 201
    case_id = response.json()["id"]
    run = client.post(f"/api/brasil/cases/{case_id}/runs", json={"mode": "demo", "seed_kind": "cnpj", "seed": "11222333000181", "steps": ["cnpj", "cep", "municipio"]})
    assert run.status_code == 200
    export = client.get(f"/api/brasil/cases/{case_id}/export")
    assert export.status_code == 200
    assert export.headers["cache-control"] == "no-store"
    assert client.get("/api/brasil/cases", headers={"Origin": ORIGIN + ".attacker.test"}).status_code == 403
    # A proxy may keep localhost as its upstream Host header.
    assert client.get("/api/brasil/cases", headers={"Host": "127.0.0.1:34567"}).status_code == 200


def test_notebook_is_valid_python_with_no_embedded_outputs_or_credentials():
    root = Path(__file__).resolve().parents[2]
    notebook = json.loads((root / "notebooks/OsintbrFLOW_Colab.ipynb").read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    code = []
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            ast.parse(source)
            code.append(source)
            assert cell["outputs"] == []
            assert cell["execution_count"] is None
    combined = "\n".join(code)
    assert 'secrets.token_urlsafe(32)' in combined
    assert 'serve_kernel_port_as_iframe' in combined
    assert 'path=PANEL_URL' in combined
    assert 'proxyPort({PORT}, {{cache: false}})' in combined
    assert '["git", "merge", "--ff-only", "origin/main"]' in combined
    assert 'cache_in_notebook=False' in combined
    # npm ci rewrites yarn.lock; a second "Run all" must not abort on it.
    assert 'INSTALL_ARTIFACTS = ["yarn.lock"]' in combined
    assert combined.count('["git", "checkout", "--", *INSTALL_ARTIFACTS]') == 2
    assert '0.0.0.0' not in combined
    assert 'files.download' not in combined


@pytest.mark.parametrize("upstream_host", [
    "127.0.0.1:34567", "localhost:34567", "[::1]:34567",
    "internal-colab-proxy:34567", "alternate-session.colab.dev", "attacker.test",
])
def test_proxy_host_is_not_an_authentication_credential(monkeypatch, tmp_path, upstream_host):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "brasil.html").write_text("<html>OSINT Brasil Flow</html>", encoding="utf-8")
    monkeypatch.setenv("OSINTBR_FRONTEND", str(frontend))
    client = proxy_client(monkeypatch)
    client.headers["Host"] = upstream_host
    assert client.get("/brasil.html").status_code == 200
    # Public UI assets contain no cases or credentials; all case data needs a key.
    assert client.get("/api/brasil/cases").status_code == 401
    assert client.post("/api/brasil/cases", json={}).status_code == 401
    assert client.get("/api/brasil/cases", headers={"Authorization": "Bearer wrong"}).status_code == 401
    client.headers["Authorization"] = "Bearer " + TOKEN
    assert client.get("/api/brasil/cases").status_code == 200
    assert client.post("/api/brasil/cases", headers={"Origin": ORIGIN}, json={"title": "Proxy test", "purpose": "Verificar Host reescrito"}).status_code == 201
    assert client.get("/api/brasil/cases", headers={"Origin": "https://attacker.test"}).status_code == 403


@pytest.mark.parametrize("peer,expected", [
    ("127.0.0.1", 200), ("::1", 200), ("172.17.0.1", 200), ("192.168.0.10", 200),
    ("10.0.0.5", 200), ("fd00::1", 200),
    ("8.8.8.8", 403), ("200.160.2.3", 403), ("2001:4860::1", 403),
    ("::ffff:200.160.2.3", 403),
])
def test_local_mode_refuses_public_peers_even_with_spoofed_host(peer, expected):
    """The lab has no login: a public source address is refused even when
    the attacker sends Host: localhost (e.g. port published on 0.0.0.0)."""
    client = TestClient(create_app(), base_url="http://localhost:8000", client=(peer, 50000))
    assert client.get("/api/brasil/cases").status_code == expected
    assert client.get("/health").status_code == expected


def test_proxy_mode_does_not_use_peer_address(monkeypatch):
    """In Colab mode the bearer token is the gate; the proxy's address is irrelevant."""
    monkeypatch.setenv("OSINTBR_PROXY_ORIGIN", ORIGIN)
    monkeypatch.setenv("OSINTBR_COLAB_TOKEN", TOKEN)
    client = TestClient(create_app(), base_url=ORIGIN, client=("8.8.8.8", 50000))
    assert client.get("/api/brasil/cases").status_code == 401
    ok = client.get("/api/brasil/cases", headers={"Authorization": "Bearer " + TOKEN})
    assert ok.status_code == 200
