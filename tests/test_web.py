from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from frame_art.catalog import Catalog
from frame_art.web import create_app


def test_tv_actions_require_confirmation(tmp_path):
    client = TestClient(create_app(Catalog(tmp_path)))
    response = client.post("/api/artworks/missing/upload-to-tv")
    assert response.status_code == 409


def test_home_uses_the_kip_visual_language(tmp_path):
    client = TestClient(create_app(Catalog(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert "Art for the <em>Frame.</em>" in response.text
    assert "--red: #b7352d" in response.text
    assert "kip<b>.</b>computer" in response.text
    assert "Make this wall yours." in response.text


def test_pending_display_remains_queued_when_tv_is_unavailable(tmp_path):
    catalog = Catalog(tmp_path)
    image = BytesIO()
    Image.new("RGB", (100, 80), "red").save(image, "JPEG")
    artwork = catalog.add(image.getvalue(), "source.jpg")
    catalog.set_tv_content_id(artwork.id, "MY_F1234")
    client = TestClient(
        create_app(catalog, lambda: (_ for _ in ()).throw(OSError("off")))
    )

    assert client.post(
        f"/api/artworks/{artwork.id}/queue-display?confirm=true"
    ).json() == {"status": "queued"}
    response = client.post("/api/pending-display/attempt?confirm=true")
    assert response.json()["status"] == "pending"
    assert catalog.pending_display().id == artwork.id
