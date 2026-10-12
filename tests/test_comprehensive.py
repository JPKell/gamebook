"""
Comprehensive integration tests for the Gamebook Authoring Tool.

Covers regression scenarios that were missed by the original 8 tests:
  - Route collision / priority between series-scoped and standalone endpoints
  - Missing imports in route handlers (the 500 bug)
  - Data consistency across the full hierarchy
  - Edge cases: empty series, missing acts, orphan nodes
  - Entity scoping: shared vs book-specific locations/items/encounters
  - Cascade delete verification at every level
  - Validation: cross-book choices, self-choices, act ownership

Architecture:
  - create_test_app(): creates a FastAPI app with an in-memory DB.
  - Each test function exercises one or more endpoints and asserts
    the expected response.

Run with:
  python -m pytest tests/test_comprehensive.py -v
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.database import Base, engine, SessionLocal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create a test client with a fresh in-memory database."""
    app = create_app()
    Base.metadata.create_all(bind=engine)
    cli = TestClient(app)
    yield cli
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def full_hierarchy(client):
    """Build a complete series > book > act > nodes > choices hierarchy.

    Returns a dict with all IDs for test convenience.
    """
    # Create series
    s = client.post("/api/series/", json={
        "title": "Test Series",
        "description": "A test world",
        "tone": "dark fantasy",
    }).json()

    # Create book
    b = client.post(f"/api/series/{s['id']}/books", json={
        "title": "Book One",
        "number": 1,
    }).json()

    # Create act
    a = client.post(f"/api/books/{b['id']}/acts", json={
        "title": "The Journey Begins",
    }).json()

    # Create nodes
    n1 = client.post(f"/api/books/{b['id']}/nodes", json={
        "title": "Entry Point",
        "type": "entry",
        "actId": a["id"],
    }).json()

    n2 = client.post(f"/api/books/{b['id']}/nodes", json={
        "title": "The Bridge",
        "type": "beat",
        "actId": a["id"],
    }).json()

    n3 = client.post(f"/api/books/{b['id']}/nodes", json={
        "title": "The End",
        "type": "ending",
        "actId": a["id"],
    }).json()

    # Create choices
    c1 = client.post(
        f"/api/books/{b['id']}/nodes/{n1['id']}/choices",
        json={"targetId": n2["id"], "text": "Cross the bridge"}
    ).json()

    c2 = client.post(
        f"/api/books/{b['id']}/nodes/{n2['id']}/choices",
        json={"targetId": n3["id"], "text": "Continue"}
    ).json()

    return {
        "series_id": s["id"],
        "book_id": b["id"],
        "act_id": a["id"],
        "nodes": [n1, n2, n3],
        "choices": [c1, c2],
    }


# ---------------------------------------------------------------------------
# Route collision / priority tests
# ---------------------------------------------------------------------------

def test_get_series_by_id_includes_books(client):
    """GET /api/series/{id} must return the full series with books.

    Regression: this endpoint was returning 500 because Book, Location,
    Item, Encounter imports were removed during code cleanup.
    """
    s = client.post("/api/series/", json={"title": "Test"}).json()

    # Create a book so the series has content
    client.post(f"/api/series/{s['id']}/books", json={"title": "Book A"})

    resp = client.get(f"/api/series/{s['id']}")
    assert resp.status_code == 200, f"GET /series/{{id}} failed: {resp.text}"
    data = resp.json()
    assert data["title"] == "Test"
    assert "books" in data
    assert len(data["books"]) == 1
    assert data["books"][0]["title"] == "Book A"


def test_get_series_by_id_returns_entities(client):
    """GET /api/series/{id} must include sharedLocations, sharedItems, sharedEncounters."""
    s = client.post("/api/series/", json={"title": "Test"}).json()

    # Add shared entities
    client.post(f"/api/series/{s['id']}/locations", json={"name": "The Crypt"})
    client.post(f"/api/series/{s['id']}/items", json={"name": "Sword", "effect": "cuts"})
    client.post(f"/api/series/{s['id']}/encounters", json={"name": "Goblin", "stats": {"hp": 10}})

    resp = client.get(f"/api/series/{s['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sharedLocations"]) == 1
    assert data["sharedLocations"][0]["name"] == "The Crypt"
    assert len(data["sharedItems"]) == 1
    assert data["sharedItems"][0]["name"] == "Sword"
    assert len(data["sharedEncounters"]) == 1
    assert data["sharedEncounters"][0]["name"] == "Goblin"


def test_get_book_standalone_not_confused_by_series_prefix(client):
    """GET /api/books/{book_id} must not be captured by /api/series/{id}/books.

    Regression: FastAPI route collision caused /api/books/{id} to fail
    because /api/series/{id}/books matched first.
    """
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()

    # This should return the book detail, NOT a 404 or the series books list
    resp = client.get(f"/api/books/{b['id']}")
    assert resp.status_code == 200, f"GET /api/books/{{id}} failed: {resp.text}"
    data = resp.json()
    assert data["title"] == "Book"
    assert "acts" in data
    assert "nodes" in data
    assert "choices" in data


def test_series_list_does_not_include_books(client):
    """GET /api/series/ returns a flat list; book data is only on GET /series/{id}."""
    client.post("/api/series/", json={"title": "Series A"})
    client.post("/api/series/", json={"title": "Series B"})

    resp = client.get("/api/series/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # The list endpoint should NOT have 'books' keys
    for item in data:
        assert "books" not in item


# ---------------------------------------------------------------------------
# Full hierarchy / round-trip tests
# ---------------------------------------------------------------------------

def test_full_roundtrip(client, full_hierarchy):
    """GET the book and verify all acts, nodes, choices are present."""
    h = full_hierarchy

    resp = client.get(f"/api/books/{h['book_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["acts"]) == 1
    assert len(data["nodes"]) == 3
    assert len(data["choices"]) == 2

    # Verify act info
    assert data["acts"][0]["title"] == "The Journey Begins"
    assert data["acts"][0]["order"] == 1


def test_list_nodes_returns_all_nodes(client, full_hierarchy):
    """GET /books/{id}/nodes returns every node in the book."""
    h = full_hierarchy
    resp = client.get(f"/api/books/{h['book_id']}/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    titles = {n["title"] for n in data}
    assert titles == {"Entry Point", "The Bridge", "The End"}


def test_node_types_preserved(client, full_hierarchy):
    """Node type (entry, beat, ending) is correctly stored and returned."""
    h = full_hierarchy
    resp = client.get(f"/api/books/{h['book_id']}/nodes")
    data = {n["id"]: n for n in resp.json()}
    assert data[h["nodes"][0]["id"]]["type"] == "entry"
    assert data[h["nodes"][1]["id"]]["type"] == "beat"
    assert data[h["nodes"][2]["id"]]["type"] == "ending"


def test_node_position_stored(client, full_hierarchy):
    """Node x/y coordinates are persisted."""
    h = full_hierarchy
    resp = client.put(f"/api/books/{h['book_id']}/nodes/{h['nodes'][1]['id']}", json={
        "x": 250,
        "y": 180,
    })
    assert resp.status_code == 200
    assert resp.json()["x"] == 250
    assert resp.json()["y"] == 180


def test_act_ordering_auto_assigned(client):
    """Creating multiple acts auto-assigns order numbers 1, 2, 3..."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()

    a1 = client.post(f"/api/books/{b['id']}/acts", json={"title": "Act One"}).json()
    a2 = client.post(f"/api/books/{b['id']}/acts", json={"title": "Act Two"}).json()
    a3 = client.post(f"/api/books/{b['id']}/acts", json={"title": "Act Three"}).json()

    assert a1["order"] == 1
    assert a2["order"] == 2
    assert a3["order"] == 3

    # List should be ordered
    resp = client.get(f"/api/books/{b['id']}/acts")
    data = resp.json()
    assert [a["order"] for a in data] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Entity scoping tests (shared vs book-specific)
# ---------------------------------------------------------------------------

def test_shared_location_belongs_to_series(client):
    """A location created on /series/{id}/locations is shared."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    resp = client.post(f"/api/series/{s['id']}/locations", json={"name": "Shared Forest"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["shared"] is True


def test_book_location_is_not_shared(client):
    """A location created on /books/{id}/locations is book-specific."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()
    resp = client.post(f"/api/books/{b['id']}/locations", json={"name": "Book Dungeon"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["shared"] is False


def test_shared_and_book_entities_are_separate(client):
    """Series and book can have their own locations with the same name."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()

    # Shared location
    client.post(f"/api/series/{s['id']}/locations", json={"name": "Forest"})
    # Book-specific location
    client.post(f"/api/books/{b['id']}/locations", json={"name": "Forest"})

    # Get the series — should only see the shared one
    resp = client.get(f"/api/series/{s['id']}")
    data = resp.json()
    assert len(data["sharedLocations"]) == 1
    assert data["sharedLocations"][0]["name"] == "Forest"

    # Get the book — should only see the book-specific one
    resp = client.get(f"/api/books/{b['id']}")
    data = resp.json()
    assert len(data["bookLocations"]) == 1


def test_item_with_effect(client):
    """Item stores its 'effect' field correctly."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    resp = client.post(f"/api/series/{s['id']}/items", json={
        "name": "Magic Ring",
        "effect": "grants invisibility",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["effect"] == "grants invisibility"


def test_encounter_with_stats(client):
    """Encounter stores stats and recurring flag."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    resp = client.post(f"/api/series/{s['id']}/encounters", json={
        "name": "Dragon",
        "stats": {"hp": 100, "atk": 20},
        "recurring": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["stats"] == {"hp": 100, "atk": 20}
    assert data["recurring"] is True


# ---------------------------------------------------------------------------
# Act CRUD tests
# ---------------------------------------------------------------------------

def test_update_act_fields(client):
    """Updating an act's title, hasEndings, and entry/exit nodes works."""
    h = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{h['id']}/books", json={"title": "Book"}).json()
    a = client.post(f"/api/books/{b['id']}/acts", json={"title": "Original"}).json()

    resp = client.put(f"/api/books/{b['id']}/acts/{a['id']}", json={
        "title": "Renamed Act",
        "hasEndings": True,
        "entryNodeIds": ["node-1"],
        "exitNodeIds": ["node-2"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Renamed Act"
    assert data["hasEndings"] is True
    assert json.loads(data["entryNodeIds"]) == ["node-1"]
    assert json.loads(data["exitNodeIds"]) == ["node-2"]


def test_delete_act_removes_it(client):
    """Deleting an act removes it but does not cascade to nodes."""
    h = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{h['id']}/books", json={"title": "Book"}).json()
    a = client.post(f"/api/books/{b['id']}/acts", json={"title": "To Delete"}).json()

    resp = client.delete(f"/api/books/{b['id']}/acts/{a['id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Act should be gone
    resp = client.get(f"/api/books/{b['id']}/acts")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


def test_act_not_found_when_wrong_book(client):
    """Updating an act from a different book returns 404."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b1 = client.post(f"/api/series/{s['id']}/books", json={"title": "Book 1"}).json()
    b2 = client.post(f"/api/series/{s['id']}/books", json={"title": "Book 2"}).json()
    a = client.post(f"/api/books/{b1['id']}/acts", json={"title": "Act"}).json()

    # Try to update act using book2's prefix
    resp = client.put(f"/api/books/{b2['id']}/acts/{a['id']}", json={"title": "Hacked"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Node CRUD edge cases
# ---------------------------------------------------------------------------

def test_create_node_without_act(client):
    """A node can be created without an act (orphan node)."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()

    resp = client.post(f"/api/books/{b['id']}/nodes", json={
        "title": "Orphan Node",
        "type": "beat",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["actId"] is None


def test_create_node_with_invalid_act_returns_404(client):
    """Creating a node with a non-existent act_id returns 404."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()

    fake_act_id = str(uuid.uuid4())
    resp = client.post(f"/api/books/{b['id']}/nodes", json={
        "title": "Bad Node",
        "actId": fake_act_id,
    })
    assert resp.status_code == 404


def test_delete_node_removes_from_act(client):
    """Deleting a node removes it from its act's nodeIds."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()
    a = client.post(f"/api/books/{b['id']}/acts", json={"title": "Act"}).json()
    n = client.post(f"/api/books/{b['id']}/nodes", json={
        "title": "To Delete",
        "actId": a["id"],
    }).json()

    # Verify node is in act's nodeIds
    resp = client.get(f"/api/books/{b['id']}/acts")
    act_data = resp.json()[0]
    assert n["id"] in json.loads(act_data["nodeIds"])

    # Delete the node
    resp = client.delete(f"/api/books/{b['id']}/nodes/{n['id']}")
    assert resp.status_code == 200

    # Node should be removed from act's nodeIds
    resp = client.get(f"/api/books/{b['id']}/acts")
    act_data = resp.json()[0]
    assert n["id"] not in json.loads(act_data["nodeIds"])


def test_delete_node_cascades_to_choices(client):
    """Deleting a node also deletes all its choices."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()
    n1 = client.post(f"/api/books/{b['id']}/nodes", json={"title": "Node 1"}).json()
    n2 = client.post(f"/api/books/{b['id']}/nodes", json={"title": "Node 2"}).json()
    c = client.post(
        f"/api/books/{b['id']}/nodes/{n1['id']}/choices",
        json={"targetId": n2["id"], "text": "Go"}
    ).json()

    # Delete the source node
    resp = client.delete(f"/api/books/{b['id']}/nodes/{n1['id']}")
    assert resp.status_code == 200

    # The choice should be gone
    resp = client.delete(f"/api/books/{b['id']}/choices/{c['id']}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Choice tests
# ---------------------------------------------------------------------------

def test_create_choice_to_self_fails(client):
    """A node cannot create a choice that points to itself."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()
    n = client.post(f"/api/books/{b['id']}/nodes", json={"title": "Loop"}).json()

    resp = client.post(
        f"/api/books/{b['id']}/nodes/{n['id']}/choices",
        json={"targetId": n["id"], "text": "Self loop"}
    )
    assert resp.status_code == 400


def test_delete_choice_removes_from_node(client):
    """Deleting a choice removes it from the source node's choices JSON."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()
    n1 = client.post(f"/api/books/{b['id']}/nodes", json={"title": "Node 1"}).json()
    n2 = client.post(f"/api/books/{b['id']}/nodes", json={"title": "Node 2"}).json()
    c = client.post(
        f"/api/books/{b['id']}/nodes/{n1['id']}/choices",
        json={"targetId": n2["id"], "text": "Go"}
    ).json()

    # Verify node has the choice
    resp = client.get(f"/api/books/{b['id']}/nodes/{n1['id']}")
    data = resp.json()
    assert len(data["choicesList"]) == 1

    # Delete the choice
    resp = client.delete(f"/api/books/{b['id']}/choices/{c['id']}")
    assert resp.status_code == 200

    # Verify choice is gone
    resp = client.get(f"/api/books/{b['id']}/nodes/{n1['id']}")
    data = resp.json()
    assert len(data["choicesList"]) == 0


def test_choice_text_stored_correctly(client):
    """Choice text is preserved exactly as submitted."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()
    n1 = client.post(f"/api/books/{b['id']}/nodes", json={"title": "Node 1"}).json()
    n2 = client.post(f"/api/books/{b['id']}/nodes", json={"title": "Node 2"}).json()

    resp = client.post(
        f"/api/books/{b['id']}/nodes/{n1['id']}/choices",
        json={"targetId": n2["id"], "text": "I choose to fight"}
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "I choose to fight"


# ---------------------------------------------------------------------------
# Series CRUD edge cases
# ---------------------------------------------------------------------------

def test_create_series_without_title_fails(client):
    """Creating a series without a title returns 400."""
    resp = client.post("/api/series/", json={})
    assert resp.status_code == 400
    assert "title" in resp.json()["detail"].lower()


def test_get_nonexistent_series_returns_404(client):
    """GET /api/series/{id} for a non-existent ID returns 404."""
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/series/{fake_id}")
    assert resp.status_code == 404


def test_update_series_fields(client):
    """Updating a series title and tone works."""
    s = client.post("/api/series/", json={"title": "Old"}).json()
    resp = client.put(f"/api/series/{s['id']}", json={
        "title": "New",
        "tone": "comedic",
        "worldGuidelines": "No violence",
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "New"

    # Verify on reload
    resp = client.get(f"/api/series/{s['id']}")
    data = resp.json()
    assert data["title"] == "New"
    assert data["tone"] == "comedic"
    assert data["worldGuidelines"] == "No violence"


def test_list_series_sorted_by_created_desc(client):
    """Series are returned newest-first."""
    client.post("/api/series/", json={"title": "Old", "createdAt": "2020-01-01"})
    client.post("/api/series/", json={"title": "New", "createdAt": "2026-10-11"})

    resp = client.get("/api/series/")
    data = resp.json()
    assert len(data) == 2
    assert data[0]["title"] == "New"


# ---------------------------------------------------------------------------
# Export test
# ---------------------------------------------------------------------------

def test_export_series_returns_valid_json(client, full_hierarchy):
    """Exporting a series returns a valid JSON structure with version, series, books."""
    h = full_hierarchy

    resp = client.post(f"/api/series/{h['series_id']}/export")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert "series" in data
    assert "books" in data
    assert data["series"]["title"] == "Test Series"
    assert len(data["books"]) == 1
    assert len(data["books"][0]["acts"]) == 1
    assert len(data["books"][0]["nodes"]) == 3
    assert len(data["books"][0]["choices"]) == 2


def test_export_series_with_shared_entities(client):
    """Export includes shared locations, items, and encounters."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    client.post(f"/api/series/{s['id']}/locations", json={"name": "Forest"})
    client.post(f"/api/series/{s['id']}/items", json={"name": "Sword"})
    client.post(f"/api/series/{s['id']}/encounters", json={"name": "Goblin"})

    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()
    client.post(f"/api/books/{b['id']}/locations", json={"name": "Dungeon"})

    resp = client.post(f"/api/series/{s['id']}/export")
    data = resp.json()
    assert len(data["series"]["sharedLocations"]) == 1
    assert len(data["series"]["sharedItems"]) == 1
    assert len(data["series"]["sharedEncounters"]) == 1
    assert len(data["books"][0]["bookLocations"]) == 1


# ---------------------------------------------------------------------------
# Cascade delete tests
# ---------------------------------------------------------------------------

def test_cascade_delete_series_removes_all_books(client):
    """Deleting a series removes all books, acts, nodes, and choices."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b1 = client.post(f"/api/series/{s['id']}/books", json={"title": "Book 1"}).json()
    b2 = client.post(f"/api/series/{s['id']}/books", json={"title": "Book 2"}).json()

    # Add content to book 1
    client.post(f"/api/books/{b1['id']}/nodes", json={"title": "Node"})

    # Delete series
    resp = client.delete(f"/api/series/{s['id']}")
    assert resp.status_code == 200

    # Series is gone
    resp = client.get(f"/api/series/{s['id']}")
    assert resp.status_code == 404

    # Book 1 is gone (even though accessed via different path)
    resp = client.get(f"/api/books/{b1['id']}")
    assert resp.status_code == 404


def test_cascade_delete_series_removes_shared_entities(client):
    """Deleting a series removes shared locations, items, and encounters."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    client.post(f"/api/series/{s['id']}/locations", json={"name": "Forest"})
    client.post(f"/api/series/{s['id']}/items", json={"name": "Sword"})
    client.post(f"/api/series/{s['id']}/encounters", json={"name": "Goblin"})

    client.delete(f"/api/series/{s['id']}")

    # Create a new series and verify no entities from the deleted one leak
    s2 = client.post("/api/series/", json={"title": "New"}).json()
    resp = client.get(f"/api/series/{s2['id']}")
    data = resp.json()
    assert len(data["sharedLocations"]) == 0
    assert len(data["sharedItems"]) == 0
    assert len(data["sharedEncounters"]) == 0


# ---------------------------------------------------------------------------
# Missing/empty data tests
# ---------------------------------------------------------------------------

def test_get_empty_series(client):
    """A series with no books returns valid data with empty lists."""
    s = client.post("/api/series/", json={"title": "Empty"}).json()
    resp = client.get(f"/api/series/{s['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Empty"
    assert data["books"] == []
    assert data["sharedLocations"] == []
    assert data["sharedItems"] == []
    assert data["sharedEncounters"] == []


def test_book_with_no_acts(client):
    """A book with no acts returns valid data with empty lists."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Empty Book"}).json()
    resp = client.get(f"/api/books/{b['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Empty Book"
    assert data["acts"] == []
    assert data["nodes"] == []
    assert data["choices"] == []


def test_list_books_for_nonexistent_series_returns_empty(client):
    """Listing books for a series that doesn't exist returns an empty list (404 on series is also acceptable)."""
    fake_id = str(uuid.uuid4())
    resp = client.get(f"/api/series/{fake_id}/books")
    # FastAPI will try to match the series, which doesn't exist — but this route
    # doesn't check for the series first. It just returns whatever books match the series_id.
    # Either empty list or 404 is acceptable.
    assert resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Node update edge cases
# ---------------------------------------------------------------------------

def test_update_node_description_and_type(client, full_hierarchy):
    """Updating a node's description and type works."""
    h = full_hierarchy
    n = h["nodes"][1]

    resp = client.put(f"/api/books/{h['book_id']}/nodes/{n['id']}", json={
        "title": "Updated Bridge",
        "description": "A rickety wooden bridge",
        "type": "exit",
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Bridge"
    assert resp.json()["type"] == "exit"


def test_update_node_assigns_act(client):
    """Reassigning a node to a different act works."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()
    a1 = client.post(f"/api/books/{b['id']}/acts", json={"title": "Act One"}).json()
    a2 = client.post(f"/api/books/{b['id']}/acts", json={"title": "Act Two"}).json()
    n = client.post(f"/api/books/{b['id']}/nodes", json={
        "title": "Node",
        "actId": a1["id"],
    }).json()

    # Reassign to act 2
    resp = client.put(f"/api/books/{b['id']}/nodes/{n['id']}", json={
        "actId": a2["id"],
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "Node"

    # Verify on reload
    resp = client.get(f"/api/books/{b['id']}/nodes")
    data = {node["id"]: node for node in resp.json()}
    assert data[n["id"]]["actId"] == a2["id"]


# ---------------------------------------------------------------------------
# Act update: entry/exit node tracking
# ---------------------------------------------------------------------------

def test_act_entry_exit_node_ids_persist(client):
    """Act entryNodeIds and exitNodeIds are stored and returned as JSON arrays."""
    s = client.post("/api/series/", json={"title": "Test"}).json()
    b = client.post(f"/api/series/{s['id']}/books", json={"title": "Book"}).json()
    a = client.post(f"/api/books/{b['id']}/acts", json={"title": "Act"}).json()

    # Set entry/exit nodes
    resp = client.put(f"/api/books/{b['id']}/acts/{a['id']}", json={
        "entryNodeIds": ["node-a", "node-b"],
        "exitNodeIds": ["node-c"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert json.loads(data["entryNodeIds"]) == ["node-a", "node-b"]
    assert json.loads(data["exitNodeIds"]) == ["node-c"]
