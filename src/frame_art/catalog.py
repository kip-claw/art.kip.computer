"""NAS-backed artwork catalogue and audit log."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


@dataclass(frozen=True)
class Artwork:
    """One original artwork and its Frame-ready rendered counterpart."""

    id: str
    filename: str
    width: int
    height: int
    created_at: str
    tv_content_id: str | None

    def json(self) -> dict[str, object]:
        """Return a JSON-ready representation."""
        return {
            "id": self.id,
            "filename": self.filename,
            "width": self.width,
            "height": self.height,
            "created_at": self.created_at,
            "tv_content_id": self.tv_content_id,
        }


class Catalog:
    """Keep originals, rendered assets, state, and audit history on one volume."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.originals = root / "originals"
        self.renders = root / "renders"
        self.state = root / "state"
        for directory in (self.originals, self.renders, self.state):
            directory.mkdir(parents=True, exist_ok=True)
        self.database = self.state / "catalog.sqlite3"
        self._initialize()

    def add(self, content: bytes, filename: str) -> Artwork:
        """Store one original and a 3840x2160 JPEG, deduplicated by SHA-256."""
        digest = sha256(content).hexdigest()
        safe_name = Path(filename).name or "artwork"
        with Image.open(BytesIO(content)) as opened:
            width, height = opened.size
            rendered = ImageOps.fit(
                opened.convert("RGB"),
                (3840, 2160),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM artwork WHERE digest = ?", (digest,)
            ).fetchone()
            if row:
                self._log(connection, "deduplicated", row["id"], None)
                return self._row_to_artwork(row)
            identifier = digest[:16]
            original = self.originals / f"{identifier}-{safe_name}"
            render = self.renders / f"{identifier}.jpg"
            original.write_bytes(content)
            rendered.save(render, "JPEG", quality=92, optimize=True)
            created = _now()
            connection.execute(
                """
                INSERT INTO artwork (id, digest, filename, width, height, created_at,
                                     original_path, render_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    digest,
                    safe_name,
                    width,
                    height,
                    created,
                    str(original),
                    str(render),
                ),
            )
            self._log(connection, "created", identifier, None)
        return Artwork(identifier, safe_name, width, height, created, None)

    def artworks(self) -> list[Artwork]:
        """Return newest-first artwork records."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM artwork ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_artwork(row) for row in rows]

    def get(self, identifier: str) -> Artwork:
        """Return one artwork or raise KeyError."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM artwork WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise KeyError(identifier)
        return self._row_to_artwork(row)

    def render_path(self, identifier: str) -> Path:
        """Return the server-side Frame-ready JPEG path."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT render_path FROM artwork WHERE id = ?", (identifier,)
            ).fetchone()
        if row is None:
            raise KeyError(identifier)
        return Path(row["render_path"])

    def set_tv_content_id(self, identifier: str, content_id: str) -> None:
        """Record the Samsung ID returned from one confirmed upload."""
        with self._connect() as connection:
            self._require_artwork(connection, identifier)
            connection.execute(
                "UPDATE artwork SET tv_content_id = ? WHERE id = ?",
                (content_id, identifier),
            )
            self._log(connection, "uploaded_to_tv", identifier, content_id)

    def mark_displayed(self, identifier: str) -> None:
        """Atomically preserve a rollback target before changing current art."""
        artwork = self.get(identifier)
        if artwork.tv_content_id is None:
            raise ValueError("Artwork has not been uploaded to the TV.")
        with self._connect() as connection:
            current = connection.execute(
                "SELECT current_artwork_id FROM selection_state WHERE id = 1"
            ).fetchone()["current_artwork_id"]
            connection.execute(
                """
                UPDATE selection_state
                SET previous_artwork_id = ?, current_artwork_id = ?, changed_at = ?
                WHERE id = 1
                """,
                (current, identifier, _now()),
            )
            self._log(connection, "displayed", identifier, artwork.tv_content_id)

    def rollback_target(self) -> Artwork | None:
        """Return the artwork that can restore the prior display."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT artwork.* FROM selection_state
                JOIN artwork ON artwork.id = selection_state.previous_artwork_id
                WHERE selection_state.id = 1
                """
            ).fetchone()
        return self._row_to_artwork(row) if row else None

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS artwork (
                    id TEXT PRIMARY KEY,
                    digest TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    render_path TEXT NOT NULL,
                    tv_content_id TEXT
                );
                CREATE TABLE IF NOT EXISTS selection_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    current_artwork_id TEXT,
                    previous_artwork_id TEXT,
                    changed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS operation (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    artwork_id TEXT,
                    tv_content_id TEXT
                );
                INSERT OR IGNORE INTO selection_state (id) VALUES (1);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _log(
        connection: sqlite3.Connection,
        action: str,
        artwork_id: str | None,
        tv_content_id: str | None,
    ) -> None:
        connection.execute(
            "INSERT INTO operation (created_at, action, artwork_id, tv_content_id) VALUES (?, ?, ?, ?)",
            (_now(), action, artwork_id, tv_content_id),
        )

    @staticmethod
    def _require_artwork(connection: sqlite3.Connection, identifier: str) -> None:
        row = connection.execute(
            "SELECT id FROM artwork WHERE id = ?", (identifier,)
        ).fetchone()
        if row is None:
            raise KeyError(identifier)

    @staticmethod
    def _row_to_artwork(row: sqlite3.Row) -> Artwork:
        return Artwork(
            row["id"],
            row["filename"],
            row["width"],
            row["height"],
            row["created_at"],
            row["tv_content_id"],
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()
