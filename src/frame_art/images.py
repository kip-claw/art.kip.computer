"""Dependency-free image checks for the Frame's 16:9 display."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class UnsupportedImageError(ValueError):
    """Raised when an image is not a readable JPEG or PNG."""


@dataclass(frozen=True)
class ImagePreflight:
    """Facts and warnings collected before an image is sent to the television."""

    path: Path
    format: str
    width: int
    height: int
    byte_size: int
    warnings: tuple[str, ...]

    @property
    def is_16_by_9(self) -> bool:
        """Return whether the image exactly fills a 16:9 frame without cropping."""
        return self.width * 9 == self.height * 16


def inspect_image(path: Path) -> ImagePreflight:
    """Read basic dimensions and provide non-blocking Frame-specific warnings."""
    data = path.read_bytes()
    image_format, width, height = _dimensions(data)
    warnings: list[str] = []
    if width * 9 != height * 16:
        warnings.append("Image is not 16:9; the television may crop or letterbox it.")
    if width < 3840 or height < 2160:
        warnings.append(
            "Image is smaller than 3840×2160; it may be upscaled on the TV."
        )
    return ImagePreflight(path, image_format, width, height, len(data), tuple(warnings))


def _dimensions(data: bytes) -> tuple[str, int, int]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return "png", width, height
    if data.startswith(b"\xff\xd8"):
        return "jpeg", *_jpeg_dimensions(data)
    raise UnsupportedImageError("Only JPEG and PNG images are supported.")


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    position = 2
    while position + 9 < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        marker = data[position + 1]
        position += 2
        while marker == 0xFF and position < len(data):
            marker = data[position]
            position += 1
        if marker in {0xD8, 0xD9}:
            continue
        if position + 2 > len(data):
            break
        length = struct.unpack(">H", data[position : position + 2])[0]
        if length < 2 or position + length > len(data):
            break
        if marker in {
            *range(0xC0, 0xC4),
            *range(0xC5, 0xC8),
            *range(0xC9, 0xCC),
            *range(0xCD, 0xD0),
        }:
            height, width = struct.unpack(">HH", data[position + 3 : position + 7])
            return width, height
        position += length
    raise UnsupportedImageError("Could not read JPEG dimensions.")
