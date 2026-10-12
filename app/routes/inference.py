"""
Inference routes.

API endpoints for the inference bridge:
  GET  /api/inference/status              — Health check for the inference endpoint.
  POST /api/books/{book_id}/nodes/{node_id}/generate — Generate story text for a single node.

These routes connect the app to the external inference endpoint so nodes
can have their storyStatus tracked and storyText populated.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models.node import Node
from app.models.book import Book
from app.models.act import Act
from app.models.choice import Choice
from app.services import inference

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/inference/status", response_model=dict)
async def get_inference_status():
    """
    Check the health of the configured inference endpoint.

    Returns a dict with:
      - status: "healthy", "unhealthy", or "not_configured"
      - endpoint: The configured endpoint URL
      - message: Human-readable status message
    """
    return await inference.check_health()


@router.post("/books/{book_id}/nodes/{node_id}/generate", response_model=dict)
async def generate_node_story(
    book_id: str,
    node_id: str,
    body: dict = {},
    session: Session = Depends(get_session),
):
    """
    Generate story text for a single node using the inference endpoint.

    The prompt is built from:
      - The node's title and description
      - The node's location (if set)
      - The node's items (if any)
      - The node's encounters (if any)
      - The previous node's storyText (for continuity), if a choice leads to this node
      - The act's context

    Args:
        book_id: UUID of the book containing the node.
        node_id: UUID of the node to generate story text for.
        body: Optional request body with:
            - model: Model name to use (defaults to config default)
            - temperature: Sampling temperature (defaults to 0.7)
            - max_tokens: Max response tokens (defaults to 2000)

    Returns:
        Dict with node_id, storyText (the generated text), and storyStatus.

    Raises:
        HTTPException 404: If the book or node is not found.
        HTTPException 400: If the node is not in the specified book.
    """
    import uuid

    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    node = session.query(Node).filter(Node.id == node_id).first()
    if not node or node.book_id != book_id:
        raise HTTPException(status_code=404, detail="Node not found")

    # Set status to "generating"
    node.storyStatus = "generating"
    session.commit()

    # Build the prompt
    prompt = _build_story_prompt(session, node, body)

    # Call the inference endpoint
    model = body.get("model")
    temperature = body.get("temperature")
    max_tokens = body.get("max_tokens")

    try:
        story_text = await inference.send_completion(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        node.storyText = story_text
        node.storyStatus = "complete"
        node.storyModel = model or "default"
        node.storyPrompt = prompt
        logger.info(
            "Story generated for node %s: %d chars", node_id, len(story_text)
        )
    except Exception as exc:
        node.storyStatus = "failed"
        node.storyPrompt = prompt
        logger.error("Story generation failed for node %s: %s", node_id, exc)
        session.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Story generation failed: {exc}",
        )

    session.commit()
    session.refresh(node)

    return {
        "id": node.id,
        "title": node.title,
        "storyText": node.storyText,
        "storyStatus": node.storyStatus,
        "storyModel": node.storyModel,
        "storyPrompt": node.storyPrompt,
    }


def _build_story_prompt(
    session: Session,
    node: Node,
    body: dict,
) -> str:
    """
    Build a prompt for generating story text for a node.

    The prompt includes:
      - Context about the gamebook world/series tone
      - The node's title, description, and type
      - Associated items and encounters
      - The previous node's storyText (for continuity)
      - Act context

    Args:
        session: Database session.
        node: The node to generate story text for.
        body: Optional request body (unused in prompt building).

    Returns:
        A formatted prompt string for the inference endpoint.
    """
    lines = []

    # System context
    lines.append(
        "You are writing a story beat for an interactive gamebook. "
        "Write in an engaging, immersive style appropriate for the genre."
    )
    lines.append("")

    # Node context
    lines.append(f"Node title: {node.title}")
    lines.append(f"Node type: {node.type}")
    if node.description:
        lines.append(f"Description: {node.description}")

    # Location context (if set)
    if node.locationId:
        lines.append(f"Location ID: {node.locationId}")

    # Items
    items_list = []
    if node.items:
        try:
            import json
            item_ids = json.loads(node.items)
            if isinstance(item_ids, list):
                from app.models.item import Item
                for item_id in item_ids:
                    item = session.query(Item).filter(Item.id == item_id).first()
                    if item:
                        items_list.append(f"  - {item.name}: {item.description or '(no description)'}")
        except Exception:
            pass
    if items_list:
        lines.append("Items available:")
        lines.extend(items_list)
        lines.append("")

    # Encounters
    encounters_list = []
    if node.encounters:
        try:
            import json
            encounter_ids = json.loads(node.encounters)
            if isinstance(encounter_ids, list):
                from app.models.encounter import Encounter
                for enc_id in encounter_ids:
                    enc = session.query(Encounter).filter(Encounter.id == enc_id).first()
                    if enc:
                        encounters_list.append(f"  - {enc.name}: {enc.description or '(no description)'}")
        except Exception:
            pass
    if encounters_list:
        lines.append("Encounters:")
        lines.extend(encounters_list)
        lines.append("")

    # Previous node context for continuity
    prev_text = _get_previous_story_text(session, node)
    if prev_text:
        lines.append("Previous story text (for continuity):")
        lines.append(f"  {prev_text}")
        lines.append("")

    # Act context
    if node.act_id:
        act = session.query(Act).filter(Act.id == node.act_id).first()
        if act:
            lines.append(f"Act: {act.title}")
            lines.append("")

    # The actual generation instruction
    lines.append("Write the story text for this node. Be vivid, engaging, and "
                 "consistent with any previous text provided. Keep it between "
                 "100 and 500 words.")

    return "\n".join(lines)


def _get_previous_story_text(session: Session, node: Node) -> Optional[str]:
    """
    Find the storyText of the node that leads to this one via a choice.

    Looks for any choice where target_id == node.id and returns the
    storyText of the source node.

    Args:
        session: Database session.
        node: The current node.

    Returns:
        The storyText of the previous node, or None if not found.
    """
    # Find choices pointing to this node
    choices = (
        session.query(Choice)
        .filter(Choice.target_id == node.id)
        .all()
    )
    for choice in choices:
        prev_node = session.query(Node).filter(Node.id == choice.source_node_id).first()
        if prev_node and prev_node.storyText:
            return prev_node.storyText
    return None
