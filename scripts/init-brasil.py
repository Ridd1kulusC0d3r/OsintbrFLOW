#!/usr/bin/env python3
"""Create local credentials without overwriting existing configuration."""

import base64
import secrets
from pathlib import Path

p = Path(__file__).resolve().parent.parent / ".env"
if p.exists():
    raise SystemExit(".env já existe; configuração preservada.")
p.write_text(
    "\n".join(
        [
            "AUTH_SECRET=" + secrets.token_hex(32),
            "MASTER_VAULT_KEY_V1=base64:"
            + base64.b64encode(secrets.token_bytes(32)).decode(),
            "POSTGRES_USER=flowsint",
            "POSTGRES_DB=flowsint",
            "POSTGRES_PASSWORD=" + secrets.token_hex(24),
            "NEO4J_USERNAME=neo4j",
            "NEO4J_PASSWORD=" + secrets.token_hex(24),
            "ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173",
        ]
    )
    + "\n"
)
p.chmod(0o600)
print(".env criado. Nenhum segredo foi exibido.")
