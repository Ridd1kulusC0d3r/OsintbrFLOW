"""`osintbr` command: data folder, port choice and local-only configuration."""

import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from osintbr import cli
from osintbr.lab import create_app


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("OSINTBR_HOME", "OSINTBR_DB", "OSINTBR_FRONTEND", "OSINTBR_PORT",
                 "OSINTBR_PROXY_ORIGIN", "OSINTBR_COLAB_TOKEN", "XDG_DATA_HOME", "APPDATA"):
        # setenv first so pytest restores the original state after each test,
        # even for variables that configure() writes directly.
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


@pytest.mark.parametrize("platform,expected", [
    ("win32", Path("AppData/Roaming/OsintbrFLOW")),
    ("darwin", Path("Library/Application Support/OsintbrFLOW")),
    ("linux", Path(".local/share/osintbrflow")),
])
def test_data_dir_follows_os_convention(monkeypatch, tmp_path, platform, expected):
    monkeypatch.setattr(cli.sys, "platform", platform)
    monkeypatch.setattr(cli.Path, "home", lambda: tmp_path)
    assert cli.data_dir() == tmp_path / expected


def test_data_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv("OSINTBR_HOME", str(tmp_path / "casos"))
    assert cli.data_dir() == tmp_path / "casos"


def test_busy_port_falls_back_to_a_free_one():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        taken = busy.getsockname()[1]
        chosen = cli.free_port(taken)
    assert chosen != taken and 0 < chosen < 65536


def frontend(tmp_path):
    folder = tmp_path / "static"
    folder.mkdir()
    (folder / "brasil.html").write_text("<html>OSINT Brasil Flow</html>")
    return folder


def test_configure_is_local_only_and_drops_proxy_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("OSINTBR_PROXY_ORIGIN", "https://example.test")
    monkeypatch.setenv("OSINTBR_COLAB_TOKEN", "x" * 40)
    args = cli.build_parser().parse_args(["--data-dir", str(tmp_path / "d"), "--frontend", str(frontend(tmp_path)), "--port", "0"])
    port, url = cli.configure(args)
    assert url == f"http://127.0.0.1:{port}/brasil.html"
    assert cli.os.environ["OSINTBR_DB"] == str(tmp_path / "d" / "brasil.sqlite3")
    assert "OSINTBR_PROXY_ORIGIN" not in cli.os.environ
    assert "OSINTBR_COLAB_TOKEN" not in cli.os.environ
    client = TestClient(create_app(), base_url=f"http://127.0.0.1:{port}")
    assert client.get("/health").json()["mode"] == "local-only"
    assert client.get("/brasil.html").status_code == 200
    ok = client.post("/api/brasil/cases", headers={"Origin": f"http://127.0.0.1:{port}"},
                     json={"title": "CLI", "purpose": "Testar o comando"})
    assert ok.status_code == 201
    other = client.post("/api/brasil/cases", headers={"Origin": "http://127.0.0.1:1"},
                        json={"title": "CLI", "purpose": "Testar o comando"})
    assert other.status_code == 403
    assert client.get("/health", headers={"Host": "attacker.test"}).status_code == 403


def test_missing_panel_gives_build_instructions(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "frontend_dir", lambda explicit=None: None)
    args = cli.build_parser().parse_args(["--data-dir", str(tmp_path)])
    with pytest.raises(SystemExit, match="build:brasil"):
        cli.configure(args)


@pytest.mark.parametrize("port", ["abc", "0", "70000", "-1"])
def test_invalid_port_env_is_rejected(monkeypatch, port):
    monkeypatch.setenv("OSINTBR_PORT", port)
    with pytest.raises(ValueError):
        create_app()


def test_parser_has_no_option_to_expose_the_lab():
    options = {o for action in cli.build_parser()._actions for o in action.option_strings}
    assert not options & {"--host", "--bind", "--public"}


# --- Janela própria (pywebview opcional), sem precisar de tela -------------

class FakeServer:
    """Stands in for uvicorn.Server: runs until should_exit, records the lifecycle."""

    def __init__(self):
        self.should_exit = False
        self.started = cli.threading.Event()
        self.stopped = cli.threading.Event()

    def run(self):
        self.started.set()
        while not self.should_exit:
            cli.time.sleep(0.01)
        self.stopped.set()


class FakeWebview:
    def __init__(self, fail=None):
        self.fail = fail
        self.windows = []
        self.server_alive_while_open = None

    def create_window(self, title, url, **kwargs):
        self.windows.append((title, url))

    def start(self, server=None):
        if self.fail:
            raise self.fail
        # The window is "open" here; the server must be serving meanwhile.
        self.server_alive_while_open = server.started.is_set() and not server.should_exit


def args(*argv):
    return cli.build_parser().parse_args(list(argv))


def test_interface_defaults(monkeypatch):
    monkeypatch.delattr(cli.sys, "frozen", raising=False)
    assert cli.interface(args()) == "navegador"
    assert cli.interface(args("--janela")) == "janela"
    assert cli.interface(args("--no-browser")) == "nenhuma"
    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    assert cli.interface(args()) == "janela"
    assert cli.interface(args("--navegador")) == "navegador"
    assert cli.interface(args("--no-browser")) == "nenhuma"


def test_window_options_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        args("--janela", "--navegador")


def test_closing_the_window_stops_the_server(monkeypatch):
    server = FakeServer()
    webview = FakeWebview()
    monkeypatch.setattr(cli, "wait_ready", lambda health, timeout=30: True)
    monkeypatch.setattr(webview, "start", lambda: FakeWebview.start(webview, server))
    cli.serve_in_window(server, "http://127.0.0.1:1/brasil.html", "http://127.0.0.1:1/health", webview)
    assert webview.windows == [("OSINT Brasil Flow", "http://127.0.0.1:1/brasil.html")]
    assert webview.server_alive_while_open is True
    assert server.should_exit and server.stopped.is_set()


def test_window_failure_falls_back_to_browser(monkeypatch, capsys):
    server = FakeServer()
    opened = []
    monkeypatch.setattr(cli, "wait_ready", lambda health, timeout=30: True)
    monkeypatch.setattr(cli.webbrowser, "open", opened.append)
    # Simulate the user pressing Ctrl+C while the browser fallback is serving.
    def interrupted(thread):
        assert thread.is_alive()
    monkeypatch.setattr(cli, "wait_until_interrupted", interrupted)
    cli.serve_in_window(server, "http://127.0.0.1:1/brasil.html", "h", FakeWebview(fail=RuntimeError("sem GUI")))
    assert opened == ["http://127.0.0.1:1/brasil.html"]
    assert "abrindo no navegador" in capsys.readouterr().out
    assert server.stopped.is_set()


def test_server_that_never_answers_is_still_stopped(monkeypatch):
    server = FakeServer()
    webview = FakeWebview()
    monkeypatch.setattr(cli, "wait_ready", lambda health, timeout=30: False)
    cli.serve_in_window(server, "u", "h", webview)
    assert webview.windows == [] and server.stopped.is_set()


def test_main_without_pywebview_uses_browser(monkeypatch, tmp_path, capsys):
    import uvicorn

    monkeypatch.setattr(cli, "load_webview", lambda: None)
    started = []

    class Server:
        def __init__(self, config):
            assert config.host == "127.0.0.1"
            started.append(config.port)

        def run(self):
            pass

    monkeypatch.setattr(uvicorn, "Server", Server)
    monkeypatch.setattr(cli.threading, "Thread", lambda **kw: type("T", (), {"start": lambda self: None})())
    cli.main(["--janela", "--data-dir", str(tmp_path / "d"), "--frontend", str(frontend(tmp_path)), "--port", "0"])
    assert started
    assert "Janela própria indisponível" in capsys.readouterr().out


def test_main_with_pywebview_opens_window(monkeypatch, tmp_path):
    import uvicorn

    webview = FakeWebview()
    calls = []
    monkeypatch.setattr(cli, "load_webview", lambda: webview)
    monkeypatch.setattr(uvicorn, "Server", lambda config: FakeServer())
    monkeypatch.setattr(cli, "serve_in_window", lambda server, url, health, wv: calls.append((url, wv)))
    cli.main(["--janela", "--data-dir", str(tmp_path / "d"), "--frontend", str(frontend(tmp_path)), "--port", "0"])
    assert calls and calls[0][1] is webview and calls[0][0].startswith("http://127.0.0.1:")


def test_load_webview_handles_missing_module(monkeypatch):
    monkeypatch.setitem(cli.sys.modules, "webview", None)
    assert cli.load_webview() is None


def test_load_webview_handles_broken_module(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def broken(name, *a, **kw):
        if name == "webview":
            raise OSError("runtime nativo ausente")
        return real_import(name, *a, **kw)

    monkeypatch.delitem(cli.sys.modules, "webview", raising=False)
    monkeypatch.setattr(builtins, "__import__", broken)
    assert cli.load_webview() is None
