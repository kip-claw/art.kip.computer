"""Small adapter around samsungtvws that keeps all mutating calls explicit."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path


class ArtConnection(Protocol):
    """The small portion of samsungtvws used by this proof of concept."""

    def open(self) -> object: ...
    def close(self) -> None: ...
    def get_device_info(self) -> dict[str, object]: ...
    def get_artmode(self) -> object: ...
    def upload(
        self,
        file: str,
        matte: str = "shadowbox_polar",
        portrait_matte: str = "shadowbox_polar",
        file_type: str = "png",
        date: str | None = None,
    ) -> str: ...
    def select_image(
        self,
        content_id: str,
        category: str | None = None,
        show: bool = True,
    ) -> object: ...


class FrameArtClient:
    """Connect to one TV and expose only the POC's required operations."""

    def __init__(self, connection: ArtConnection) -> None:
        self.connection = connection

    def doctor(self) -> dict[str, object]:
        """Check Art Mode connectivity without changing TV state."""
        self.connection.open()
        try:
            return {
                "device": self.connection.get_device_info(),
                "art_mode": self.connection.get_artmode(),
            }
        finally:
            self.connection.close()

    def upload(self, image: Path, *, matte: str = "none") -> str:
        """Upload an image, leaving the current display unchanged."""
        self.connection.open()
        try:
            return self.connection.upload(
                str(image), matte=matte, file_type=image.suffix[1:]
            )
        finally:
            self.connection.close()

    def display(self, content_id: str) -> None:
        """Make an already-uploaded image current in Art Mode."""
        self.connection.open()
        try:
            self.connection.select_image(content_id, show=True)
        finally:
            self.connection.close()
