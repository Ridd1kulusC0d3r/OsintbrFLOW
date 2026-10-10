#!/usr/bin/env python3
"""Create or check .env.prod for the hosted team deployment (Degrau 3).

Stdlib only. Never overwrites an existing file and never prints secrets.

  python scripts/init-prod.py --domain osint.exemplo.com.br --email ti@exemplo.com.br
  python scripts/init-prod.py --check        # audit an existing .env.prod
"""

import argparse
import base64
import os
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / ".env.prod"

# Values shipped in upstream examples or commonly typed by hand.
KNOWN_WEAK = {
    "superscretchangeitplz",
    "base64:qnHTmwYb+uoygIw9MsRMY22vS5YPchY+QOi/E79GAvM=",
    "password", "flowsint", "neo4j", "changeme", "change-me", "secret",
    "admin", "123456", "test-secret-please-ignore",
}
# name -> minimum length of the value
SECRETS = {
    "AUTH_SECRET": 32,
    "POSTGRES_PASSWORD": 24,
    "NEO4J_PASSWORD": 24,
}
DOMAIN_RE = re.compile(
    r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def parse_env(text):
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def problems(values):
    """Return a list of human-readable problems (never containing secrets)."""
    found = []
    for name, minimum in SECRETS.items():
        value = values.get(name, "")
        if not value:
            found.append(f"{name} ausente.")
        elif value.lower() in KNOWN_WEAK or len(value) < minimum:
            found.append(f"{name} fraco ou padrão (mínimo {minimum} caracteres aleatórios).")
        elif len(set(value)) < 8:
            found.append(f"{name} com pouca variação de caracteres.")
    key = values.get("MASTER_VAULT_KEY_V1", "")
    if not key:
        found.append("MASTER_VAULT_KEY_V1 ausente.")
    elif key in KNOWN_WEAK:
        found.append("MASTER_VAULT_KEY_V1 é a chave de exemplo do upstream.")
    else:
        try:
            raw = base64.b64decode(key.removeprefix("base64:"), validate=True)
        except ValueError:
            raw = b""
        if not key.startswith("base64:") or len(raw) != 32:
            found.append("MASTER_VAULT_KEY_V1 deve ser 'base64:' + 32 bytes aleatórios.")
    domain = values.get("DOMAIN", "")
    if not DOMAIN_RE.match(domain):
        found.append("DOMAIN ausente ou inválido (ex.: osint.exemplo.com.br, sem https://).")
    elif domain in {"localhost"} or domain.endswith((".local", ".localhost", "example.com")):
        found.append("DOMAIN precisa ser um nome público seu para o HTTPS automático.")
    if not EMAIL_RE.match(values.get("ACME_EMAIL", "")):
        found.append("ACME_EMAIL ausente ou inválido.")
    if values.get("FLOWSINT_ALLOW_REGISTRATION", "false").lower() in {"1", "true", "yes", "on"}:
        found.append(
            "AVISO: FLOWSINT_ALLOW_REGISTRATION=true — qualquer pessoa na internet "
            "pode criar conta. Volte para false depois de criar as contas da equipe."
        )
    return found


def generate(domain, email):
    return "\n".join([
        "# OsintbrFLOW — produção (Degrau 3). Gerado por scripts/init-prod.py.",
        "# NÃO versione este arquivo. Guarde uma cópia no cofre de senhas da equipe.",
        f"DOMAIN={domain}",
        f"ACME_EMAIL={email}",
        "AUTH_SECRET=" + secrets.token_hex(32),
        "MASTER_VAULT_KEY_V1=base64:" + base64.b64encode(secrets.token_bytes(32)).decode(),
        "POSTGRES_USER=flowsint",
        "POSTGRES_DB=flowsint",
        "POSTGRES_PASSWORD=" + secrets.token_hex(24),
        "NEO4J_USERNAME=neo4j",
        "NEO4J_PASSWORD=" + secrets.token_hex(24),
        "# Abra (true) só para criar as contas da equipe; depois volte para false.",
        "FLOWSINT_ALLOW_REGISTRATION=false",
        "",
    ])


NEXT_STEPS = """
Próximos passos (detalhes em docs/brasil/DEPLOY.md):
  1. Aponte o DNS (registro A/AAAA) de {domain} para o IP desta máquina.
  2. Libere só as portas 22, 80 e 443 no firewall.
  3. Para criar a primeira conta, troque FLOWSINT_ALLOW_REGISTRATION para true
     em {path} e suba:
       docker compose --env-file {path} -f compose.br.yml -f compose.prod.yml up -d --build
  4. Crie as contas da equipe em https://{domain}/register
  5. Volte FLOWSINT_ALLOW_REGISTRATION para false e reaplique o comando do passo 3.
  6. Confira: python scripts/init-prod.py --check
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--domain", help="nome público, ex.: osint.exemplo.com.br")
    parser.add_argument("--email", help="e-mail para o certificado (Let's Encrypt)")
    parser.add_argument("--check", action="store_true", help="só verificar o arquivo existente")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    path = args.path

    if args.check or path.exists():
        if not path.exists():
            print(f"{path.name} não existe. Rode sem --check para criá-lo.", file=sys.stderr)
            return 2
        if not args.check:
            print(f"{path.name} já existe; nada foi sobrescrito. Verificando...")
        found = problems(parse_env(path.read_text(encoding="utf-8")))
        blocking = [p for p in found if not p.startswith("AVISO")]
        for item in found:
            print(("  ! " if item.startswith("AVISO") else "  x ") + item)
        if path.stat().st_mode & 0o077:
            print(f"  ! Permissões abertas demais. Rode: chmod 600 {path.name}")
        if blocking:
            print("Configuração recusada. Corrija os itens acima ou apague o arquivo e gere de novo.")
            return 1
        print("Configuração aprovada. Nenhum segredo foi exibido.")
        return 0

    domain = (args.domain or "").strip().lower()
    email = (args.email or "").strip()
    content = generate(domain, email)
    found = problems(parse_env(content))
    if found:
        for item in found:
            print("  x " + item, file=sys.stderr)
        print("Informe --domain e --email válidos.", file=sys.stderr)
        return 1
    # O_EXCL: never clobber a file created between the check and the write.
    # Created with mode 600 from the start: no window where secrets are world-readable.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
    path.chmod(0o600)  # in case a umask stripped bits on exotic systems
    print(f"{path.name} criado com permissão 600. Nenhum segredo foi exibido.")
    print(NEXT_STEPS.format(domain=domain, path=path.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
