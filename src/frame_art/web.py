"""Tailnet-facing curator application, intentionally narrow and confirm-first."""

from __future__ import annotations

import os
from html import escape
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from samsungtvws import SamsungTVArt

from .catalog import Artwork, Catalog
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

    @app.get("/artworks/{identifier}/preview")
    def artwork_preview(identifier: str) -> FileResponse:
        """Serve a Frame-ready preview to the private curator."""
        try:
            return FileResponse(catalogue.render_path(identifier), media_type="image/jpeg")
        except KeyError as error:
            raise HTTPException(404, "Artwork not found.") from error

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
        cards = "".join(_artwork_card(art) for art in catalogue.artworks())
        empty_state = "" if cards else _EMPTY_STATE
        return _PAGE.format(cards=cards, empty_state=empty_state)

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


def _artwork_card(artwork: Artwork) -> str:
    """Render safe, small metadata cards without trusting uploaded filenames."""
    identifier = escape(artwork.id, quote=True)
    filename = escape(artwork.filename)
    dimensions = f"{artwork.width} × {artwork.height}"
    state = "On Frame" if artwork.tv_content_id else "Ready to upload"
    state_class = "is-on-frame" if artwork.tv_content_id else "is-ready"
    return f"""
    <article class="art-card">
      <img src="/artworks/{identifier}/preview" alt="Preview of {filename}">
      <div class="art-card__body">
        <p class="eyebrow">{state}</p>
        <h3>{filename}</h3>
        <p class="art-card__meta">{dimensions} original · 3840 × 2160 Frame render</p>
        <span class="status {state_class}"><span></span>{state}</span>
      </div>
    </article>"""


_EMPTY_STATE = """
<section class="empty-state" aria-label="Empty catalogue">
  <p class="eyebrow">The collection is waiting</p>
  <h2>Make this wall yours.</h2>
  <p>Drop in a JPEG or PNG and we’ll prepare a private 4K Frame-ready edition on the NAS.</p>
</section>"""


_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Frame Art · Kip</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17201b;
      --muted: #5d6862;
      --paper: #f7f5ef;
      --line: #d9d5ca;
      --red: #b7352d;
      --green: #1f6b52;
      --radius: 8px;
      --shadow: 0 24px 60px rgba(23, 32, 27, .14);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .shell {{ width: min(1120px, calc(100% - 80px)); margin: 0 auto; }}
    .masthead {{ border-bottom: 1px solid var(--line); padding: 20px 0; }}
    .masthead__inside {{ display: flex; align-items: center; justify-content: space-between; gap: 20px; }}
    .wordmark {{ color: var(--ink); font-weight: 800; letter-spacing: -.03em; text-decoration: none; }}
    .wordmark b {{ color: var(--red); }}
    .private {{ color: var(--muted); font-size: .8125rem; }}
    .hero {{ padding: clamp(52px, 9vw, 112px) 0 clamp(36px, 6vw, 72px); display: grid; grid-template-columns: 1.25fr .75fr; gap: 64px; align-items: end; }}
    .eyebrow {{ margin: 0 0 10px; color: var(--red); font-size: .75rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }}
    h1, h2, h3 {{ letter-spacing: -.04em; line-height: 1.06; }}
    h1 {{ max-width: 760px; margin: 0; font-size: clamp(3rem, 7vw, 6.2rem); }}
    h1 em {{ color: var(--red); font-style: normal; }}
    .hero__copy {{ color: var(--muted); font-size: 1.125rem; max-width: 36rem; }}
    .upload-panel {{ padding: 24px; background: #fff; border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }}
    .upload-panel h2 {{ margin: 0 0 4px; font-size: 1.35rem; }}
    .upload-panel p {{ margin: 0 0 20px; color: var(--muted); font-size: .875rem; }}
    .upload-controls {{ display: flex; gap: 10px; }}
    input[type=file] {{ width: 100%; min-width: 0; padding: 10px; border: 1px solid var(--line); border-radius: 5px; color: var(--muted); }}
    button {{ appearance: none; border: 0; border-radius: 5px; padding: 11px 16px; background: var(--red); color: #fff; cursor: pointer; font: inherit; font-weight: 800; white-space: nowrap; }}
    button:hover {{ background: #982b25; }}
    button:disabled {{ cursor: wait; opacity: .65; }}
    .notice {{ display: none; margin: 14px 0 0; padding: 10px 12px; border-radius: 5px; font-size: .875rem; }}
    .notice.success {{ display: block; background: #e8f2ec; color: #15503b; }}
    .notice.error {{ display: block; background: #fae9e7; color: #84231f; }}
    .collection {{ border-top: 1px solid var(--line); padding: 32px 0 72px; }}
    .section-heading {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px; margin-bottom: 22px; }}
    .section-heading h2 {{ margin: 0; font-size: clamp(1.75rem, 3vw, 2.5rem); }}
    .section-heading p {{ margin: 0; color: var(--muted); font-size: .875rem; }}
    .art-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; }}
    .art-card {{ overflow: hidden; background: #fff; border: 1px solid var(--line); border-radius: var(--radius); }}
    .art-card img {{ display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: cover; background: #e9e6df; }}
    .art-card__body {{ padding: 17px; }}
    .art-card h3 {{ overflow: hidden; margin: 0 0 6px; font-size: 1.125rem; text-overflow: ellipsis; white-space: nowrap; }}
    .art-card__meta {{ margin: 0 0 14px; color: var(--muted); font-size: .8125rem; }}
    .status {{ display: inline-flex; align-items: center; gap: 7px; color: var(--muted); font-size: .75rem; font-weight: 800; }}
    .status span {{ display: block; width: 8px; height: 8px; border-radius: 50%; background: #a5aaa6; }}
    .status.is-on-frame {{ color: var(--green); }} .status.is-on-frame span {{ background: var(--green); }}
    .status.is-ready {{ color: var(--red); }} .status.is-ready span {{ background: var(--red); }}
    .empty-state {{ padding: 64px 24px; border: 1px dashed #bdb8aa; border-radius: var(--radius); text-align: center; }}
    .empty-state h2 {{ margin: 0 0 10px; font-size: clamp(1.75rem, 3vw, 2.5rem); }} .empty-state p:last-child {{ max-width: 34rem; margin: 0 auto; color: var(--muted); }}
    footer {{ padding: 24px 0 40px; color: var(--muted); font-size: .8125rem; }}
    @media (max-width: 760px) {{ .shell {{ width: min(100% - 40px, 1120px); }} .hero {{ grid-template-columns: 1fr; gap: 32px; padding-top: 56px; }} .upload-controls {{ flex-direction: column; }} button {{ width: 100%; }} }}
  </style>
</head>
<body>
  <header class="masthead"><div class="shell masthead__inside"><a class="wordmark" href="/">kip<b>.</b>computer</a><span class="private">Private Frame curator</span></div></header>
  <main class="shell">
    <section class="hero">
      <div><p class="eyebrow">A quiet wall, deliberately chosen</p><h1>Art for the <em>Frame.</em></h1><p class="hero__copy">A private NAS collection for preparing and selecting the images that live in your home. Nothing is sent to the TV without an explicit confirmation.</p></div>
      <section class="upload-panel" aria-labelledby="upload-title"><h2 id="upload-title">Add to the collection</h2><p>JPEG or PNG · rendered as a 3840 × 2160 Frame edition.</p><form id="upload-form"><div class="upload-controls"><input id="artwork-file" name="file" type="file" accept="image/jpeg,image/png" required><button id="upload-button" type="submit">Prepare art</button></div></form><p id="notice" class="notice" role="status"></p></section>
    </section>
    <section class="collection"><div class="section-heading"><h2>Collection</h2><p>Stored on the NAS · tailnet only</p></div><div class="art-grid">{cards}</div>{empty_state}</section>
  </main>
  <footer class="shell">art.kip.computer · Private, local, and confirmation-first.</footer>
  <script>
    const form = document.querySelector('#upload-form'); const notice = document.querySelector('#notice'); const button = document.querySelector('#upload-button');
    form.addEventListener('submit', async (event) => {{ event.preventDefault(); button.disabled = true; button.textContent = 'Preparing…'; notice.className = 'notice'; try {{ const response = await fetch('/api/artworks', {{method: 'POST', body: new FormData(form)}}); const body = await response.json(); if (!response.ok) throw new Error(body.detail || 'Could not prepare artwork.'); notice.textContent = 'Prepared ' + body.filename + '. Refreshing collection…'; notice.className = 'notice success'; setTimeout(() => location.reload(), 650); }} catch (error) {{ notice.textContent = error.message; notice.className = 'notice error'; button.disabled = false; button.textContent = 'Prepare art'; }} }});
  </script>
</body>
</html>"""
