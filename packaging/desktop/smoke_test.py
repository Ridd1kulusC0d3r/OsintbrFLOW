"""Teste de fumaça do aplicativo de desktop, sem tela e sem rede externa.

Só biblioteca padrão; roda igual no Windows, macOS e Linux, localmente e no CI.

    python packaging/desktop/smoke_test.py packaging/desktop/dist/OsintbrFLOW/OsintbrFLOW

Também aceita um comando instalado, por exemplo: smoke_test.py osintbr

Verifica: partida a frio até /health responder, criação de caso com a
Origin correta, rota demonstrativa CNPJ→CEP→município com três evidências
"ok", recusa (422) de semente com formato de CPF, banco gravado na pasta
indicada por OSINTBR_HOME e encerramento limpo.
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

SYNTHETIC_CPF = "52998224725"  # CPF sintético, documentado publicamente para testes


def request(method, url, origin=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, decode(response)
    except urllib.error.HTTPError as error:
        return error.code, decode(error)


def decode(response):
    raw = response.read()
    if "json" in response.headers.get("content-type", ""):
        return json.loads(raw or b"null")
    return raw.decode("utf-8", "replace")


def check(condition, message):
    if not condition:
        raise SystemExit(f"FALHOU: {message}")
    print(f"ok  {message}")


def main(argv=None):
    # Console do Windows no CI pode não ser UTF-8; não quebrar por causa de "→".
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        raise SystemExit(__doc__)
    # which() returns relative paths unchanged; the app runs with another cwd.
    executable = str(Path(shutil.which(argv[0]) or argv[0]).resolve())
    home = Path(tempfile.mkdtemp(prefix="osintbr-smoke-"))
    env = dict(os.environ, OSINTBR_HOME=str(home), PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    for name in ("OSINTBR_DB", "OSINTBR_FRONTEND", "OSINTBR_PROXY_ORIGIN", "OSINTBR_COLAB_TOKEN"):
        env.pop(name, None)
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" else {}

    started = time.perf_counter()
    process = subprocess.Popen(
        [executable, "--no-browser", "--port", "0"], env=env, cwd=home,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", **flags,
    )
    lines = []
    ready = threading.Event()

    def read_output():
        for line in process.stdout:
            lines.append(line.rstrip())
            print(f"    | {line.rstrip()}")
            if "pronto em" in line:
                ready.set()

    threading.Thread(target=read_output, daemon=True).start()
    try:
        if not ready.wait(120):
            raise SystemExit("FALHOU: o aplicativo não ficou pronto em 120 s")
        cold_start = time.perf_counter() - started
        url = next(re.search(r"http://127\.0\.0\.1:\d+", l).group(0) for l in lines if "pronto em" in l)
        print(f"ok  partida a frio: {cold_start:.2f} s ({url})")

        status, body = request("GET", url + "/health")
        check(status == 200 and body["mode"] == "local-only", "/health responde em modo local-only")
        status, _ = request("GET", url + "/brasil.html")
        check(status == 200, "painel servido")

        status, case = request("POST", url + "/api/brasil/cases", origin=url,
                               body={"title": "Fumaça", "purpose": "Teste do aplicativo de desktop"})
        check(status == 201, "caso criado com a Origin correta")
        status, _ = request("POST", url + "/api/brasil/cases", origin="http://127.0.0.1:1",
                            body={"title": "Fumaça", "purpose": "Origem estranha"})
        check(status == 403, "Origin diferente recusada (403)")

        runs = f"{url}/api/brasil/cases/{case['id']}/runs"
        status, run = request("POST", runs, origin=url, body={
            "seed_kind": "cnpj", "seed": "11222333000181", "steps": ["cnpj", "cep", "municipio"], "mode": "demo"})
        evidence = run.get("evidence", []) if isinstance(run, dict) else []
        check(status == 200 and len(evidence) == 3 and all(e["status"] == "ok" for e in evidence),
              "rota demonstrativa CNPJ→CEP→município com 3 evidências ok")

        status, body = request("POST", runs, origin=url, body={
            "seed_kind": "cnpj", "seed": SYNTHETIC_CPF, "steps": ["cnpj"], "mode": "demo"})
        check(status == 422 and "CPF" in str(body), "semente com formato de CPF recusada (422)")

        status, bundle = request("GET", f"{url}/api/brasil/cases/{case['id']}/export")
        check(status == 200 and len(bundle["runs"]) == 1, "exportação do caso com 1 coleta")

        database = home / "brasil.sqlite3"
        check(database.exists(), f"banco gravado na pasta do usuário ({database})")
    finally:
        if process.poll() is None:
            if sys.platform == "win32":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.send_signal(signal.SIGINT)
            try:
                process.wait(15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise SystemExit("FALHOU: o aplicativo não encerrou em 15 s")
        shutil.rmtree(home, ignore_errors=True)
    check(not any("Traceback" in l for l in lines), "nenhum erro no registro do aplicativo")
    if sys.platform == "win32":
        # Ctrl+Break: o uvicorn encerra limpo e depois repassa o sinal ao
        # Windows, que finaliza o processo com código diferente de zero.
        print(f"ok  encerrado (código {process.returncode})")
    else:
        check(process.returncode == 0 and any("encerrado" in l for l in lines),
              f"encerrado sem erro (código {process.returncode})")
    print("TESTE DE FUMAÇA APROVADO")


if __name__ == "__main__":
    main()
