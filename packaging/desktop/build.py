"""Gera o aplicativo de desktop OsintbrFLOW com PyInstaller (Windows, macOS, Linux).

Uso, a partir da raiz do repositório e com o painel já compilado
(`npm run build:brasil --workspace flowsint-app`):

    python -m pip install -r requirements-brasil.txt "pyinstaller>=6.10,<7" "pillow>=11,<13"
    python -m pip install "pywebview>=5,<7"     # opcional: janela própria
    python packaging/desktop/build.py           # gera packaging/desktop/dist/
    python packaging/desktop/build.py --zip     # também gera o .zip de distribuição

Formato "uma pasta" (onedir), não "arquivo único" (onefile): o onefile
descompacta ~40 MB numa pasta temporária a cada abertura, o que deixa a
partida mais lenta, deixa lixo se o processo for encerrado à força e
dispara mais alarmes falsos de antivírus no Windows. O onedir abre direto.

Só entra no pacote o que o código importa, o painel compilado e
sources.json. Nada de .env, venvs, testes, dados de casos ou node_modules.
"""

import argparse
import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PANEL = ROOT / "flowsint-app" / "dist-brasil"
MANUAL = ROOT / "docs" / "manual"  # manual ilustrado (HTML + imagens), copiado para o .zip
SOURCES = ROOT / "flowsint-core" / "src" / "osintbr" / "sources.json"
NAME = "OsintbrFLOW"

# Nunca devem aparecer no pacote final (verificado depois do build).
FORBIDDEN = (".env", "node_modules", "brasil.sqlite3", "site-packages", "tests", ".git")

LAUNCHERS = {
    "windows": ["Abrir OsintbrFLOW.bat"],
    "macos": ["Abrir OsintbrFLOW.command"],
    "linux": ["abrir-osintbrflow.sh"],
}
PIPX_LAUNCHERS = {
    "windows": ["Abrir OsintbrFLOW (pipx).bat"],
    "macos": ["Abrir OsintbrFLOW (pipx).command"],
    "linux": ["abrir-osintbrflow-pipx.sh"],
}


def system():
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def version():
    text = (ROOT / "flowsint-core" / "src" / "osintbr" / "__init__.py").read_text(encoding="utf-8")
    return text.split('__version__ = "', 1)[1].split('"', 1)[0]


def icon(work):
    """Windows quer .ico de verdade; o icon.ico do painel é um PNG renomeado.

    Sem Pillow, segue sem ícone (o aplicativo funciona igual). No Linux o
    executável não carrega ícone; no macOS o ícone só vale para pacotes .app,
    que este build não gera (o executável roda pelo lançador .command).
    """
    if system() != "windows":
        return None
    try:
        from PIL import Image
    except ImportError:
        print("Pillow ausente: executável sem ícone.")
        return None
    target = work / "osintbrflow.ico"
    with Image.open(PANEL / "icon.png") as image:
        image.save(target, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return target


def pyinstaller_args(work, dist, with_window):
    sep = ";" if system() == "windows" else ":"
    args = [
        sys.executable, "-m", "PyInstaller",
        str(HERE / "entrada.py"),
        "--name", NAME,
        "--onedir",
        "--console",  # a janela de texto mostra onde ficam os casos e encerra o servidor ao ser fechada
        "--noconfirm", "--clean",
        "--log-level", "WARN",
        "--workpath", str(work),
        "--distpath", str(dist),
        "--specpath", str(work),
        "--paths", str(ROOT / "flowsint-core" / "src"),
        "--paths", str(ROOT / "flowsint-types" / "src"),
        # flowsint_types registra os tipos importando os módulos dinamicamente.
        "--collect-submodules", "flowsint_types",
        "--collect-submodules", "osintbr",
        "--add-data", f"{PANEL}{sep}osintbr/static",
        "--add-data", f"{SOURCES}{sep}osintbr",
        "--add-data", f"{ROOT / 'LICENSE'}{sep}osintbr",
        "--add-data", f"{ROOT / 'NOTICE'}{sep}osintbr",
    ]
    for module in ("tkinter", "pytest", "IPython", "matplotlib", "numpy"):
        args += ["--exclude-module", module]
    if not with_window:
        args += ["--exclude-module", "webview"]
    ico = icon(work)
    if ico:
        args += ["--icon", str(ico)]
    return args


def check_bundle(app):
    found = [str(p.relative_to(app)) for p in app.rglob("*") if p.name in FORBIDDEN]
    if found:
        raise SystemExit(f"Itens proibidos no pacote: {found}")
    if not (app / "_internal" / "osintbr" / "static" / "brasil.html").exists():
        raise SystemExit("Painel ausente no pacote.")
    if not (app / "_internal" / "osintbr" / "sources.json").exists():
        raise SystemExit("sources.json ausente no pacote.")


def size_mb(folder):
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) / 1_000_000


def package(dist, app):
    """Pasta de distribuição: COMECE-AQUI.md, manual/, lançador do sistema e o aplicativo."""
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine().lower(), platform.machine().lower())
    label = f"{NAME}-{version()}-{system()}-{arch}"
    folder = dist / label
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir()
    shutil.copytree(app, folder / NAME, symlinks=True)
    shutil.copy2(HERE / "COMECE-AQUI.md", folder)
    if (MANUAL / "index.html").exists():
        shutil.copytree(MANUAL, folder / "manual")
    else:
        print("Manual ausente (docs/manual/index.html): .zip sem manual.")
    for launcher in LAUNCHERS[system()]:
        target = folder / launcher
        shutil.copy2(HERE / "lancadores" / launcher, target)
        target.chmod(0o755)
    # Variante para quem instalou com pipx (chama o comando `osintbr`).
    (folder / "pipx").mkdir()
    for launcher in PIPX_LAUNCHERS[system()]:
        target = folder / "pipx" / launcher
        shutil.copy2(HERE / "lancadores" / "pipx" / launcher, target)
        target.chmod(0o755)
    # zipfile guarda as permissões Unix: os lançadores continuam executáveis.
    archive = shutil.make_archive(str(dist / label), "zip", root_dir=dist, base_dir=label)
    print(f"Zip: {archive} ({Path(archive).stat().st_size / 1_000_000:.1f} MB)")
    return Path(archive)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gera o aplicativo de desktop OsintbrFLOW.")
    parser.add_argument("--zip", action="store_true", help="também gera o .zip de distribuição")
    parser.add_argument("--sem-janela", action="store_true", help="não empacotar o pywebview mesmo que esteja instalado")
    args = parser.parse_args(argv)

    if not (PANEL / "brasil.html").exists():
        raise SystemExit("Painel não compilado. Rode: npm run build:brasil --workspace flowsint-app")
    work = HERE / "build"
    dist = HERE / "dist"
    with_window = not args.sem_janela and importlib.util.find_spec("webview") is not None
    print(f"Janela própria (pywebview): {'incluída' if with_window else 'não incluída; abre no navegador'}")
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run(pyinstaller_args(work, dist, with_window), check=True, cwd=ROOT)
    app = dist / NAME
    check_bundle(app)
    print(f"Aplicativo: {app} ({size_mb(app):.1f} MB)")
    if args.zip:
        package(dist, app)


if __name__ == "__main__":
    main()
