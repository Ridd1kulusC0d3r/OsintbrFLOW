#!/usr/bin/env python3
"""Launcher for a development checkout. Installed copies use the `osintbr` command."""

import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(root / "flowsint-types/src"), str(root / "flowsint-core/src")]

from osintbr.cli import main  # noqa: E402

main()
