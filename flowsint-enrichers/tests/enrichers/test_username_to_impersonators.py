from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tools.social import sosia

from flowsint_enrichers import ENRICHER_REGISTRY
from flowsint_enrichers.social.to_impersonators import UsernameToImpersonatorsEnricher
from flowsint_types import SocialAccount, Username

RAIZ = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Registro e metadados
# ---------------------------------------------------------------------------
def test_registrado():
    enricher = ENRICHER_REGISTRY.get_enricher("username_to_impersonators", "s", "s")
    assert enricher.name() == "username_to_impersonators"


def test_metadados():
    assert UsernameToImpersonatorsEnricher.category() == "social"
    assert UsernameToImpersonatorsEnricher.key() == "username"
    assert UsernameToImpersonatorsEnricher.input_schema()["type"] == "Username"
    assert UsernameToImpersonatorsEnricher.output_schema()["type"] == "SocialAccount"
    nomes = {p["name"] for p in UsernameToImpersonatorsEnricher.get_params_schema()}
    assert nomes == {
        "max_variantes",
        "risco_minimo",
        "ler_perfil",
        "oficiais",
        "plataformas",
        "modo",
    }


def test_biblioteca_igual_a_ferramenta_autonoma():
    """tools/social é cópia da ferramenta em ferramentas/sosia: não podem divergir."""
    for nome in (
        "sosia.py",
        "sites_padrao.json",
        "sites_extra.json",
        "demo/caso_demo.json",
    ):
        copia = RAIZ / "flowsint-enrichers/src/tools/social" / nome
        fonte = RAIZ / "ferramentas/sosia" / nome
        assert copia.read_bytes() == fonte.read_bytes(), (
            f"{nome} divergiu; copie de ferramentas/sosia"
        )


# ---------------------------------------------------------------------------
# Varredura no caso demo (sem internet)
# ---------------------------------------------------------------------------
async def _rodar(params):
    grafo = MagicMock()
    enricher = UsernameToImpersonatorsEnricher(
        sketch_id="s", scan_id="s", graph_service=grafo, params=params
    )
    entrada = [Username(value="bancoaurora")]
    with patch("flowsint_enrichers.social.to_impersonators.Logger"):
        saida = await enricher.scan(entrada)
        enricher.postprocess(saida, entrada)
    return saida, grafo


@pytest.mark.asyncio
async def test_demo_encontra_criticos_e_monta_grafo():
    saida, grafo = await _rodar({"modo": "demo", "risco_minimo": "BAIXO"})
    assert all(isinstance(c, SocialAccount) for c in saida)
    assert len(saida) == 7
    criticos = {
        (c.username.value, c.platform) for c in saida if c.sosia_risco == "CRÍTICO"
    }
    assert criticos == {
        ("banc0aurora", "Instagram"),
        ("bancoaurora_oficial", "Instagram"),
        ("bancoaurora_suporte", "Telegram"),
    }
    telegram = next(c for c in saida if c.platform == "Telegram")
    assert telegram.display_name == "Suporte Banco Aurora"
    assert "pix" in telegram.sosia_sinais
    assert telegram.id == "bancoaurora_suporte@Telegram"
    rotulos = [
        chamada.kwargs["rel_label"]
        for chamada in grafo.create_relationship.call_args_list
    ]
    assert (
        rotulos.count("LOOKALIKE_OF") == 7 and rotulos.count("HAS_SOCIAL_ACCOUNT") == 7
    )


@pytest.mark.asyncio
async def test_contato_compartilhado_vira_pivo_no_grafo():
    """O mesmo WhatsApp em dois sósias (Instagram e Telegram) liga as duas contas a um só Phone."""
    saida, grafo = await _rodar({"modo": "demo", "risco_minimo": "BAIXO"})
    ligacoes = [
        (c.kwargs["from_obj"].id, c.kwargs["to_obj"].number)
        for c in grafo.create_relationship.call_args_list
        if c.kwargs["rel_label"] == "PUBLISHES_CONTACT"
    ]
    assert sorted(ligacoes) == [
        ("banc0aurora@Instagram", "+5531900000000"),
        ("bancoaurora_suporte@Telegram", "+5531900000000"),
    ]
    insta = next(c for c in saida if c.username.value == "banc0aurora")
    assert insta.sosia_contatos == "+5531900000000"
    assert "mesmo telefone/WhatsApp de outro sósia" in insta.sosia_sinais
    assert len(insta.sosia_evidencia_sha256) == 64 and insta.sosia_coletado_em_utc


@pytest.mark.asyncio
async def test_risco_minimo_filtra():
    saida, _ = await _rodar({"modo": "demo", "risco_minimo": "CRÍTICO"})
    assert {c.sosia_risco for c in saida} == {"CRÍTICO"}
    assert len(saida) == 3


@pytest.mark.asyncio
async def test_sem_leitura_de_perfil_nao_ha_critico():
    saida, _ = await _rodar(
        {"modo": "demo", "risco_minimo": "BAIXO", "ler_perfil": "nao"}
    )
    assert len(saida) == 7
    assert "CRÍTICO" not in {c.sosia_risco for c in saida}


@pytest.mark.asyncio
async def test_falha_de_rede_nao_derruba_o_lote():
    enricher = UsernameToImpersonatorsEnricher(
        sketch_id="s", scan_id="s", params={"max_variantes": 5}
    )
    with (
        patch.object(sosia, "baixar", side_effect=RuntimeError("sem rede")),
        patch("flowsint_enrichers.social.to_impersonators.Logger") as log,
        patch.object(sosia.time, "sleep"),
    ):
        saida = await enricher.scan([Username(value="marca")])
    assert saida == []
    assert log.error.called


@pytest.mark.asyncio
async def test_contas_oficiais_e_filtro_de_plataformas():
    """Conta reserva da marca não vira sósia; o filtro limita as plataformas consultadas."""
    saida, _ = await _rodar(
        {
            "modo": "demo",
            "risco_minimo": "BAIXO",
            "oficiais": "bancoaurora_oficial, @BancoAurora_BR",
            "plataformas": "instagram,TikTok",
        }
    )
    pares = {(c.username.value, c.platform) for c in saida}
    assert ("bancoaurora_oficial", "Instagram") not in pares
    assert ("bancoaurora_br", "TikTok") not in pares
    assert {c.platform for c in saida} == {"Instagram", "TikTok"}
    assert ("banc0aurora", "Instagram") in pares


@pytest.mark.asyncio
async def test_plataforma_desconhecida_nao_quebra():
    with patch("flowsint_enrichers.social.to_impersonators.Logger") as log:
        enricher = UsernameToImpersonatorsEnricher(
            sketch_id="s", scan_id="s", params={"plataformas": "Orkut"}
        )
        saida = await enricher.scan([Username(value="marca")])
    assert saida == []
    assert "Orkut" in log.error.call_args.args[1]["message"]
