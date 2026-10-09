"""Bounded, fixed-origin public-source clients with explicit failure semantics."""

import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone

import httpx

from flowsint_types.brazil import normalize_cep, normalize_cnpj

VERSION = "0.1.0"
MAX_BYTES = 2_000_000


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


class SourceError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


PERSON_ID_MESSAGE = (
    "Isto parece um CPF (11 dígitos). O OSINT Brasil Flow não consulta "
    "pessoas físicas: use CNPJ, CEP ou código IBGE de município."
)


def looks_like_cpf(value):
    """True for 11 digits with optional CPF punctuation. The value is never echoed."""
    return bool(re.fullmatch(r"[0-9]{3}\.?[0-9]{3}\.?[0-9]{3}-?[0-9]{2}", str(value).strip()))


def endpoint(kind, value):
    # Refuse person identifiers before any normalization or network call.
    if looks_like_cpf(value):
        raise ValueError(PERSON_ID_MESSAGE)
    if kind == "cnpj":
        value = normalize_cnpj(value)
        return value, f"https://brasilapi.com.br/api/cnpj/v1/{value}"
    if kind == "cep":
        value = normalize_cep(value)
        return value, f"https://viacep.com.br/ws/{value}/json/"
    if kind == "municipio" and re.fullmatch(r"[0-9]{7}", str(value)):
        return str(
            value
        ), f"https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{value}"
    raise ValueError("Tipo ou código de município inválido.")


class Provider:
    def __init__(self, transport=None):
        self.transport = transport

    async def fetch(self, kind, value, mode="live"):
        value, url = endpoint(kind, value)
        if mode == "demo":
            fixtures = {
                "cnpj": {
                    "cnpj": "11222333000181",
                    "razao_social": "AURORA PESQUISA LTDA · FICTÍCIA",
                    "cep": "30130010",
                    "municipio": "BELO HORIZONTE",
                    "uf": "MG",
                    "descricao_situacao_cadastral": "ATIVA",
                    "cnae_fiscal": 6201501,
                    "capital_social": 100000,
                },
                "cep": {
                    "cep": "30130-010",
                    "logradouro": "Avenida de demonstração",
                    "bairro": "Centro",
                    "localidade": "Belo Horizonte",
                    "uf": "MG",
                    "ibge": "3106200",
                },
                "municipio": {
                    "id": 3106200,
                    "nome": "Belo Horizonte",
                    "microrregiao": {
                        "mesorregiao": {"UF": {"sigla": "MG", "nome": "Minas Gerais"}}
                    },
                },
            }
            expected = {
                "cnpj": "11222333000181",
                "cep": "30130010",
                "municipio": "3106200",
            }
            if value != expected[kind]:
                raise ValueError(
                    "O laboratório aceita somente a semente fictícia indicada."
                )
            raw = canonical(fixtures[kind])
            data = fixtures[kind]
            url = f"demo://{kind}/{value}"
        elif mode == "live":
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15),
                follow_redirects=False,
                transport=self.transport,
                trust_env=True,
            ) as client:
                for attempt in range(2):
                    try:
                        async with client.stream(
                            "GET",
                            url,
                            headers={
                                "User-Agent": f"OsintbrFLOW/{VERSION}",
                                "Accept": "application/json",
                            },
                        ) as response:
                            if (
                                response.status_code == 429
                                or response.status_code >= 500
                            ):
                                if attempt == 0:
                                    await asyncio.sleep(0.25)
                                    continue
                                raise SourceError(
                                    "unavailable",
                                    f"Fonte indisponível (HTTP {response.status_code}).",
                                )
                            if response.status_code == 404:
                                raise SourceError(
                                    "not_found",
                                    "Registro não retornado pela fonte; não prova inexistência.",
                                )
                            if response.status_code != 200:
                                raise SourceError(
                                    "error",
                                    f"Fonte respondeu HTTP {response.status_code}.",
                                )
                            chunks, size = [], 0
                            async for chunk in response.aiter_bytes():
                                size += len(chunk)
                                if size > MAX_BYTES:
                                    raise SourceError(
                                        "error", "Resposta excede limite de 2 MB."
                                    )
                                chunks.append(chunk)
                            raw = b"".join(chunks).decode("utf-8")
                        data = json.loads(raw)
                        break
                    except httpx.RequestError as exc:
                        raise SourceError(
                            "unavailable", "Falha de rede ou timeout da fonte."
                        ) from exc
                    except (ValueError, UnicodeError) as exc:
                        raise SourceError(
                            "error", "Fonte retornou conteúdo JSON inválido."
                        ) from exc
        else:
            raise ValueError("Modo inválido.")
        if not isinstance(data, dict) or data.get("erro"):
            raise SourceError(
                "not_found", "A fonte não retornou um registro utilizável."
            )
        if kind == "municipio" and not isinstance(data.get("nome"), str):
            raise SourceError("schema_error", "Resposta do IBGE sem nome do município.")
        # Identity mismatches must never contaminate a case or become a false relationship.
        try:
            actual = {
                "cnpj": lambda: normalize_cnpj(data.get("cnpj", "")),
                "cep": lambda: normalize_cep(data.get("cep", "")),
                "municipio": lambda: str(data.get("id", "")),
            }[kind]()
        except ValueError as exc:
            raise SourceError(
                "schema_error", "Resposta sem identificador válido."
            ) from exc
        if actual != value:
            raise SourceError(
                "schema_error", "Identificador retornado difere do solicitado."
            )
        return {
            "kind": kind,
            "query": value,
            "url": url,
            "retrieved_at": now(),
            "raw": raw,
            "sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "data": data,
            "mode": mode,
            "connector_version": VERSION,
        }
