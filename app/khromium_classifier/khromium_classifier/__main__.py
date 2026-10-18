# Copyright 2026 Khromium. All rights reserved.
# Proprietary commercial software. See LICENSE.khromium at the repo root.

import argparse
import json
import os
import sys

from khromium_classifier.heuristics import local_decision
from khromium_classifier.license_key import mint
from khromium_classifier.provider import classify_live
from khromium_classifier.server import serve


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Khromium companion. Classifies pasted DOM without rebuilding Chromium."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve_parser = sub.add_parser("serve", help="Run the local web UI and AI proxy")
    serve_parser.add_argument("--port", type=int, default=8765)

    classify_parser = sub.add_parser("classify", help="Classify an HTML file")
    classify_parser.add_argument("--html", required=True)
    classify_parser.add_argument("--provider", default="openai")
    classify_parser.add_argument(
        "--live",
        action="store_true",
        help="Dev-only direct provider call. Requires KHROMIUM_ALLOW_BYO_KEY=1.",
    )

    mint_parser = sub.add_parser("mint", help="Mint a KHRO1 license token")
    mint_parser.add_argument("--plan", required=True, choices=["browser", "ai_monthly"])
    mint_parser.add_argument("--subject", required=True)
    mint_parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="ai_monthly period in days. Default is 31. Ignored for browser.",
    )

    args = parser.parse_args(argv)
    if args.command == "serve":
        serve(args.port)
        return 0
    if args.command == "mint":
        print(mint(args.plan, args.subject, days=args.days))
        return 0
    try:
        html = open(args.html, encoding="utf-8").read()
    except OSError as exc:
        print(exc, file=sys.stderr)
        return 2
    if args.live:
        if os.environ.get("KHROMIUM_ALLOW_BYO_KEY") != "1":
            print(
                "Direct provider calls are dev-only. Set KHROMIUM_ALLOW_BYO_KEY=1. "
                "Paid AI uses the Khromium proxy, which holds the provider key.",
                file=sys.stderr,
            )
            return 2
        decision = classify_live(args.provider, html)
    else:
        decision = local_decision(html)
    print(json.dumps(decision, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
