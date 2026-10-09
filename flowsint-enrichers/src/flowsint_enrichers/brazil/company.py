"""OSINT Brasil Flow additions. Provider failures propagate to the task status."""

from osintbr.providers import Provider

from flowsint_core.core.enricher_base import Enricher
from flowsint_enrichers.registry import flowsint_enricher
from flowsint_types.brazil import BrazilCEP, BrazilCompany, BrazilMunicipality


@flowsint_enricher
class BrazilCompanyLookup(Enricher):
    """Consulta CNPJ na BrasilAPI. Fonte intermediária; não é certidão da Receita."""

    InputType = BrazilCompany
    OutputType = BrazilCompany

    @classmethod
    def name(cls):
        return "br_cnpj_lookup"

    @classmethod
    def category(cls):
        return "Brasil"

    @classmethod
    def key(cls):
        return "cnpj"

    async def scan(self, data):
        result = []
        for item in data:
            e = await Provider().fetch("cnpj", item.cnpj)
            d = e["data"]
            result.append(
                BrazilCompany(
                    cnpj=d["cnpj"],
                    name=d.get("razao_social"),
                    cep=d.get("cep"),
                    municipality=d.get("municipio"),
                    uf=d.get("uf"),
                    status=d.get("descricao_situacao_cadastral"),
                    source_url=e["url"],
                    retrieved_at=e["retrieved_at"],
                    evidence_sha256=e["sha256"],
                )
            )
        return result

    def postprocess(self, results, original_input):
        for item in results:
            self.create_node(item)
        return results


@flowsint_enricher
class BrazilCompanyToCEP(Enricher):
    """Extrai CEP já observado no cadastro. Execute br_cnpj_lookup antes."""

    InputType = BrazilCompany
    OutputType = BrazilCEP

    @classmethod
    def name(cls):
        return "br_company_to_cep"

    @classmethod
    def category(cls):
        return "Brasil"

    @classmethod
    def key(cls):
        return "cnpj"

    async def scan(self, data):
        self.pairs = [(item, BrazilCEP(cep=item.cep)) for item in data if item.cep]
        return [cep for _, cep in self.pairs]

    def postprocess(self, results, original_input):
        for company, cep in self.pairs:
            self.create_node(cep)
            self.create_relationship(company, cep, "CADASTRADA_NO_CEP")
        return results


@flowsint_enricher
class BrazilCEPToMunicipality(Enricher):
    """Consulta ViaCEP e IBGE. CEP é área postal, não endereço exato de uma pessoa."""

    InputType = BrazilCEP
    OutputType = BrazilMunicipality

    @classmethod
    def name(cls):
        return "br_cep_to_municipality"

    @classmethod
    def category(cls):
        return "Brasil"

    @classmethod
    def key(cls):
        return "cep"

    async def scan(self, data):
        self.pairs = []
        for item in data:
            postal = await Provider().fetch("cep", item.cep)
            record = await Provider().fetch(
                "municipio", str(postal["data"].get("ibge", ""))
            )
            d = record["data"]
            self.pairs.append(
                (
                    item,
                    BrazilMunicipality(
                        code=str(d["id"]),
                        name=d["nome"],
                        uf=postal["data"].get("uf"),
                        source_url=record["url"],
                        retrieved_at=record["retrieved_at"],
                        evidence_sha256=record["sha256"],
                    ),
                )
            )
        return [city for _, city in self.pairs]

    def postprocess(self, results, original_input):
        for cep, city in self.pairs:
            self.create_node(city)
            self.create_relationship(cep, city, "CEP_NO_MUNICIPIO")
        return results
