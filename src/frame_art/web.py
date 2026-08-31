"""Tailnet-facing curator application, intentionally narrow and confirm-first."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from samsungtvws import SamsungTVArt

from .catalog import Catalog
from .client import FrameArtClient

ClientFactory = Callable[[], FrameArtClient]


def create_app(
    catalog: Catalog | None = None, client_factory: ClientFactory | None = None
) -> FastAPI:
    """Create the app; injected dependencies keep TV operations testable."""
    catalogue = catalog or Catalog(
        Path(os.environ.get("FRAME_ART_DATA_DIR", "frame-art-data"))
    )
    make_client = client_factory or _client_from_environment
    app = FastAPI(title="Frame Art", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/artworks")
    def artworks() -> list[dict[str, object]]:
        return [artwork.json() for artwork in catalogue.artworks()]

    @app.post("/api/artworks")
    async def add_artwork(file: Annotated[UploadFile, File()]) -> dict[str, object]:
        try:
            return catalogue.add(await file.read(), file.filename or "artwork").json()
        except Exception as error:
            raise HTTPException(400, f"Could not prepare artwork: {error}") from error

    @app.post("/api/artworks/{identifier}/upload-to-tv")
    def upload_to_tv(identifier: str, confirm: bool = False) -> dict[str, str]:
        _require_confirmation(confirm, "upload")
        try:
            content_id = make_client().upload(catalogue.render_path(identifier))
            catalogue.set_tv_content_id(identifier, content_id)
        except KeyError as error:
            raise HTTPException(404, "Artwork not found.") from error
        return {"content_id": content_id}

    @app.post("/api/artworks/{identifier}/display")
    def display(identifier: str, confirm: bool = False) -> dict[str, str]:
        _require_confirmation(confirm, "display")
        try:
            artwork = catalogue.get(identifier)
            if artwork.tv_content_id is None:
                raise HTTPException(409, "Upload this artwork to the TV first.")
            make_client().display(artwork.tv_content_id)
            catalogue.mark_displayed(identifier)
        except KeyError as error:
            raise HTTPException(404, "Artwork not found.") from error
        return {"status": "displayed"}

    @app.post("/api/rollback")
    def rollback(confirm: bool = False) -> dict[str, str]:
        _require_confirmation(confirm, "rollback")
        artwork = catalogue.rollback_target()
        if artwork is None or artwork.tv_content_id is None:
            raise HTTPException(409, "No previous display is available.")
        make_client().display(artwork.tv_content_id)
        catalogue.mark_displayed(artwork.id)
        return {"status": "rolled back"}

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        cards = (
            "".join(
                f"<li><b>{art.filename}</b> — {art.width}×{art.height} — {art.tv_content_id or 'not on TV'}</li>"
                for art in catalogue.artworks()
            )
            or "<li>No art yet.</li>"
        )
        return f"""<!doctype html><title>Frame Art</title><h1>Frame Art</h1>
<p>Private NAS curator. Uploading or displaying requires explicit API confirmation.</p>
<form action='/api/artworks' method='post' enctype='multipart/form-data'><input name='file' type='file' accept='image/jpeg,image/png' required><button>Prepare artwork</button></form>
<h2>Catalogue</h2><ul>{cards}</ul>"""

    return app


def _require_confirmation(confirm: bool, operation: str) -> None:
    if not confirm:
        raise HTTPException(409, f"Refusing {operation}; repeat with confirm=true.")


def _client_from_environment() -> FrameArtClient:
    host = os.environ.get("FRAME_ART_TV_HOST")
    if not host:
        raise HTTPException(503, "FRAME_ART_TV_HOST is not configured.")
    token = Path(os.environ.get("FRAME_ART_TOKEN_FILE", "/data/state/samsung-token"))
    return FrameArtClient(SamsungTVArt(host=host, token_file=str(token)))


app = create_app()
