"""Owner-isolated SQLite evidence store, serialized append and portable integrity checks."""

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .engine import compare, project
from .providers import canonical, now


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def verify(bundle):
    errors = []
    if bundle.get("schema") != "osintbrflow.bundle.v1":
        return {"valid": False, "errors": ["Schema desconhecido."]}
    body = {k: v for k, v in bundle.items() if k != "checksum"}
    if digest(body) != bundle.get("checksum"):
        errors.append("Checksum do pacote diverge.")
    previous = "0" * 64
    for run in bundle.get("runs", []):
        if project(run.get("evidence", [])) != run.get("graph"):
            errors.append(f"Grafo difere das evidências: {run.get('id')}")
        unsigned = {k: v for k, v in run.items() if k != "chain_hash"}
        if run.get("previous_hash") != previous or digest(unsigned) != run.get(
            "chain_hash"
        ):
            errors.append(f"Cadeia inválida: {run.get('id')}")
        previous = run.get("chain_hash")
        for e in run.get("evidence", []):
            if e.get("status") == "ok":
                if hashlib.sha256(e.get("raw", "").encode()).hexdigest() != e.get(
                    "sha256"
                ):
                    errors.append(f"Conteúdo alterado: {e.get('id')}")
                try:
                    if json.loads(e["raw"]) != e["data"]:
                        errors.append(f"Projeção divergente: {e.get('id')}")
                except (ValueError, KeyError):
                    errors.append("Conteúdo inválido.")
    if previous != bundle.get("head_hash"):
        errors.append("Cabeça da cadeia diverge.")
    return {
        "valid": not errors,
        "errors": errors,
        "runs": len(bundle.get("runs", [])),
        "note": "Integridade local; hash não comprova veracidade, autoria ou cadeia de custódia jurídica.",
    }


class Store:
    def __init__(self, path=None):
        self.path = path or os.getenv("OSINTBR_DB", "data/brasil.sqlite3")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL, purpose TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, case_id TEXT NOT NULL REFERENCES cases(id), payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS runs_case ON runs(case_id,seq);
            CREATE INDEX IF NOT EXISTS cases_owner ON cases(owner);""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, owner, title, purpose):
        item = {
            "id": str(uuid.uuid4()),
            "title": title,
            "purpose": purpose,
            "created_at": now(),
        }
        with self.connect() as db:
            db.execute(
                "INSERT INTO cases VALUES (?,?,?,?,?)",
                (item["id"], owner, title, purpose, item["created_at"]),
            )
        return item

    def list(self, owner):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,title,purpose,created_at FROM cases WHERE owner=? ORDER BY created_at DESC",
                    (owner,),
                )
            ]

    def get(self, owner, case_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT id,title,purpose,created_at FROM cases WHERE owner=? AND id=?",
                (owner, case_id),
            ).fetchone()
            if not row:
                raise KeyError("Caso não encontrado.")
            runs = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM runs WHERE case_id=? ORDER BY seq", (case_id,)
                )
            ]
        return {**dict(row), "runs": runs}

    def append(self, owner, case_id, run):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute(
                "SELECT id FROM cases WHERE id=? AND owner=?", (case_id, owner)
            ).fetchone():
                raise KeyError("Caso não encontrado.")
            previous = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM runs WHERE case_id=? ORDER BY seq", (case_id,)
                )
            ]
            baseline = next(
                (
                    r
                    for r in reversed(previous)
                    if r["seed"] == run["seed"]
                    and r["mode"] == run["mode"]
                    and r["steps"] == run["steps"]
                    and r["status"] == "complete"
                ),
                None,
            )
            run["baseline_id"] = (
                baseline["id"] if baseline and run["status"] == "complete" else None
            )
            run["changes"] = (
                compare(baseline["graph"], run["graph"]) if run["baseline_id"] else []
            )
            run["case_id"] = case_id
            run["previous_hash"] = previous[-1]["chain_hash"] if previous else "0" * 64
            run["chain_hash"] = digest(run)
            db.execute(
                "INSERT INTO runs(id,case_id,payload) VALUES (?,?,?)",
                (run["id"], case_id, canonical(run)),
            )
        return run

    def export(self, owner, case_id):
        case = self.get(owner, case_id)
        runs = case.pop("runs")
        body = {
            "schema": "osintbrflow.bundle.v1",
            "case": case,
            "runs": runs,
            "head_hash": runs[-1]["chain_hash"] if runs else "0" * 64,
        }
        return {**body, "checksum": digest(body)}
