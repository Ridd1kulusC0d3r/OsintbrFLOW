import asyncio
import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from osintbr.api import build_router
from osintbr.engine import execute, native_graph, project, validate_recipe
from osintbr.providers import Provider, SourceError
from osintbr.store import Store, verify

from flowsint_types.brazil import (
    BrazilCEP,
    BrazilCompany,
    normalize_cep,
    normalize_cnpj,
)


@pytest.mark.parametrize(
    "value", ["11222333000181", "11.222.333/0001-81", "12.ABC.345/01DE-35"]
)
def test_cnpj_numeric_and_receita_alpha_example(value):
    assert len(normalize_cnpj(value)) == 14
    assert BrazilCompany(cnpj=value).cnpj == normalize_cnpj(value)


@pytest.mark.parametrize(
    "value",
    [
        "00000000000000",
        "11111111111111",
        "11222333000182",
        "12.ABC.345/01DE-36",
        "https://localhost",
        "11222333000181?x",
    ],
)
def test_reject_bad_cnpj(value):
    with pytest.raises(ValueError):
        normalize_cnpj(value)


@pytest.mark.parametrize("value", ["30130-010", "30130010"])
def test_cep(value):
    assert normalize_cep(value) == "30130010"
    assert BrazilCEP(cep=value).nodeLabel == "CEP 30130-010"


@pytest.mark.parametrize(
    "steps",
    [["cnpj", "cnpj"], ["municipio", "cnpj"], ["cnpj", "municipio"], ["cnpj"] * 100],
)
def test_no_cycle_or_incompatible_pipeline(steps):
    with pytest.raises(ValueError):
        validate_recipe("cnpj", "11222333000181", steps)


async def demo():
    return await execute("cnpj", "11222333000181", ["cnpj", "cep", "municipio"], "demo")


@pytest.mark.asyncio
async def test_demo_does_not_call_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("network")

    monkeypatch.setattr(httpx.AsyncClient, "stream", fail)
    r = await demo()
    assert r["status"] == "complete" and len(r["graph"]["edges"]) == 2
    assert all(e["url"].startswith("demo://") for e in r["evidence"])
    assert r["graph"]["nodes"][0]["id"] == "cnpj:11222333000181"


@pytest.mark.asyncio
async def test_exact_raw_bytes_and_real_contract():
    raw = b'{"cep":"30130-010","ibge":"3106200"}\n'
    e = await Provider(
        httpx.MockTransport(lambda req: httpx.Response(200, content=raw))
    ).fetch("cep", "30130010")
    assert e["sha256"] == hashlib.sha256(raw).hexdigest()
    assert e["raw"].endswith("\n") and e["mode"] == "live"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,status",
    [
        (httpx.Response(404), "not_found"),
        (httpx.Response(200, json={"erro": True}), "not_found"),
        (httpx.Response(200, json={"cep": "99999-999"}), "schema_error"),
        (httpx.Response(200, text="not json"), "error"),
        (httpx.Response(302, headers={"location": "http://127.0.0.1"}), "error"),
        (httpx.Response(200, content=b" " * 2_000_001), "error"),
    ],
)
async def test_failure_semantics_and_redirect_block(response, status):
    with pytest.raises(SourceError) as error:
        await Provider(httpx.MockTransport(lambda req: response)).fetch(
            "cep", "30130010"
        )
    assert error.value.status == status


@pytest.mark.asyncio
async def test_retry_is_bounded():
    requests = []

    def respond(req):
        requests.append(req)
        return httpx.Response(429)

    with pytest.raises(SourceError):
        await Provider(httpx.MockTransport(respond)).fetch("cep", "30130010")
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_partial_is_not_absence(tmp_path):
    store = Store(str(tmp_path / "db"))
    case = store.create("alice", "Test", "Test purpose")
    store.append("alice", case["id"], await demo())

    class Partial(Provider):
        async def fetch(self, kind, value, mode):
            if kind == "cep":
                raise SourceError("unavailable", "timeout")
            return await super().fetch(kind, value, mode)

    r = store.append(
        "alice",
        case["id"],
        await execute(
            "cnpj", "11222333000181", ["cnpj", "cep", "municipio"], "demo", Partial()
        ),
    )
    assert r["status"] == "partial" and r["changes"] == [] and r["baseline_id"] is None


@pytest.mark.asyncio
async def test_diff_integrity_tamper_and_restart(tmp_path):
    store = Store(str(tmp_path / "db"))
    case = store.create("alice", "Test", "Test purpose")
    r1 = store.append("alice", case["id"], await demo())
    r2 = await demo()
    r2["evidence"][0]["data"]["capital_social"] = 200000
    r2["evidence"][0]["raw"] = json.dumps(r2["evidence"][0]["data"])
    r2["evidence"][0]["sha256"] = hashlib.sha256(
        r2["evidence"][0]["raw"].encode()
    ).hexdigest()
    r2["graph"] = project(r2["evidence"])
    r2 = store.append("alice", case["id"], r2)
    assert (
        r2["baseline_id"] == r1["id"] and r2["changes"][0]["field"] == "capital_social"
    )
    bundle = Store(str(tmp_path / "db")).export("alice", case["id"])
    assert verify(bundle)["valid"]
    altered = copy.deepcopy(bundle)
    altered["runs"][0]["evidence"][0]["raw"] = "tampered"
    assert not verify(altered)["valid"]
    altered = copy.deepcopy(bundle)
    altered["runs"].reverse()
    assert not verify(altered)["valid"]
    with pytest.raises(KeyError):
        store.export("bob", case["id"])


@pytest.mark.asyncio
async def test_native_graph_identifiers_and_evidence():
    run = await demo()
    run["chain_hash"] = "test"
    graph = native_graph(run)
    assert graph["nodes"][0]["nodeType"] == "BrazilCompany"
    assert (
        BrazilCompany.model_validate(graph["nodes"][0]["nodeProperties"]).cnpj
        == "11222333000181"
    )
    assert (
        graph["nodes"][0]["nodeProperties"]["evidence_sha256"]
        == run["evidence"][0]["sha256"]
    )


def test_concurrent_append_preserves_chain(tmp_path):
    store = Store(str(tmp_path / "db"))
    case = store.create("alice", "Test", "Test purpose")

    def append(_):
        return store.append("alice", case["id"], asyncio.run(demo()))

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(append, range(8)))
    assert verify(store.export("alice", case["id"]))["valid"]


def test_api_isolation_execution_export_and_validation(tmp_path):
    store = Store(str(tmp_path / "db"))
    app = FastAPI()

    def owner(x_owner: str = Header("alice")):
        return x_owner

    app.include_router(build_router(owner, store), prefix="/api/brasil")
    with TestClient(app) as c:
        case = c.post(
            "/api/brasil/cases",
            json={"title": "Caso API", "purpose": "Validar comportamento"},
        ).json()
        path = "/api/brasil/cases/" + case["id"]
        assert c.get(path, headers={"x-owner": "bob"}).status_code == 404
        assert (
            c.post(
                path + "/runs",
                headers={"x-owner": "bob"},
                json={"seed": "11222333000181", "steps": ["cnpj"], "mode": "demo"},
            ).status_code
            == 404
        )
        assert (
            c.post(
                path + "/runs", json={"seed": "bad", "steps": ["cnpj"], "mode": "live"}
            ).status_code
            == 422
        )
        r = c.post(
            path + "/runs",
            json={
                "seed": "11222333000181",
                "steps": ["cnpj", "cep", "municipio"],
                "mode": "demo",
            },
        )
        assert r.status_code == 200 and r.json()["status"] == "complete"
        bundle = c.get(path + "/export").json()
        assert c.post("/api/brasil/verify", json=bundle).json()["valid"]
        assert (
            c.get(path + "/graph/" + r.json()["id"]).json()["nodes"][0]["nodeType"]
            == "BrazilCompany"
        )
        assert len(c.get("/api/brasil/sources").json()) > 1000
        assert c.post("/api/brasil/verify", json=[]).status_code == 422


# Synthetic, publicly documented test CPF. Real CPFs never belong in fixtures.
SYNTHETIC_CPF = ["52998224725", "529.982.247-25"]


@pytest.mark.parametrize("seed", SYNTHETIC_CPF)
@pytest.mark.parametrize(
    "kind,steps",
    [("cnpj", ["cnpj"]), ("cep", ["cep"]), ("municipio", ["municipio"])],
)
@pytest.mark.parametrize("mode", ["live", "demo"])
def test_person_identifier_is_refused_before_any_request(tmp_path, seed, kind, steps, mode):
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, json={})

    app = FastAPI()
    store = Store(tmp_path / "cases.sqlite3")
    provider = Provider(httpx.MockTransport(handler))
    app.include_router(build_router(lambda: "u", store, provider), prefix="/api")
    client = TestClient(app)
    case = client.post("/api/cases", json={"title": "CPF", "purpose": "Recusar pessoa física"}).json()
    response = client.post(
        f"/api/cases/{case['id']}/runs",
        json={"seed_kind": kind, "seed": seed, "steps": steps, "mode": mode},
    )
    assert response.status_code == 422
    assert "CPF" in response.json()["detail"]
    # The identifier is neither sent to a source, echoed back nor stored.
    assert calls == []
    assert seed.replace(".", "").replace("-", "")[:9] not in response.text
    assert client.get(f"/api/cases/{case['id']}").json()["runs"] == []
