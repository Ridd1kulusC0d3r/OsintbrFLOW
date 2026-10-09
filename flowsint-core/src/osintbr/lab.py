"""Portable single-user laboratory. Never expose this app to a network."""

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import build_router

app = FastAPI(title="OSINT Brasil Flow · laboratório local")


@app.middleware("http")
async def local_only(request: Request, call_next):
    allowed = {"127.0.0.1", "localhost", "[::1]"}
    host = request.headers.get("host", "").rsplit(":", 1)[0]
    if host not in allowed:
        return JSONResponse(
            {"detail": "Laboratório restrito a localhost."}, status_code=403
        )
    origin = request.headers.get("origin")
    if origin and origin not in {
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    }:
        return JSONResponse({"detail": "Origem não autorizada."}, status_code=403)
    if request.method not in {
        "GET",
        "HEAD",
        "OPTIONS",
    } and "application/json" not in request.headers.get("content-type", ""):
        return JSONResponse({"detail": "Envie application/json."}, status_code=415)
    return await call_next(request)


app.include_router(build_router(lambda: "local-lab"), prefix="/api/brasil")


@app.get("/health")
def health():
    return {"status": "ok", "mode": "local-only"}


root = Path(os.getenv("OSINTBR_FRONTEND", "flowsint-app/dist"))
if root.exists():
    app.mount("/", StaticFiles(directory=root, html=True), name="frontend")
