"""Tests for image preflight checks."""

import struct

import pytest

from frame_art.images import UnsupportedImageError, inspect_image


@pytest.mark.unit
def test_inspect_png_reports_frame_ready_image(tmp_path):
    image = tmp_path / "art.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 3840, 2160))

    result = inspect_image(image)

    assert result.format == "png"
    assert result.is_16_by_9 is True
    assert result.warnings == ()


@pytest.mark.unit
def test_inspect_png_warns_about_cropping_and_upscale(tmp_path):
    image = tmp_path / "small.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 100, 100))

    result = inspect_image(image)

    assert result.is_16_by_9 is False
    assert len(result.warnings) == 2


@pytest.mark.unit
def test_inspect_image_rejects_unrecognised_format(tmp_path):
    image = tmp_path / "not-art.txt"
    image.write_text("nope", encoding="utf-8")

    with pytest.raises(UnsupportedImageError, match="JPEG and PNG"):
        inspect_image(image)
