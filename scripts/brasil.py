#!/usr/bin/env python3
"""Cross-platform launcher for the portable Brazil laboratory."""

import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
os.chdir(root)
if not (root / "flowsint-app/dist/brasil.html").exists():
    raise SystemExit(
        "Compile o frontend primeiro: npm install --legacy-peer-deps && npm run build --workspace flowsint-app"
    )
env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join(
    str(root / p) for p in ["flowsint-types/src", "flowsint-core/src"]
)
raise SystemExit(
    subprocess.call(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "osintbr.lab:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        env=env,
    )
)
