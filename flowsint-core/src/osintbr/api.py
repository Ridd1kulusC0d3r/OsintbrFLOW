"""API factory shared by authenticated Flowsint and localhost laboratory."""

import asyncio
import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .engine import RECIPES, execute, native_graph
from .store import Store, verify


class CaseInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=120)
    purpose: str = Field(min_length=5, max_length=500)


class RunInput(BaseModel):
    seed_kind: Literal["cnpj", "cep", "municipio"] = "cnpj"
    seed: str = Field(min_length=1, max_length=30)
    steps: list[Literal["cnpj", "cep", "municipio"]] = Field(min_length=1, max_length=3)
    mode: Literal["demo", "live"] = "live"


def build_router(owner_dependency, store=None, provider=None):
    router = APIRouter()

    # Store creation is lazy so importing the native API does not write to disk.
    def get_store():
        return store or Store()

    semaphore = asyncio.Semaphore(4)

    @router.get("/recipes")
    def recipes(owner=Depends(owner_dependency)):
        return RECIPES

    @router.get("/sources")
    def sources(owner=Depends(owner_dependency)):
        return json.loads(Path(__file__).with_name("sources.json").read_text())

    @router.get("/cases")
    def cases(owner=Depends(owner_dependency)):
        return get_store().list(owner)

    @router.post("/cases", status_code=201)
    def create(body: CaseInput, owner=Depends(owner_dependency)):
        return get_store().create(owner, body.title.strip(), body.purpose.strip())

    def case_or_404(owner, case_id):
        try:
            return get_store().get(owner, case_id)
        except KeyError:
            raise HTTPException(404, "Caso não encontrado.")

    @router.get("/cases/{case_id}")
    def get(case_id: str, owner=Depends(owner_dependency)):
        return case_or_404(owner, case_id)

    @router.post("/cases/{case_id}/runs")
    async def run(case_id: str, body: RunInput, owner=Depends(owner_dependency)):
        case_or_404(owner, case_id)
        try:
            # A run performs at most three serial lookups and two attempts per lookup.
            async with semaphore:
                result = await execute(
                    body.seed_kind, body.seed, body.steps, body.mode, provider
                )
            return get_store().append(owner, case_id, result)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/cases/{case_id}/export")
    def export(case_id: str, owner=Depends(owner_dependency)):
        case_or_404(owner, case_id)
        return get_store().export(owner, case_id)

    @router.get("/cases/{case_id}/graph/{run_id}")
    def graph(case_id: str, run_id: str, owner=Depends(owner_dependency)):
        case = case_or_404(owner, case_id)
        selected = next((r for r in case["runs"] if r["id"] == run_id), None)
        if not selected:
            raise HTTPException(404, "Coleta não encontrada.")
        return native_graph(selected)

    @router.post("/verify")
    async def check(request: Request, owner=Depends(owner_dependency)):
        raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > 15_000_000:
                raise HTTPException(413, "Pacote excede 15 MB.")
        try:
            return verify(json.loads(raw))
        except (ValueError, TypeError, KeyError, AttributeError):
            raise HTTPException(422, "Pacote inválido.")

    return router
