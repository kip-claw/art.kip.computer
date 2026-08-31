from fastapi.testclient import TestClient

from frame_art.catalog import Catalog
from frame_art.web import create_app


def test_tv_actions_require_confirmation(tmp_path):
    client = TestClient(create_app(Catalog(tmp_path)))
    response = client.post("/api/artworks/missing/upload-to-tv")
    assert response.status_code == 409
