#!/usr/bin/env python3
"""Verify an exported evidence bundle offline."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(root / "flowsint-core/src"), str(root / "flowsint-types/src")]
from osintbr.store import verify  # noqa: E402 - local source roots are set above

if len(sys.argv) != 2:
    raise SystemExit("Uso: python scripts/verify-bundle.py arquivo.json")
result = verify(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["valid"] else 1)
