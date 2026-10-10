"""`osintbr` command: start the single-user laboratory and open the panel.

Stdlib + uvicorn only. Always binds to 127.0.0.1; there is no option to
expose the laboratory, which has no login by design.
"""

import argparse
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from . import __version__

HOST = "127.0.0.1"
STATIC = Path(__file__).with_name("static")


def data_dir():
    """Per-user folder for cases, following each OS convention."""
    if os.getenv("OSINTBR_HOME"):
        return Path(os.environ["OSINTBR_HOME"])
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "OsintbrFLOW"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "OsintbrFLOW"
    base = Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "osintbrflow"


def free_port(preferred):
    """Use the preferred port when free; otherwise let the OS choose one."""
    for candidate in (preferred, 0):
        with socket.socket() as probe:
            try:
                probe.bind((HOST, candidate))
            except OSError:
                continue
            return probe.getsockname()[1]
    raise SystemExit("Nenhuma porta local disponível.")


def frontend_dir(explicit=None):
    candidates = [explicit, os.getenv("OSINTBR_FRONTEND"), STATIC]
    # Development checkout: repository layout next to flowsint-core/.
    repo = Path(__file__).resolve().parents[3] / "flowsint-app"
    candidates += [repo / "dist-brasil", repo / "dist"]
    for candidate in candidates:
        if candidate and (Path(candidate) / "brasil.html").exists():
            return Path(candidate)
    return None


def wait_and_open(url, health, open_browser, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=1) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(0.2)
    else:
        print("O servidor não respondeu a tempo.", file=sys.stderr)
        return
    print(f"OSINT Brasil Flow pronto em {url}")
    print("Para encerrar, feche esta janela ou pressione Ctrl+C.")
    if open_browser:
        webbrowser.open(url)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="osintbr",
        description="Laboratório OSINT Brasil Flow: casos, grafo e evidências com hash, no seu computador.",
    )
    parser.add_argument("--port", type=int, default=8000, help="porta local preferida (padrão: 8000; outra livre se ocupada)")
    parser.add_argument("--data-dir", type=Path, help="pasta dos casos (padrão: pasta de dados do usuário)")
    parser.add_argument("--frontend", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--no-browser", action="store_true", help="não abrir o navegador")
    parser.add_argument("--print-data-dir", action="store_true", help="mostrar a pasta dos casos e sair")
    parser.add_argument("--version", action="version", version=f"OsintbrFLOW {__version__}")
    return parser


def configure(args):
    """Prepare environment for osintbr.lab; returns (port, url) or exits with a clear message."""
    folder = args.data_dir or data_dir()
    if args.print_data_dir:
        print(folder)
        raise SystemExit(0)
    frontend = frontend_dir(args.frontend)
    if frontend is None:
        raise SystemExit(
            "Painel não encontrado. Em um checkout de desenvolvimento, compile com:\n"
            "  npm run build:brasil --workspace flowsint-app"
        )
    folder.mkdir(parents=True, exist_ok=True)
    port = free_port(args.port)
    # The lab reads its configuration at import time.
    os.environ["OSINTBR_DB"] = str(folder / "brasil.sqlite3")
    os.environ["OSINTBR_FRONTEND"] = str(frontend)
    os.environ["OSINTBR_PORT"] = str(port)
    for name in ("OSINTBR_PROXY_ORIGIN", "OSINTBR_COLAB_TOKEN"):
        os.environ.pop(name, None)
    return port, f"http://{HOST}:{port}/brasil.html"


def main(argv=None):
    args = build_parser().parse_args(argv)
    port, url = configure(args)
    import uvicorn

    from .lab import create_app

    threading.Thread(
        target=wait_and_open,
        args=(url, f"http://{HOST}:{port}/health", not args.no_browser),
        daemon=True,
    ).start()
    print(f"Casos guardados em: {os.environ['OSINTBR_DB']}")
    uvicorn.run(create_app(), host=HOST, port=port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
