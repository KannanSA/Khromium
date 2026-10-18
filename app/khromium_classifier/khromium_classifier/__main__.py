# Copyright 2026 The Khromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
import sys

from khromium_classifier.heuristics import local_decision
from khromium_classifier.provider import classify_live
from khromium_classifier.server import serve


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Khromium companion. Classifies pasted DOM without rebuilding Chromium."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve_parser = sub.add_parser("serve", help="Run the local web UI")
    serve_parser.add_argument("--port", type=int, default=8765)

    classify_parser = sub.add_parser("classify", help="Classify an HTML file")
    classify_parser.add_argument("--html", required=True)
    classify_parser.add_argument("--provider", default="openai")
    classify_parser.add_argument(
        "--live",
        action="store_true",
        help="Call OpenAI or Grok. Requires KHROMIUM_OPENAI_API_KEY or KHROMIUM_XAI_API_KEY.",
    )

    args = parser.parse_args(argv)
    if args.command == "serve":
        serve(args.port)
        return 0
    try:
        html = open(args.html, encoding="utf-8").read()
    except OSError as exc:
        print(exc, file=sys.stderr)
        return 2
    if args.live:
        decision = classify_live(args.provider, html)
    else:
        decision = local_decision(html)
    print(json.dumps(decision, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
