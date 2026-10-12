"""
Node routes.

API endpoints for managing nodes within a book. Each node is a story
beat with a title, description, type, position, and a JSON array of
choices. Items and encounters are also stored as JSON arrays of IDs.

Creating a node can optionally specify an act_id and position (x, y).
If no act is specified, the node is created as an orphan (no act).

Endpoints:
  GET    /api/books/{book_id}/nodes              — List all nodes in a book.
  POST   /api/books/{book_id}/nodes              — Create a node.
  GET    /api/books/{book_id}/nodes/{node_id}    — Get a node with choices.
  PUT    /api/books/{book_id}/nodes/{node_id}    — Update a node.
  DELETE /api/books/{book_id}/nodes/{node_id}    — Delete a node.
  POST   /api/books/{book_id}/nodes/{node_id}/choices — Add a choice.
  DELETE /api/books/{book_id}/choices/{choice_id}    — Delete a choice.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models.node import Node
from app.models.choice import Choice
from app.models.act import Act
from app.models.book import Book

router = APIRouter()


@router.get("/{book_id}/nodes", response_model=list[dict])
def list_nodes(book_id: str, session: Session = Depends(get_session)):
    """Return all nodes in a book."""
    nodes = session.query(Node).filter(Node.book_id == book_id).all()
    return [
        {
            "id": n.id, "title": n.title, "description": n.description,
            "locationId": n.locationId,
            "items": json.loads(n.items) if n.items else [],
            "encounters": json.loads(n.encounters) if n.encounters else [],
            "type": n.type,
            "actId": n.act_id,
            "choices": json.loads(n.choices) if n.choices else [],
            "x": n.x, "y": n.y,
            "storyText": n.storyText, "storyStatus": n.storyStatus,
            "storyModel": n.storyModel, "storyPrompt": n.storyPrompt,
        }
        for n in nodes
    ]


@router.post("/{book_id}/nodes", response_model=dict)
def create_node(
    book_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Create a node within a book. Optional act, position, and type."""
    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    title = body.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    import uuid
    act_id = body.get("actId")
    if act_id:
        # Verify act exists in this book
        act = session.query(Act).filter(Act.id == act_id).first()
        if not act or act.book_id != book_id:
            raise HTTPException(status_code=404, detail="Act not found")

    items = body.get("items", [])
    encounters = body.get("encounters", [])
    
    node = Node(
        id=str(uuid.uuid4()),
        book_id=book_id,
        act_id=act_id,
        title=title,
        description=body.get("description", ""),
        locationId=body.get("locationId"),
        items=json.dumps(items) if isinstance(items, list) else items,
        encounters=json.dumps(encounters) if isinstance(encounters, list) else encounters,
        type=body.get("type", "beat"),
        choices="[]",
        x=body.get("x", 0.0),
        y=body.get("y", 0.0),
        storyText=body.get("storyText"),
        storyStatus=body.get("storyStatus", "pending"),
        storyModel=body.get("storyModel"),
        storyPrompt=body.get("storyPrompt"),
    )
    session.add(node)

    # Update the act's nodeIds list
    if act_id:
        act = session.query(Act).filter(Act.id == act_id).first()
        node_ids = json.loads(act.nodeIds or "[]")
        node_ids.append(node.id)
        act.nodeIds = json.dumps(node_ids)

    session.commit()
    session.refresh(node)
    return {
        "id": node.id, "title": node.title, "description": node.description,
        "locationId": node.locationId,
        "items": json.loads(node.items) if node.items else [],
        "encounters": json.loads(node.encounters) if node.encounters else [],
        "type": node.type,
        "actId": node.act_id,
        "choices": json.loads(node.choices) if node.choices else [],
        "x": node.x, "y": node.y,
        "storyText": node.storyText, "storyStatus": node.storyStatus,
        "storyModel": node.storyModel, "storyPrompt": node.storyPrompt,
    }


@router.get("/{book_id}/nodes/{node_id}", response_model=dict)
def get_node(
    book_id: str,
    node_id: str,
    session: Session = Depends(get_session),
):
    """Get a node and its choices."""
    node = session.query(Node).filter(Node.id == node_id).first()
    if not node or node.book_id != book_id:
        raise HTTPException(status_code=404, detail="Node not found")

    choices = (
        session.query(Choice)
        .filter(Choice.source_node_id == node_id)
        .all()
    )

    return {
        "id": node.id, "title": node.title, "description": node.description,
        "locationId": node.locationId, "items": json.loads(node.items) if node.items else [],
        "encounters": json.loads(node.encounters) if node.encounters else [], "type": node.type,
        "actId": node.act_id, "choices": json.loads(node.choices) if node.choices else [],
        "x": node.x, "y": node.y,
        "storyText": node.storyText, "storyStatus": node.storyStatus,
        "storyModel": node.storyModel, "storyPrompt": node.storyPrompt,
        "choicesList": [
            {"id": c.id, "sourceNodeId": c.source_node_id,
             "targetId": c.target_id, "text": c.text}
            for c in choices
        ],
    }


@router.put("/{book_id}/nodes/{node_id}", response_model=dict)
def update_node(
    book_id: str,
    node_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Update a node's fields."""
    node = session.query(Node).filter(Node.id == node_id).first()
    if not node or node.book_id != book_id:
        raise HTTPException(status_code=404, detail="Node not found")

    for field in ("title", "description", "locationId", "type",
                  "x", "y", "storyText", "storyStatus", "storyModel",
                  "storyPrompt"):
        if field in body:
            setattr(node, field, body[field])

    if "items" in body:
        node.items = json.dumps(body["items"]) if isinstance(body["items"], list) else body["items"]
    if "encounters" in body:
        node.encounters = json.dumps(body["encounters"]) if isinstance(body["encounters"], list) else body["encounters"]
    if "choices" in body:
        node.choices = json.dumps(body["choices"]) if isinstance(body["choices"], list) else body["choices"]
    if "actId" in body:
        node.act_id = body["actId"]

    session.commit()
    session.refresh(node)
    return {
        "id": node.id, "title": node.title, "type": node.type,
        "x": node.x, "y": node.y,
    }


@router.delete("/{book_id}/nodes/{node_id}")
def delete_node(
    book_id: str,
    node_id: str,
    session: Session = Depends(get_session),
):
    """Delete a node, its choices, and remove from its act's nodeIds."""
    node = session.query(Node).filter(Node.id == node_id).first()
    if not node or node.book_id != book_id:
        raise HTTPException(status_code=404, detail="Node not found")

    # Remove from act's nodeIds
    if node.act_id:
        act = session.query(Act).filter(Act.id == node.act_id).first()
        if act:
            node_ids = json.loads(act.nodeIds or "[]")
            node_ids = [n for n in node_ids if n != node_id]
            act.nodeIds = json.dumps(node_ids)

    # Delete choices
    session.query(Choice).filter(Choice.source_node_id == node_id).delete()

    session.delete(node)
    session.commit()
    return {"status": "deleted"}


@router.post("/{book_id}/nodes/{node_id}/choices", response_model=dict)
def add_choice(
    book_id: str,
    node_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """
    Add a choice to a node. The target node must be in the same book.
    """
    import uuid

    node = session.query(Node).filter(Node.id == node_id).first()
    if not node or node.book_id != book_id:
        raise HTTPException(status_code=404, detail="Node not found")

    target_id = body.get("targetId")
    text = body.get("text")

    if not target_id or not text:
        raise HTTPException(status_code=400, detail="targetId and text are required")

    # Validate target is in the same book
    target = session.query(Node).filter(Node.id == target_id).first()
    if not target or target.book_id != book_id:
        raise HTTPException(status_code=400, detail="Target node must be in the same book")

    # Prevent self-choice
    if target_id == node_id:
        raise HTTPException(status_code=400, detail="A node cannot choose itself")

    choice = Choice(
        id=str(uuid.uuid4()),
        source_node_id=node_id,
        target_id=target_id,
        text=text,
    )
    session.add(choice)

    # Update node's choices JSON
    choices = json.loads(node.choices or "[]")
    choices.append(choice.id)
    node.choices = json.dumps(choices)

    session.commit()
    session.refresh(choice)
    return {
        "id": choice.id, "sourceNodeId": choice.source_node_id,
        "targetId": choice.target_id, "text": choice.text,
    }


@router.delete("/{book_id}/choices/{choice_id}")
def delete_choice(
    book_id: str,
    choice_id: str,
    session: Session = Depends(get_session),
):
    """Delete a choice and remove it from the source node's choices."""
    choice = session.query(Choice).filter(Choice.id == choice_id).first()
    if not choice:
        raise HTTPException(status_code=404, detail="Choice not found")

    source_node = session.query(Node).filter(Node.id == choice.source_node_id).first()
    if source_node:
        choices = json.loads(source_node.choices or "[]")
        choices = [c for c in choices if c != choice_id]
        source_node.choices = json.dumps(choices)

    session.delete(choice)
    session.commit()
    return {"status": "deleted"}
