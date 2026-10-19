# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

"""Public download site for paid Khromium Shield."""

import sys
from pathlib import Path

_CLASSIFIER = Path(__file__).resolve().parents[2] / "khromium_classifier"
if _CLASSIFIER.is_dir() and str(_CLASSIFIER) not in sys.path:
    sys.path.insert(0, str(_CLASSIFIER))

__version__ = "1.0.0"
