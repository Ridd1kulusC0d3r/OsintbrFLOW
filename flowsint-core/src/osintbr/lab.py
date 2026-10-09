"""Single-user laboratory: localhost, or an explicitly configured Colab proxy."""

import hmac
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import build_router


def create_app():
    proxy_origin = os.getenv("OSINTBR_PROXY_ORIGIN", "").rstrip("/")
    token = os.getenv("OSINTBR_COLAB_TOKEN", "")
    hosts = {"127.0.0.1", "localhost", "::1"}
    origins = {
        "http://127.0.0.1:8000", "http://localhost:8000",
        "http://127.0.0.1:5173", "http://localhost:5173",
    }
    if proxy_origin or token:
        proxy = urlsplit(proxy_origin)
        if (
            proxy.scheme != "https" or not proxy.hostname
            or proxy.username or proxy.password or proxy.path
            or proxy.query or proxy.fragment or proxy.port not in {None, 443}
            or len(token) < 32 or not token.isascii()
        ):
            raise ValueError("Proxy exige origem HTTPS exata e token ASCII de pelo menos 32 caracteres.")
        origins.add(proxy_origin)

    app = FastAPI(title="OSINT Brasil Flow · laboratório", docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def lab_access(request: Request, call_next):
        try:
            host = urlsplit("//" + request.headers.get("host", "")).hostname
        except ValueError:
            host = None
        # Colab can rewrite the upstream Host header. In proxy mode, Host
        # is transport metadata, not an access credential: every API route
        # still requires the session bearer token and an allowed Origin.
        # Keep DNS-rebinding protection for the unauthenticated local mode.
        if not token and host not in hosts:
            return JSONResponse({"detail": "Host não autorizado."}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return JSONResponse({"detail": "Origem não autorizada."}, status_code=403)
        if token and request.url.path.startswith("/api/"):
            authorization = request.headers.get("authorization", "")
            if not hmac.compare_digest(authorization.encode(), ("Bearer " + token).encode()):
                return JSONResponse({"detail": "Chave da sessão ausente ou inválida."}, status_code=401)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and "application/json" not in request.headers.get("content-type", ""):
            return JSONResponse({"detail": "Envie application/json."}, status_code=415)
        response = await call_next(request)
        if token:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    app.include_router(build_router(lambda: "local-lab"), prefix="/api/brasil")

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "colab-proxy" if token else "local-only"}

    root = Path(os.getenv("OSINTBR_FRONTEND", "flowsint-app/dist"))
    if root.exists():
        app.mount("/", StaticFiles(directory=root, html=True), name="frontend")
    return app


app = create_app()
