#!/usr/bin/env python
"""Manual smoke test: one live vision API call against a real image.

Not part of the pytest suite — SPEC.md Phase 3 keeps automated tests free
of live API calls. Run directly:

    ANTHROPIC_API_KEY=sk-... python scripts/smoke_extract.py path/to/label.jpg
"""

import json
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from extraction import ExtractionError, VisionExtractor, needs_better_image  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/smoke_extract.py <path-to-image>", file=sys.stderr)
        return 2

    image_path = Path(sys.argv[1])
    if not image_path.is_file():
        print(f"No such file: {image_path}", file=sys.stderr)
        return 2

    media_type, _ = mimetypes.guess_type(image_path.name)
    if media_type not in ("image/jpeg", "image/png", "image/webp"):
        print(f"Unsupported or undetected image type: {media_type}", file=sys.stderr)
        return 2

    try:
        extractor = VisionExtractor()
        result = extractor.extract(image_path.read_bytes(), media_type=media_type)
    except ExtractionError as exc:
        print(f"Extraction failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.model_dump(), indent=2))
    print(
        f"\nneeds_better_image: {needs_better_image(result)} "
        f"(legibility: {result.government_warning.legibility})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
