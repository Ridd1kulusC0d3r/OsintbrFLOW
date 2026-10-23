"""SÓSIA no CI Brasil: suíte da ferramenta autônoma e paridade com a cópia usada pelo enriquecedor."""

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
KIT = RAIZ / "ferramentas" / "sosia"
COPIA = RAIZ / "flowsint-enrichers" / "src" / "tools" / "social"


@pytest.mark.parametrize(
    "nome", ["sosia.py", "sites_padrao.json", "sites_extra.json", "demo/caso_demo.json"]
)
def test_copia_do_enriquecedor_igual_a_ferramenta(nome):
    assert (COPIA / nome).read_bytes() == (KIT / nome).read_bytes(), (
        f"{nome} divergiu: copie ferramentas/sosia/{nome} para flowsint-enrichers/src/tools/social/{nome}"
    )


def test_suite_da_ferramenta_autonoma():
    r = subprocess.run(
        [
            sys.executable,
            "-I",
            "-X",
            "utf8",
            "-X",
            "warn_default_encoding",
            "-W",
            "error::EncodingWarning",
            "-W",
            "error::ResourceWarning",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
        ],
        cwd=KIT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    assert r.returncode == 0, r.stderr[-3000:]
    assert "OK" in r.stderr


def test_demo_pela_linha_de_comando(tmp_path):
    r = subprocess.run(
        [
            sys.executable,
            "-I",
            "-X",
            "utf8",
            "sosia.py",
            "--demo",
            "--sem-abrir",
            "--saida",
            str(tmp_path),
        ],
        cwd=KIT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert r.returncode == 0, r.stderr[-3000:]
    assert "CRÍTICO: 3" in r.stdout
    pasta = next(tmp_path.iterdir())
    assert {p.name for p in pasta.iterdir()} >= {
        "relatorio.html",
        "achados.csv",
        "mudancas.csv",
        "manifesto.txt",
    }
