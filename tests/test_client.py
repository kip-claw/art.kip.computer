"""Tests for explicit TV interactions using a mocked connection."""

from pathlib import Path

import pytest

from frame_art.client import FrameArtClient


class FakeArtConnection:
    def __init__(self):
        self.calls = []

    def open(self):
        self.calls.append("open")

    def close(self):
        self.calls.append("close")

    def get_device_info(self):
        self.calls.append("get_device_info")
        return {"name": "The Frame"}

    def get_artmode(self):
        self.calls.append("get_artmode")
        return "on"

    def upload(self, file, matte, file_type):
        self.calls.append(("upload", file, matte, file_type))
        return "MY_F0001"

    def select_image(self, content_id, show=True):
        self.calls.append(("select_image", content_id, show))


@pytest.mark.unit
def test_doctor_only_reads_tv_state():
    connection = FakeArtConnection()

    result = FrameArtClient(connection).doctor()

    assert result == {"device": {"name": "The Frame"}, "art_mode": "on"}
    assert connection.calls == ["open", "get_device_info", "get_artmode", "close"]


@pytest.mark.unit
def test_upload_does_not_select_the_new_image():
    connection = FakeArtConnection()

    content_id = FrameArtClient(connection).upload(Path("art.jpg"), matte="none")

    assert content_id == "MY_F0001"
    assert connection.calls == [
        "open",
        ("upload", "art.jpg", "none", "jpg"),
        "close",
    ]


@pytest.mark.unit
def test_display_selects_only_the_requested_content_id():
    connection = FakeArtConnection()

    FrameArtClient(connection).display("MY_F0001")

    assert connection.calls == [
        "open",
        ("select_image", "MY_F0001", True),
        "close",
    ]
