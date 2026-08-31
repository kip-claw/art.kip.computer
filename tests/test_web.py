from fastapi.testclient import TestClient

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
