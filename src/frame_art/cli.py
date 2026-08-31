"""Command-line interface for careful, manual Frame Art Mode experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

from samsungtvws import SamsungTVArt

from .client import FrameArtClient
from .images import ImagePreflight, inspect_image

if TYPE_CHECKING:
    from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manual Samsung The Frame Art Mode POC"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "upload", "display"):
        command = subparsers.add_parser(name)
        command.add_argument(
            "--host", required=True, help="LAN IP address or hostname of the TV"
        )
        command.add_argument(
            "--token-file", type=Path, default=Path(".frame-art-token")
        )
    upload = subparsers.choices["upload"]
    upload.add_argument("image", type=Path)
    upload.add_argument("--matte", default="none")
    upload.add_argument(
        "--dry-run", action="store_true", help="Inspect only; never connects to the TV"
    )
    upload.add_argument(
        "--confirm-upload", action="store_true", help="Required before uploading"
    )
    display = subparsers.choices["display"]
    display.add_argument("content_id")
    display.add_argument(
        "--confirm-display",
        action="store_true",
        help="Required before changing the display",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "upload":
        preflight = inspect_image(args.image)
        print(json.dumps(_preflight_json(preflight), indent=2))
        if args.dry_run:
            return 0
        if not args.confirm_upload:
            raise SystemExit(
                "Refusing upload: rerun with --confirm-upload after reviewing preflight."
            )
        content_id = _client(args).upload(args.image, matte=args.matte)
        print(f"Uploaded. content_id: {content_id}")
        return 0
    if args.command == "display":
        if not args.confirm_display:
            raise SystemExit("Refusing display change: rerun with --confirm-display.")
        _client(args).display(args.content_id)
        print(f"Displaying {args.content_id} in Art Mode.")
        return 0
    print(json.dumps(_client(args).doctor(), indent=2, default=str))
    return 0


def _client(args: argparse.Namespace) -> FrameArtClient:
    return FrameArtClient(SamsungTVArt(host=args.host, token_file=str(args.token_file)))


def _preflight_json(preflight: ImagePreflight) -> dict[str, object]:
    return {
        "path": str(preflight.path),
        "format": preflight.format,
        "width": preflight.width,
        "height": preflight.height,
        "byte_size": preflight.byte_size,
        "warnings": preflight.warnings,
    }


if __name__ == "__main__":
    raise SystemExit(main())
