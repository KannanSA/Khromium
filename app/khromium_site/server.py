#!/usr/bin/env python3
# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""Run from anywhere: python3 app/khromium_site/server.py"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_CLASSIFIER = _ROOT.parent / "khromium_classifier"
for _path in (_CLASSIFIER, _ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from khromium_site.server import main

if __name__ == "__main__":
    raise SystemExit(main())
