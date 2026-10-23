"""SÓSIA — perfis imitadores de um username (OSINT Brasil Flow).

Gera variantes que enganam o olho (homóglifos, iscas de "suporte"/"oficial",
as duas combinadas, separadores e erros de digitação), verifica em quais
plataformas estão registradas, descarta plataformas que respondem "existe"
até para um nome impossível (soft-404) e lê nome de exibição e bio dos
perfis encontrados para marcar como CRÍTICO quem imita o original.

Desde a 1.2, telefones/WhatsApp e e-mails publicados nas bios viram nós
``Phone`` e ``Email`` ligados à conta (``PUBLISHES_CONTACT``): quando dois
sósias publicam o mesmo número, o grafo mostra os dois presos ao mesmo nó,
que é o pivô da operação. Cada conta carrega também a prova da leitura
(SHA-256 da página e hora da coleta, em UTC).

A biblioteca é a mesma da ferramenta autônoma em ``ferramentas/sosia``
(cópia idêntica em ``tools/social/sosia.py``, conferida pelos testes).
"""

import asyncio
from typing import Dict, List, Tuple, Union

from tools.social import sosia

from flowsint_core.core.enricher_base import Enricher
from flowsint_core.core.logger import Logger
from flowsint_enrichers.registry import flowsint_enricher
from flowsint_types import Email, Phone, SocialAccount, Username

NIVEIS = ["CRÍTICO", "ALTO", "MÉDIO", "BAIXO"]


@flowsint_enricher
class UsernameToImpersonatorsEnricher(Enricher):
    """[SÓSIA] Encontra perfis imitadores: variantes do username registradas, com risco e sinais de golpe."""

    InputType = Username
    OutputType = SocialAccount

    @classmethod
    def name(cls) -> str:
        return "username_to_impersonators"

    @classmethod
    def category(cls) -> str:
        return "social"

    @classmethod
    def key(cls) -> str:
        return "username"

    @classmethod
    def get_params_schema(cls):
        return [
            {
                "name": "max_variantes",
                "type": "number",
                "description": "Quantas variantes verificar (60 = padrão; cada uma é consultada em 12 plataformas).",
                "required": False,
                "default": 60,
            },
            {
                "name": "risco_minimo",
                "type": "select",
                "description": "Só levar ao grafo sósias a partir deste nível de risco.",
                "required": False,
                "default": "MÉDIO",
                "options": [{"label": n, "value": n} for n in NIVEIS],
            },
            {
                "name": "ler_perfil",
                "type": "select",
                "description": "Ler nome de exibição e bio dos perfis encontrados (necessário para o nível CRÍTICO).",
                "required": False,
                "default": "sim",
                "options": [
                    {"label": "Sim", "value": "sim"},
                    {"label": "Não", "value": "nao"},
                ],
            },
            {
                "name": "oficiais",
                "type": "string",
                "description": "Contas da própria marca, separadas por vírgula (ex.: 'bancoaurora_sac,bancoaurora.rj'): nunca viram sósia.",
                "required": False,
            },
            {
                "name": "plataformas",
                "type": "string",
                "description": "Só estas plataformas, separadas por vírgula (ex.: 'Instagram,TikTok'). Vazio = as 12 padrão.",
                "required": False,
            },
            {
                "name": "modo",
                "type": "select",
                "description": "'demo' usa o caso fictício bancoaurora, sem internet (para laboratório e Colab).",
                "required": False,
                "default": "live",
                "options": [
                    {"label": "Ao vivo", "value": "live"},
                    {"label": "Demonstração", "value": "demo"},
                ],
            },
        ]

    def _log(self, mensagem: str) -> None:
        texto = mensagem.strip()
        if texto:
            Logger.info(self.sketch_id, {"message": f"[SÓSIA] {texto}"})

    @staticmethod
    def _virgulas(valor) -> List[str]:
        return [x.strip() for x in str(valor or "").split(",") if x.strip()]

    def _analisar(self, original: str, sites: Dict, rede, pausa: float) -> List[Dict]:
        """Bloqueante (rede + linhas de execução): roda fora do laço assíncrono."""
        busca = sosia.executar(
            original,
            sites,
            rede,
            pausa,
            maximo=int(self.params.get("max_variantes") or 60),
            ler_perfis=self.params.get("ler_perfil", "sim") != "nao",
            oficiais=self._virgulas(self.params.get("oficiais")),
            mostrar=self._log,
        )
        return busca["achados"]

    async def scan(self, data: List[InputType]) -> List[OutputType]:
        try:
            sites = sosia.carregar_sites(
                plataformas=self._virgulas(self.params.get("plataformas")) or None
            )
        except ValueError as e:
            Logger.error(self.sketch_id, {"message": f"[SÓSIA] {e}"})
            return []
        demo = self.params.get("modo") == "demo"
        minimo = NIVEIS.index(self.params.get("risco_minimo") or "MÉDIO")
        self.pares: List[Tuple[Username, Username, SocialAccount]] = []
        self.contatos: List[Tuple[SocialAccount, Union[Phone, Email]]] = []

        for original in data:
            try:
                if demo:
                    alvo, rede, _ = sosia.rede_demo(sites)
                    pausa = 0.0
                else:
                    alvo, rede, pausa = original.value, sosia.baixar, 0.3
                achados = await asyncio.to_thread(
                    self._analisar, alvo, sites, rede, pausa
                )
            except Exception as e:
                Logger.error(
                    self.sketch_id,
                    {"message": f"[SÓSIA] Falha ao analisar {original.value}: {e}"},
                )
                continue

            for a in achados:
                if NIVEIS.index(a["risco"]) > minimo:
                    continue
                variante = Username(value=a["variante"], platform=a["site"])
                conta = SocialAccount(
                    username=variante,
                    platform=a["site"],
                    profile_url=a["url"],
                    display_name=a.get("perfil_nome") or None,
                    bio=a.get("perfil_bio") or None,
                    sosia_original=alvo,
                    sosia_risco=a["risco"],
                    sosia_tecnica=sosia.TECNICAS[a["tecnica"]][1],
                    sosia_sinais="; ".join(a.get("sinais", [])) or None,
                    sosia_perfil_legivel=bool(a.get("perfil_legivel")),
                    sosia_contatos="; ".join(c["valor"] for c in a.get("contatos", []))
                    or None,
                    sosia_evidencia_sha256=(a.get("prova") or {}).get("sha256"),
                    sosia_coletado_em_utc=(a.get("prova") or {}).get("coletado_em_utc"),
                )
                self.pares.append((original, variante, conta))
                for c in a.get("contatos", []):
                    try:
                        if c["tipo"] == "telefone":
                            self.contatos.append((conta, Phone(number=c["valor"])))
                        elif c["tipo"] == "email":
                            self.contatos.append((conta, Email(email=c["valor"])))
                    except ValueError:
                        continue  # número/e-mail que o tipo do Flowsint não aceita: fica só na propriedade
            Logger.info(
                self.sketch_id,
                {
                    "message": f"[SÓSIA] {original.value}: {len(achados)} sósia(s) registrados, "
                    f"{sum(1 for a in achados if a['risco'] == 'CRÍTICO')} CRÍTICO(S)"
                },
            )
        return [conta for _, _, conta in self.pares]

    def postprocess(
        self, results: List[OutputType], original_input: List[InputType]
    ) -> List[OutputType]:
        if not self._graph_service:
            return results
        for original, variante, conta in getattr(self, "pares", []):
            try:
                self.create_node(original)
                self.create_node(variante)
                self.create_node(conta)
                self.create_relationship(variante, original, "LOOKALIKE_OF")
                self.create_relationship(variante, conta, "HAS_SOCIAL_ACCOUNT")
                self.log_graph_message(
                    f"{variante.value} ({conta.platform}) imita {original.value} · {conta.sosia_risco}"
                )
            except Exception as e:
                Logger.error(
                    self.sketch_id,
                    {
                        "message": f"[SÓSIA] Falha ao gravar {variante.value} em {conta.platform}: {e}"
                    },
                )
        for conta, contato in getattr(self, "contatos", []):
            try:
                self.create_node(contato)
                self.create_relationship(conta, contato, "PUBLISHES_CONTACT")
                self.log_graph_message(
                    f"{conta.username.value} ({conta.platform}) publica {contato.nodeLabel}"
                )
            except Exception as e:
                Logger.error(
                    self.sketch_id,
                    {"message": f"[SÓSIA] Falha ao gravar contato de {conta.id}: {e}"},
                )
        return results


InputType = UsernameToImpersonatorsEnricher.InputType
OutputType = UsernameToImpersonatorsEnricher.OutputType
