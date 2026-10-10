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
