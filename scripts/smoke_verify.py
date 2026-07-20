#!/usr/bin/env python
"""Manual smoke test: hits a running server's POST /api/verify with a real
image. Complements scripts/smoke_extract.py (which calls the vision API
directly) by proving the whole HTTP pipeline end-to-end.

Not part of the pytest suite. Start the server first:

    cd backend && uvicorn app:app --reload

Then:

    python scripts/smoke_verify.py path/to/label.jpg \
        --brand-name "Old Tom Distillery" \
        --class-type "Kentucky Straight Bourbon Whiskey" \
        --alcohol-content 45 \
        --net-contents "750 mL" \
        --beverage-type distilled_spirits
"""

import argparse
import json
import mimetypes
import sys
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test POST /api/verify against a running server.")
    parser.add_argument("image", type=Path, help="Path to a label image (JPEG/PNG).")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the running server.")
    parser.add_argument("--brand-name", default="Old Tom Distillery")
    parser.add_argument("--class-type", default="Kentucky Straight Bourbon Whiskey")
    parser.add_argument("--alcohol-content", default="45")
    parser.add_argument("--net-contents", default="750 mL")
    parser.add_argument(
        "--beverage-type", default="distilled_spirits",
        choices=["distilled_spirits", "wine", "beer"],
    )
    args = parser.parse_args()

    if not args.image.is_file():
        print(f"No such file: {args.image}", file=sys.stderr)
        return 2

    media_type, _ = mimetypes.guess_type(args.image.name)
    if media_type not in ("image/jpeg", "image/png", "image/webp"):
        print(f"Unsupported or undetected image type: {media_type}", file=sys.stderr)
        return 2

    form_data = {
        "brand_name": args.brand_name,
        "class_type": args.class_type,
        "alcohol_content": args.alcohol_content,
        "net_contents": args.net_contents,
        "beverage_type": args.beverage_type,
    }

    with httpx.Client(timeout=30.0) as client:
        try:
            health = client.get(f"{args.url}/api/health")
        except httpx.ConnectError:
            print(f"Could not reach {args.url} — is the server running?", file=sys.stderr)
            return 2
        print(f"health: {health.status_code} {health.json()}", file=sys.stderr)

        response = client.post(
            f"{args.url}/api/verify",
            data=form_data,
            files={"image": (args.image.name, args.image.read_bytes(), media_type)},
        )

    print(f"\nPOST /api/verify -> {response.status_code}", file=sys.stderr)
    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text)

    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
