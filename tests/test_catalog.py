from io import BytesIO

import pytest
from PIL import Image

from frame_art.catalog import Catalog


def _jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (100, 80), "red").save(output, "JPEG")
    return output.getvalue()


@pytest.mark.unit
def test_catalog_renders_and_deduplicates(tmp_path):
    catalog = Catalog(tmp_path)
    first = catalog.add(_jpeg(), "source.jpg")
    duplicate = catalog.add(_jpeg(), "again.jpg")
    assert duplicate.id == first.id
    with Image.open(catalog.render_path(first.id)) as rendered:
        assert rendered.size == (3840, 2160)


@pytest.mark.unit
def test_pending_display_survives_until_marked_displayed(tmp_path):
    catalog = Catalog(tmp_path)
    artwork = catalog.add(_jpeg(), "source.jpg")
    catalog.set_tv_content_id(artwork.id, "MY_F1234")
    catalog.set_pending_display(artwork.id)
    assert catalog.pending_display().id == artwork.id
    catalog.mark_displayed(artwork.id)
    assert catalog.pending_display() is None
