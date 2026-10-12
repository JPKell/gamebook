"""
Integration tests for the Gamebook Authoring Tool.

Tests the API routes using FastAPI's TestClient with an in-memory
SQLite database. Each test creates its own database session and
tears it down afterwards.

Test structure:
  - create_test_app(): creates a FastAPI app with an in-memory DB.
  - Each test function exercises one or more endpoints and asserts
    the expected response.

Run with:
  python -m pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.database import Base, engine, SessionLocal


@pytest.fixture
def client():
    """Create a test client with a fresh in-memory database."""
    app = create_app()
    # Use a test database URL
    import os
    os.environ["DATABASE_URL"] = "sqlite:///file::memory:?cache=shared"

    from app.database import engine
    Base.metadata.create_all(bind=engine)

    client = TestClient(app)
    yield client

    Base.metadata.drop_all(bind=engine)


def test_create_series(client):
    """Creating a series returns the new series ID and title."""
    response = client.post("/api/series/", json={
        "title": "The Ashen Cycle",
        "description": "A dark fantasy world",
        "tone": "dark fantasy",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "The Ashen Cycle"
    assert data["tone"] == "dark fantasy"
    assert "id" in data


def test_create_book_in_series(client):
    """Creating a book within a series requires a valid series ID."""
    # Create series first
    series_resp = client.post("/api/series/", json={"title": "Test Series"})
    series_id = series_resp.json()["id"]

    # Create book
    book_resp = client.post(f"/api/series/{series_id}/books", json={
        "title": "Book One",
        "number": 1,
    })
    assert book_resp.status_code == 200
    assert book_resp.json()["title"] == "Book One"


def test_get_book_with_entities(client):
    """Fetching a book returns acts, nodes, choices, and entities."""
    # Create series and book
    series_resp = client.post("/api/series/", json={"title": "Test"})
    series_id = series_resp.json()["id"]
    book_resp = client.post(f"/api/series/{series_id}/books", json={"title": "Test Book"})
    book_id = book_resp.json()["id"]

    # Fetch book
    response = client.get(f"/api/books/{book_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Book"
    assert data["acts"] == []
    assert data["nodes"] == []
    assert data["choices"] == []


def test_create_and_update_node(client):
    """Creating a node and updating its title works."""
    series_resp = client.post("/api/series/", json={"title": "Test"})
    book_resp = client.post(f"/api/series/{series_resp.json()['id']}/books", json={"title": "Book"})
    book_id = book_resp.json()["id"]

    # Create node
    node_resp = client.post(f"/api/books/{book_id}/nodes", json={
        "title": "The Bridge",
        "type": "beat",
        "description": "A crumbling bridge",
    })
    assert node_resp.status_code == 200
    node_id = node_resp.json()["id"]

    # Update node
    update_resp = client.put(f"/api/books/{book_id}/nodes/{node_id}", json={
        "title": "The Broken Bridge",
        "type": "exit",
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "The Broken Bridge"


def test_create_choice_between_nodes(client):
    """Creating a choice between two nodes in the same book."""
    series_resp = client.post("/api/series/", json={"title": "Test"})
    book_resp = client.post(f"/api/series/{series_resp.json()['id']}/books", json={"title": "Book"})
    book_id = book_resp.json()["id"]

    # Create two nodes
    n1 = client.post(f"/api/books/{book_id}/nodes", json={"title": "Node 1"}).json()
    n2 = client.post(f"/api/books/{book_id}/nodes", json={"title": "Node 2"}).json()

    # Create choice
    choice_resp = client.post(
        f"/api/books/{book_id}/nodes/{n1['id']}/choices",
        json={"targetId": n2["id"], "text": "Go to Node 2"},
    )
    assert choice_resp.status_code == 200
    assert choice_resp.json()["targetId"] == n2["id"]
    assert choice_resp.json()["text"] == "Go to Node 2"


def test_cross_book_choice_fails(client):
    """A choice cannot target a node in a different book."""
    series_resp = client.post("/api/series/", json={"title": "Test"})
    book1 = client.post(f"/api/series/{series_resp.json()['id']}/books", json={"title": "Book 1"}).json()
    book2 = client.post(f"/api/series/{series_resp.json()['id']}/books", json={"title": "Book 2"}).json()

    n1 = client.post(f"/api/books/{book1['id']}/nodes", json={"title": "Node 1"}).json()
    n2 = client.post(f"/api/books/{book2['id']}/nodes", json={"title": "Node 2"}).json()

    # Try to create a cross-book choice
    resp = client.post(
        f"/api/books/{book1['id']}/nodes/{n1['id']}/choices",
        json={"targetId": n2["id"], "text": "Jump to Book 2"},
    )
    assert resp.status_code == 400


def test_create_shared_location(client):
    """Creating a shared location belongs to a series."""
    series_resp = client.post("/api/series/", json={"title": "Test"})
    series_id = series_resp.json()["id"]

    loc_resp = client.post(f"/api/series/{series_id}/locations", json={
        "name": "The Crypt",
        "description": "A dark underground passage",
    })
    assert loc_resp.status_code == 200
    assert loc_resp.json()["shared"] is True


def test_delete_series_cascades(client):
    """Deleting a series removes all associated books and data."""
    series_resp = client.post("/api/series/", json={"title": "To Delete"})
    series_id = series_resp.json()["id"]
    client.post(f"/api/series/{series_id}/books", json={"title": "Book"})

    delete_resp = client.delete(f"/api/series/{series_id}")
    assert delete_resp.status_code == 200

    # Verify series is gone
    get_resp = client.get(f"/api/series/{series_id}")
    assert get_resp.status_code == 404
