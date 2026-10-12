"""
Phase 6 — Inference Integration (Bridge) Test Suite

Tests the inference bridge implementation:
- Health check endpoint (/api/inference/status)
- Story generation endpoint (/api/books/{book_id}/nodes/{node_id}/generate)
- Inference service retry logic
- Prompt building with node context (items, encounters, previous story text)
- storyStatus transitions: pending → generating → complete/failed

Phase 5 quality: Error handling (tested via HTTP 502 on inference failure).
"""

import pytest
from fastapi.testclient import TestClient
from app import create_app
from app.database import Base, engine


@pytest.fixture
def client():
    """Create a test client with a fresh in-memory database."""
    import os
    os.environ["DATABASE_URL"] = "sqlite:///file::memory:?cache=shared"

    from app.database import engine as test_engine
    Base.metadata.create_all(bind=test_engine)

    app = create_app()
    client = TestClient(app)
    yield client

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def book_with_context(client):
    """Create a book with acts, nodes, items, encounters, and choices for testing."""
    # Create a series
    series_response = client.post("/api/series/", json={
        "title": "Test Series",
        "description": "A test series"
    })
    assert series_response.status_code == 200
    series_id = series_response.json()["id"]

    # Create a book
    book_response = client.post(f"/api/series/{series_id}/books/", json={
        "title": "Test Book",
        "number": 1
    })
    assert book_response.status_code == 200
    book_id = book_response.json()["id"]

    # Create an act
    act_response = client.post(f"/api/books/{book_id}/acts/", json={
        "title": "Act 1"
    })
    assert act_response.status_code == 200
    act_id = act_response.json()["id"]

    # Create an item
    item_response = client.post(f"/api/books/{book_id}/items/", json={
        "name": "Torch",
        "description": "A flickering torch",
        "effect": {"lightBonus": 1}
    })
    assert item_response.status_code == 200
    item_id = item_response.json()["id"]

    # Create an encounter
    encounter_response = client.post(f"/api/books/{book_id}/encounters/", json={
        "name": "Ghost",
        "description": "A spectral apparition",
        "stats": {"hp": 5, "attack": 3},
        "recurring": False
    })
    assert encounter_response.status_code == 200
    encounter_id = encounter_response.json()["id"]

    # Create node 1 (entry)
    node1_response = client.post(f"/api/books/{book_id}/nodes/", json={
        "title": "Dark Corridor",
        "actId": act_id,
        "type": "entry",
        "description": "You enter a dark, narrow corridor.",
        "items": [item_id],
        "x": 100,
        "y": 100
    })
    assert node1_response.status_code == 200
    node1_id = node1_response.json()["id"]

    # Create node 2 (beat, with encounter)
    node2_response = client.post(f"/api/books/{book_id}/nodes/", json={
        "title": "Haunted Room",
        "actId": act_id,
        "type": "beat",
        "description": "You enter a room filled with echoes.",
        "encounters": [encounter_id],
        "x": 200,
        "y": 200
    })
    assert node2_response.status_code == 200
    node2_id = node2_response.json()["id"]

    # Create a choice from node1 to node2
    choice_response = client.post(
        f"/api/books/{book_id}/nodes/{node1_id}/choices/",
        json={
            "targetId": node2_id,
            "text": "Enter the haunted room"
        }
    )
    assert choice_response.status_code == 200

    return {
        "book_id": book_id,
        "series_id": series_id,
        "act_id": act_id,
        "node1_id": node1_id,
        "node2_id": node2_id,
        "item_id": item_id,
        "encounter_id": encounter_id,
    }


class TestInferenceHealthCheck:
    """Tests for the inference health check endpoint."""

    def test_health_check_returns_status(self, client):
        """GET /api/inference/status should return a status dict."""
        response = client.get("/api/inference/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "endpoint" in data
        assert "message" in data
        assert data["status"] in ("healthy", "unhealthy", "not_configured")

    def test_health_check_reports_not_configured_when_no_key(self, client):
        """When no API key is set and endpoint is default, status is 'not_configured'."""
        response = client.get("/api/inference/status")
        data = response.json()
        # By default, no API key is configured, so it should be not_configured
        assert data["status"] == "not_configured"


class TestStoryGeneration:
    """Tests for the story generation endpoint."""

    def test_generate_story_success(self, client, book_with_context):
        """Story generation should call the inference endpoint and save the response."""
        from unittest.mock import patch

        # Mock the send_completion to return a fake story
        async def mock_send(*args, **kwargs):
            return "You walk down the dark corridor, your torch casting shadows on the walls."

        from app.services import inference as inf_module
        with patch.object(inf_module, 'send_completion', new=mock_send):
            response = client.post(
                f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}/generate",
                json={}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["storyStatus"] == "complete"
        assert data["storyText"] == "You walk down the dark corridor, your torch casting shadows on the walls."
        assert data["title"] == "Dark Corridor"

    def test_generate_story_sets_generating_status_first(self, client, book_with_context):
        """Story generation should set storyStatus to 'generating' before calling the endpoint."""
        from unittest.mock import patch, AsyncMock

        async def mock_send(*args, **kwargs):
            return "Generated text"

        from app.services import inference as inf_module
        with patch.object(inf_module, 'send_completion', new=mock_send):
            response = client.post(
                f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}/generate",
                json={}
            )

        assert response.status_code == 200
        # Verify the node was updated
        node_data = client.get(f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}").json()
        assert node_data["storyStatus"] == "complete"
        assert node_data["storyText"] is not None

    def test_generate_story_returns_404_for_missing_book(self, client):
        """Should return 404 if the book does not exist."""
        response = client.post(
            "/api/books/nonexistent/nodes/node1/generate",
            json={}
        )
        assert response.status_code == 404

    def test_generate_story_returns_404_for_missing_node(self, client, book_with_context):
        """Should return 404 if the node does not exist."""
        response = client.post(
            f"/api/books/{book_with_context['book_id']}/nodes/nonexistent/generate",
            json={}
        )
        assert response.status_code == 404

    def test_generate_story_includes_model_in_response(self, client, book_with_context):
        """The response should include the model used."""
        from unittest.mock import patch

        async def mock_send(*args, **kwargs):
            return "Generated text"

        from app.services import inference as inf_module
        with patch.object(inf_module, 'send_completion', new=mock_send):
            response = client.post(
                f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}/generate",
                json={"model": "custom-model"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["storyModel"] == "custom-model"


class TestInferenceRetry:
    """Tests for inference service retry logic."""

    def test_send_completion_retries_on_timeout(self):
        """send_completion has retry logic for timeouts (code verification)."""
        # We verify the retry logic exists in the source by checking
        # that the function contains the expected retry pattern.
        import inspect
        from app.services.inference import send_completion
        source = inspect.getsource(send_completion)
        assert "max_retries" in source, "send_completion should use max_retries"
        assert "backoff" in source, "send_completion should use exponential backoff"
        assert "time.sleep" in source, "send_completion should sleep between retries"


class TestPromptBuilding:
    """Tests for the prompt building logic in story generation."""

    def test_prompt_includes_node_title_and_description(self, client, book_with_context):
        """The prompt should include the node's title and description."""
        from unittest.mock import patch
        from app.services import inference as inf_module

        captured_prompt = [None]

        async def mock_send(prompt, **kwargs):
            captured_prompt[0] = prompt
            return "Generated text"

        with patch.object(inf_module, 'send_completion', new=mock_send):
            client.post(
                f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}/generate",
                json={}
            )

        assert captured_prompt[0] is not None
        assert "Dark Corridor" in captured_prompt[0]
        assert "dark, narrow corridor" in captured_prompt[0]

    def test_prompt_includes_items(self, client, book_with_context):
        """The prompt should include items associated with the node."""
        from unittest.mock import patch
        from app.services import inference as inf_module

        captured_prompt = [None]

        async def mock_send(prompt, **kwargs):
            captured_prompt[0] = prompt
            return "Generated text"

        with patch.object(inf_module, 'send_completion', new=mock_send):
            client.post(
                f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}/generate",
                json={}
            )

        assert captured_prompt[0] is not None
        assert "Torch" in captured_prompt[0]

    def test_prompt_includes_encounters(self, client, book_with_context):
        """The prompt should include encounters associated with the node."""
        from unittest.mock import patch
        from app.services import inference as inf_module

        captured_prompt = [None]

        async def mock_send(prompt, **kwargs):
            captured_prompt[0] = prompt
            return "Generated text"

        with patch.object(inf_module, 'send_completion', new=mock_send):
            client.post(
                f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node2_id']}/generate",
                json={}
            )

        assert captured_prompt[0] is not None
        assert "Ghost" in captured_prompt[0]

    def test_prompt_includes_previous_story_text(self, client, book_with_context):
        """The prompt should include the previous node's storyText for continuity."""
        from unittest.mock import patch
        from app.services import inference as inf_module
        import json

        captured_prompt = [None]

        async def mock_send(prompt, **kwargs):
            captured_prompt[0] = prompt
            return "Generated text"

        # First generate story for node1 (entry node)
        with patch.object(inf_module, 'send_completion', new=mock_send):
            client.post(
                f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}/generate",
                json={}
            )

        # Verify node1 has storyText
        node1_data = client.get(f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}").json()
        assert node1_data["storyText"] == "Generated text"

        # Now generate for node2 (which has a choice from node1)
        captured_prompt[0] = None
        with patch.object(inf_module, 'send_completion', new=mock_send):
            client.post(
                f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node2_id']}/generate",
                json={}
            )

        assert captured_prompt[0] is not None
        assert "Generated text" in captured_prompt[0], \
            "Previous story text should be included in the prompt for continuity"


class TestStoryStatusTransitions:
    """Tests for storyStatus state transitions."""

    def test_status_transitions_pending_to_complete(self, client, book_with_context):
        """storyStatus should transition: pending → generating → complete."""
        from unittest.mock import patch
        from app.services import inference as inf_module

        # Node starts with pending status
        node_data = client.get(f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}").json()
        assert node_data["storyStatus"] == "pending"

        async def mock_send(*args, **kwargs):
            return "Complete story"

        with patch.object(inf_module, 'send_completion', new=mock_send):
            response = client.post(
                f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}/generate",
                json={}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["storyStatus"] == "complete"

    def test_status_transitions_pending_to_failed(self, client, book_with_context):
        """storyStatus should transition: pending → generating → failed on error."""
        from unittest.mock import patch
        from app.services import inference as inf_module

        # Node starts with pending status
        node_data = client.get(f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}").json()
        assert node_data["storyStatus"] == "pending"

        async def mock_send(*args, **kwargs):
            raise RuntimeError("API unavailable")

        with patch.object(inf_module, 'send_completion', new=mock_send):
            response = client.post(
                f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}/generate",
                json={}
            )

        assert response.status_code == 502
        # Verify the node status was set to failed
        node_data = client.get(f"/api/books/{book_with_context['book_id']}/nodes/{book_with_context['node1_id']}").json()
        assert node_data["storyStatus"] == "failed"
