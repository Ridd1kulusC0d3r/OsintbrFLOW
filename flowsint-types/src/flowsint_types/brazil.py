"""Brazilian entity types. Added by OSINT Brasil Flow; upstream types preserved."""

import re

from pydantic import Field, field_validator, model_validator

from .flowsint_base import FlowsintType
from .registry import flowsint_type


def normalize_cnpj(value: str) -> str:
    value = re.sub(r"[.\s/\-]", "", str(value)).upper()
    if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", value) or len(set(value)) == 1:
        raise ValueError(
            "CNPJ inválido: use 12 caracteres e dois dígitos verificadores."
        )
    base = value[:12]
    for weights in (
        [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
        [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
    ):
        remainder = sum((ord(c) - 48) * w for c, w in zip(base, weights)) % 11
        base += str(0 if remainder < 2 else 11 - remainder)
    if base != value:
        raise ValueError("Dígitos verificadores do CNPJ não conferem.")
    return value


def normalize_cep(value: str) -> str:
    value = re.sub(r"[\s\-]", "", str(value))
    if not re.fullmatch(r"[0-9]{8}", value):
        raise ValueError("CEP precisa de oito dígitos.")
    return value


@flowsint_type
class BrazilCompany(FlowsintType):
    """Pessoa jurídica brasileira, identificada pelo CNPJ completo, nunca pelo nome."""

    cnpj: str = Field(..., title="CNPJ", json_schema_extra={"primary": True})
    name: str | None = None
    cep: str | None = None
    municipality: str | None = None
    uf: str | None = None
    status: str | None = None
    source_url: str | None = None
    retrieved_at: str | None = None
    evidence_sha256: str | None = None
    _validate_cnpj = field_validator("cnpj")(normalize_cnpj)

    @model_validator(mode="after")
    def label(self):
        self.nodeLabel = self.name or self.cnpj
        return self

    @classmethod
    def from_string(cls, value):
        return cls(cnpj=value)

    @classmethod
    def detect(cls, value):
        try:
            normalize_cnpj(value)
            return True
        except ValueError:
            return False


@flowsint_type
class BrazilCEP(FlowsintType):
    """Área postal; não demonstra residência ou localização exata."""

    cep: str = Field(..., title="CEP", json_schema_extra={"primary": True})
    _validate_cep = field_validator("cep")(normalize_cep)

    @model_validator(mode="after")
    def label(self):
        self.nodeLabel = f"CEP {self.cep[:5]}-{self.cep[5:]}"
        return self

    @classmethod
    def from_string(cls, value):
        return cls(cep=value)

    @classmethod
    def detect(cls, value):
        return bool(re.fullmatch(r"[0-9]{5}-[0-9]{3}", value.strip()))


@flowsint_type
class BrazilMunicipality(FlowsintType):
    """Município identificado pelo código IBGE de sete dígitos."""

    code: str = Field(
        ...,
        title="Código IBGE",
        pattern=r"^[0-9]{7}$",
        json_schema_extra={"primary": True},
    )
    name: str | None = None
    uf: str | None = None
    source_url: str | None = None
    retrieved_at: str | None = None
    evidence_sha256: str | None = None

    @model_validator(mode="after")
    def label(self):
        self.nodeLabel = self.name or self.code
        return self

    @classmethod
    def from_string(cls, value):
        return cls(code=value)

    @classmethod
    def detect(cls, value):
        return False  # Seven digits alone are ambiguous.
