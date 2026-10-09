"""Deterministic bounded workflows. No probabilistic identity merges or guilt scores."""

import uuid

from .providers import Provider, SourceError, endpoint, now

RECIPES = [
    {
        "id": "empresa-territorio",
        "name": "Empresa → território",
        "seed_kind": "cnpj",
        "steps": ["cnpj", "cep", "municipio"],
        "description": "Cadastro empresarial, área postal e município oficial.",
    },
    {
        "id": "cadastro",
        "name": "Verificação cadastral",
        "seed_kind": "cnpj",
        "steps": ["cnpj"],
        "description": "Uma coleta empresarial preservada com origem e hash.",
    },
    {
        "id": "territorio",
        "name": "CEP → município",
        "seed_kind": "cep",
        "steps": ["cep", "municipio"],
        "description": "Contexto territorial sem inferir localização de pessoas.",
    },
    {
        "id": "municipio",
        "name": "Município oficial",
        "seed_kind": "municipio",
        "steps": ["municipio"],
        "description": "Confirmação do código e nome na API do IBGE.",
    },
]


def validate_recipe(seed_kind, seed, steps):
    value, _ = endpoint(seed_kind, seed)
    allowed = {
        "cnpj": [["cnpj"], ["cnpj", "cep"], ["cnpj", "cep", "municipio"]],
        "cep": [["cep"], ["cep", "municipio"]],
        "municipio": [["municipio"]],
    }
    if steps not in allowed.get(seed_kind, []):
        raise ValueError(
            "Fluxo incompatível: conecte CNPJ → CEP → município, sem ciclos."
        )
    return value


def project(evidence):
    nodes, edges = [], []
    for e in evidence:
        if e.get("status") != "ok":
            continue
        d, kind = e["data"], e["kind"]
        key = f"{kind}:{e['query']}"
        if kind == "cnpj":
            props = {
                k: d.get(k)
                for k in [
                    "cnpj",
                    "razao_social",
                    "nome_fantasia",
                    "cep",
                    "municipio",
                    "uf",
                    "descricao_situacao_cadastral",
                    "cnae_fiscal",
                    "capital_social",
                    "data_inicio_atividade",
                ]
            }
            label = d.get("razao_social") or e["query"]
        elif kind == "cep":
            props = {
                k: d.get(k)
                for k in ["cep", "logradouro", "bairro", "localidade", "uf", "ibge"]
            }
            label = f"CEP {d.get('cep', e['query'])}"
        else:
            uf = ((d.get("microrregiao") or {}).get("mesorregiao") or {}).get("UF") or (
                (
                    (d.get("regiao-imediata") or {}).get("regiao-intermediaria") or {}
                ).get("UF")
                or {}
            )
            props = {"code": str(d["id"]), "name": d["nome"], "uf": uf.get("sigla")}
            label = d["nome"]
        nodes.append(
            {
                "id": key,
                "kind": kind,
                "label": label,
                "properties": props,
                "evidence_id": e["id"],
            }
        )
        if len(nodes) > 1:
            prev = nodes[-2]
            edges.append(
                {
                    "id": f"{prev['id']}->{key}",
                    "source": prev["id"],
                    "target": key,
                    "label": "CADASTRADA_NO_CEP"
                    if kind == "cep"
                    else "CEP_NO_MUNICIPIO",
                    "evidence_id": evidence[len(nodes) - 2]["id"],
                    "epistemic_status": "source_statement",
                }
            )
    return {"nodes": nodes, "edges": edges}


def compare(previous, current):
    changes = []
    old = {n["id"]: n for n in previous["nodes"]}
    new = {n["id"]: n for n in current["nodes"]}
    for key in sorted(old.keys() | new.keys()):
        if key not in old or key not in new:
            changes.append(
                {
                    "entity": key,
                    "field": "entity",
                    "before": old.get(key),
                    "after": new.get(key),
                }
            )
            continue
        for field in sorted(
            old[key]["properties"].keys() | new[key]["properties"].keys()
        ):
            a, b = old[key]["properties"].get(field), new[key]["properties"].get(field)
            if a != b:
                changes.append({"entity": key, "field": field, "before": a, "after": b})
    return changes


async def execute(seed_kind, seed, steps, mode, provider=None):
    seed = validate_recipe(seed_kind, seed, steps)
    provider = provider or Provider()
    evidence, cursor = [], seed
    for kind in steps:
        try:
            if not cursor:
                raise SourceError(
                    "missing_input",
                    "Etapa anterior não forneceu o identificador necessário.",
                )
            item = await provider.fetch(kind, cursor, mode)
            item.update(id=str(uuid.uuid4()), status="ok")
            evidence.append(item)
            cursor = (
                item["data"].get("cep") if kind == "cnpj" else item["data"].get("ibge")
            )
        except (SourceError, ValueError) as exc:
            evidence.append(
                {
                    "id": str(uuid.uuid4()),
                    "kind": kind,
                    "query": cursor,
                    "status": getattr(exc, "status", "invalid_input"),
                    "message": str(exc),
                    "retrieved_at": now(),
                    "mode": mode,
                }
            )
            break
    graph = project(evidence)
    ok = sum(e["status"] == "ok" for e in evidence)
    return {
        "id": str(uuid.uuid4()),
        "created_at": now(),
        "seed_kind": seed_kind,
        "seed": seed,
        "steps": steps,
        "mode": mode,
        "status": "complete" if ok == len(steps) else "partial" if ok else "failed",
        "evidence": evidence,
        "graph": graph,
    }


def native_graph(run):
    """Explicit exchange into the inherited Flowsint JSON graph importer."""
    types = {
        "cnpj": "BrazilCompany",
        "cep": "BrazilCEP",
        "municipio": "BrazilMunicipality",
    }
    nodes = []
    for n in run["graph"]["nodes"]:
        e = next(e for e in run["evidence"] if e["id"] == n["evidence_id"])
        props = dict(n["properties"])
        if n["kind"] == "cnpj":
            props.update(
                name=props.get("razao_social"),
                municipality=props.get("municipio"),
                status=props.get("descricao_situacao_cadastral"),
            )
        if n["kind"] == "cep":
            props["cep"] = e["query"]
        props.update(
            source_url=e["url"],
            retrieved_at=e["retrieved_at"],
            evidence_sha256=e["sha256"],
            evidence_id=e["id"],
            collection_mode=run["mode"],
        )
        nodes.append(
            {
                "id": n["id"],
                "nodeType": types[n["kind"]],
                "nodeLabel": n["label"],
                "nodeProperties": props,
            }
        )
    return {
        "nodes": nodes,
        "edges": run["graph"]["edges"],
        "osintbrflow": {
            "run_id": run["id"],
            "mode": run["mode"],
            "chain_hash": run["chain_hash"],
        },
    }
