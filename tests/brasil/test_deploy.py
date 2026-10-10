"""Degrau 3 (hosted team deploy): secrets generator and static deploy contracts."""

import importlib.util
import re
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("init_prod", ROOT / "scripts/init-prod.py")
init_prod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(init_prod)

ARGS = ["--domain", "osint.exemplo.com.br", "--email", "ti@exemplo.com.br"]


def test_generates_strong_private_file_without_printing_secrets(tmp_path, capsys):
    target = tmp_path / ".env.prod"
    assert init_prod.main(ARGS + ["--path", str(target)]) == 0
    values = init_prod.parse_env(target.read_text())
    assert init_prod.problems(values) == []
    assert values["FLOWSINT_ALLOW_REGISTRATION"] == "false"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    out = capsys.readouterr().out
    for name in ("AUTH_SECRET", "POSTGRES_PASSWORD", "NEO4J_PASSWORD", "MASTER_VAULT_KEY_V1"):
        assert values[name] not in out


def test_two_runs_produce_different_secrets(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    init_prod.main(ARGS + ["--path", str(a)])
    init_prod.main(ARGS + ["--path", str(b)])
    va, vb = init_prod.parse_env(a.read_text()), init_prod.parse_env(b.read_text())
    assert va["AUTH_SECRET"] != vb["AUTH_SECRET"]


def test_never_overwrites_existing_file(tmp_path):
    target = tmp_path / ".env.prod"
    target.write_text("AUTH_SECRET=superscretchangeitplz\n")
    target.chmod(0o600)
    assert init_prod.main(ARGS + ["--path", str(target)]) == 1  # audited, refused
    assert target.read_text() == "AUTH_SECRET=superscretchangeitplz\n"


@pytest.mark.parametrize("override,fragment", [
    ("AUTH_SECRET=superscretchangeitplz", "AUTH_SECRET"),
    ("AUTH_SECRET=" + "a" * 64, "AUTH_SECRET"),
    ("POSTGRES_PASSWORD=flowsint", "POSTGRES_PASSWORD"),
    ("NEO4J_PASSWORD=password", "NEO4J_PASSWORD"),
    ("MASTER_VAULT_KEY_V1=base64:qnHTmwYb+uoygIw9MsRMY22vS5YPchY+QOi/E79GAvM=", "MASTER_VAULT_KEY_V1"),
    ("MASTER_VAULT_KEY_V1=base64:c2hvcnQ=", "MASTER_VAULT_KEY_V1"),
    ("DOMAIN=https://osint.exemplo.com.br", "DOMAIN"),
    ("DOMAIN=localhost", "DOMAIN"),
    ("ACME_EMAIL=", "ACME_EMAIL"),
])
def test_check_refuses_weak_or_default_values(tmp_path, override, fragment):
    target = tmp_path / ".env.prod"
    init_prod.main(ARGS + ["--path", str(target)])
    key = override.split("=", 1)[0]
    lines = [ln for ln in target.read_text().splitlines() if not ln.startswith(key + "=")]
    target.write_text("\n".join(lines + [override]) + "\n")
    assert init_prod.main(["--check", "--path", str(target)]) == 1
    assert any(fragment in p for p in init_prod.problems(init_prod.parse_env(target.read_text())))


def test_open_registration_is_a_warning_not_a_refusal(tmp_path, capsys):
    target = tmp_path / ".env.prod"
    init_prod.main(ARGS + ["--path", str(target)])
    target.write_text(target.read_text().replace(
        "FLOWSINT_ALLOW_REGISTRATION=false", "FLOWSINT_ALLOW_REGISTRATION=true"))
    assert init_prod.main(["--check", "--path", str(target)]) == 0
    assert "qualquer pessoa" in capsys.readouterr().out


def test_refuses_to_generate_without_valid_domain(tmp_path):
    target = tmp_path / ".env.prod"
    assert init_prod.main(["--domain", "", "--email", "x", "--path", str(target)]) == 1
    assert not target.exists()


def test_prod_override_publishes_only_caddy():
    text = (ROOT / "compose.prod.yml").read_text()
    published = re.findall(r'^\s+- "(\d+):\d+(?:/udp)?"$', text, re.M)
    assert sorted(set(published)) == ["443", "80"]
    for service in ("postgres", "redis", "neo4j", "api", "app"):
        block = re.search(rf"^  {service}:\n(.*?)(?=^  \S|\Z)", text, re.M | re.S).group(1)
        assert "ports: !reset []" in block, service
    assert "FLOWSINT_ALLOW_REGISTRATION=${FLOWSINT_ALLOW_REGISTRATION:-false}" in text
    assert "compose.lab.yml" in text  # explicit warning against mixing


def test_caddyfile_has_security_headers_and_body_limit():
    text = (ROOT / "deploy/Caddyfile").read_text()
    for needle in ("Strict-Transport-Security", "X-Content-Type-Options \"nosniff\"",
                   "frame-ancestors 'none'", "X-Frame-Options \"DENY\"",
                   "Referrer-Policy", "max_size 10MB", "reverse_proxy app:8080"):
        assert needle in text
    assert "rate_limit" not in text  # stock Caddy has no rate limiter
