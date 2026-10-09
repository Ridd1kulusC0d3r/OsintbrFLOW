"""Optional native-integration tests; require inherited core runtime dependencies."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("AUTH_SECRET", "test-only-not-a-deployment-secret")
pytest.importorskip("celery")
from osintbr.engine import execute, native_graph
from osintbr.providers import Provider

from flowsint_core.imports.json.parse_json import parse_json
from flowsint_enrichers.brazil.company import (
    BrazilCEPToMunicipality,
    BrazilCompanyLookup,
    BrazilCompanyToCEP,
)
from flowsint_types.brazil import BrazilCompany


@pytest.mark.asyncio
async def test_native_enrichers_and_graph_import():
    original = Provider.fetch

    async def fake(self, kind, value, mode="live"):
        return await original(self, kind, value, "demo")

    with patch.object(Provider, "fetch", fake):
        graph = MagicMock()
        data = [BrazilCompany(cnpj="11222333000181")]
        for cls in [BrazilCompanyLookup, BrazilCompanyToCEP, BrazilCEPToMunicipality]:
            obj = cls(graph_service=graph)
            out = await obj.scan(data)
            obj.postprocess(out, data)
            data = out
        assert data[0].code == "3106200"
        assert graph.create_node_from_flowsint_type.call_count == 3
        assert graph.create_relationship.call_count == 2
    r = await execute("cnpj", "11222333000181", ["cnpj", "cep", "municipio"], "demo")
    r["chain_hash"] = "example"
    parsed = parse_json(json.dumps(native_graph(r)).encode(), 100)
    assert len(parsed.entities) == 3 and len(parsed.edges) == 2
