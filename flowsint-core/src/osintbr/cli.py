"""`osintbr` command: start the single-user laboratory and open the panel.

Stdlib + uvicorn only; pywebview is optional (own window, `--janela`).
Always binds to 127.0.0.1; there is no option to expose the laboratory,
which has no login by design.
"""

import argparse
import logging
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


# Local health checks must never go through a system/corporate HTTP proxy.
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def wait_ready(health, timeout=30, alive=lambda: True):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not alive():
            print("O servidor parou durante a inicialização (porta ocupada?).", file=sys.stderr, flush=True)
            return False
        try:
            with LOCAL.open(health, timeout=1) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.2)
    print("O servidor não respondeu a tempo.", file=sys.stderr, flush=True)
    return False


def wait_and_open(url, health, open_browser, timeout=30):
    if not wait_ready(health, timeout):
        return
    print(f"OSINT Brasil Flow pronto em {url}", flush=True)
    print("Para encerrar, feche esta janela ou pressione Ctrl+C.", flush=True)
    if open_browser:
        webbrowser.open(url)


def frozen():
    """True inside the desktop executable built with PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def interface(args):
    """Where the panel appears: 'janela' (own window), 'navegador' or 'nenhuma'."""
    if args.no_browser:
        return "nenhuma"
    if args.navegador:
        return "navegador"
    if args.janela or frozen():
        return "janela"
    return "navegador"


def load_webview():
    try:
        import webview
    except Exception:  # absent, or present but broken (e.g. missing native runtime)
        return None
    return webview


def wait_until_interrupted(thread):
    """Keep the server alive in browser fallback until Ctrl+C or the console closes."""
    try:
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        pass


def serve_in_window(server, url, health, webview):
    """Server in a background thread, window on the main thread (GUI toolkits need it).

    Closing the window stops the server. If the window cannot be created
    (no GUI backend), fall back to the browser while the server keeps running.
    """
    thread = threading.Thread(target=server.run, name="osintbr-servidor", daemon=True)
    thread.start()
    try:
        if not wait_ready(health, alive=thread.is_alive):
            raise SystemExit(1)
        print(f"OSINT Brasil Flow pronto em {url}", flush=True)
        print("Fechar a janela do painel encerra o laboratório.", flush=True)
        # pywebview logs a traceback per missing GUI toolkit; one line is enough here.
        logging.getLogger("pywebview").setLevel(logging.CRITICAL)
        try:
            webview.create_window("OSINT Brasil Flow", url, width=1280, height=820, min_size=(900, 600))
            webview.start()
        except Exception as exc:  # pywebview raises varied errors when no GUI backend exists
            print(f"Janela própria indisponível ({type(exc).__name__}); abrindo no navegador.", flush=True)
            print("Para encerrar, feche esta janela ou pressione Ctrl+C.", flush=True)
            webbrowser.open(url)
            wait_until_interrupted(thread)
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def port_number(text):
    try:
        value = int(text)
    except ValueError:
        value = -1
    if not 0 <= value <= 65535:
        raise argparse.ArgumentTypeError("use um número entre 0 e 65535")
    return value


def build_parser():
    parser = argparse.ArgumentParser(
        prog="osintbr",
        description="Laboratório OSINT Brasil Flow: casos, grafo e evidências com hash, no seu computador.",
    )
    parser.add_argument("--port", type=port_number, default=8000, help="porta local preferida (padrão: 8000; outra livre se ocupada)")
    parser.add_argument("--data-dir", type=Path, help="pasta dos casos (padrão: pasta de dados do usuário)")
    parser.add_argument("--frontend", type=Path, help=argparse.SUPPRESS)
    shown = parser.add_mutually_exclusive_group()
    shown.add_argument("--janela", action="store_true", help="abrir em janela própria (requer pywebview; padrão no aplicativo)")
    shown.add_argument("--navegador", action="store_true", help="abrir no navegador (padrão no comando instalado)")
    shown.add_argument("--no-browser", action="store_true", help="não abrir janela nem navegador")
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
    mode = interface(args)
    webview = load_webview() if mode == "janela" else None
    if mode == "janela" and webview is None:
        hint = "" if frozen() else " (requer o extra janela: pywebview)"
        print(f"Janela própria indisponível{hint}; abrindo no navegador.", flush=True)
        mode = "navegador"
    import uvicorn

    from .lab import create_app

    health = f"http://{HOST}:{port}/health"
    server = uvicorn.Server(uvicorn.Config(create_app(), host=HOST, port=port, log_level="warning", access_log=False))
    print(f"Casos guardados em: {os.environ['OSINTBR_DB']}", flush=True)
    try:
        if mode == "janela":
            serve_in_window(server, url, health, webview)
        else:
            threading.Thread(target=wait_and_open, args=(url, health, mode == "navegador"), daemon=True).start()
            server.run()
    except KeyboardInterrupt:
        # Ctrl+C: uvicorn (or serve_in_window) already stopped the server; no traceback.
        pass
    print("Laboratório encerrado.", flush=True)


if __name__ == "__main__":
    main()
