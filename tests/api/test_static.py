"""Tests for the additive static-files (SPA) mount on the FastAPI app."""

from pathlib import Path

from fastapi.testclient import TestClient

from budget_tracker.api.app import create_app


def test_serves_index_when_dist_exists(tmp_path: Path) -> None:
    """When the dist dir exists, ``/`` serves index.html and ``/api/*`` still works."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Budget Dashboard</title>")

    client = TestClient(create_app(static_dir=dist))

    root = client.get("/")
    assert root.status_code == 200
    assert "Budget Dashboard" in root.text

    # The additive mount must not shadow the JSON API.
    assert client.get("/api/health").json() == {"status": "ok"}


def test_no_mount_when_dist_missing(tmp_path: Path) -> None:
    """With no dist dir, the app behaves exactly as before (no SPA at ``/``)."""
    client = TestClient(create_app(static_dir=tmp_path / "does-not-exist"))

    assert client.get("/").status_code == 404
    assert client.get("/api/health").status_code == 200
