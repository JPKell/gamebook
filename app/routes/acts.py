"""
Act routes.

API endpoints for managing acts within a book. Acts are ordered groups
of nodes. Creating a new act auto-assigns the next order number.
Updating act entry/exit nodes updates the nodeIds field.

Endpoints:
  GET    /api/books/{book_id}/acts              — List acts in a book.
  POST   /api/books/{book_id}/acts              — Create a new act.
  PUT    /api/books/{book_id}/acts/{act_id}     — Update an act.
  DELETE /api/books/{book_id}/acts/{act_id}     — Delete an act.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models.act import Act
from app.models.book import Book

router = APIRouter()


@router.get("/{book_id}/acts", response_model=list[dict])
def list_acts(book_id: str, session: Session = Depends(get_session)):
    """Return all acts in a book, ordered."""
    acts = (
        session.query(Act)
        .filter(Act.book_id == book_id)
        .order_by(Act.order)
        .all()
    )
    return [
        {
            "id": a.id, "title": a.title, "order": a.order,
            "entryNodeIds": a.entryNodeIds, "exitNodeIds": a.exitNodeIds,
            "nodeIds": a.nodeIds, "hasEndings": bool(a.hasEndings),
        }
        for a in acts
    ]


@router.post("/{book_id}/acts", response_model=dict)
def create_act(
    book_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Create a new act. Auto-assigns order = max(existing) + 1."""
    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    import uuid
    # Determine next order number
    max_order = (
        session.query(Act.order)
        .filter(Act.book_id == book_id)
        .order_by(Act.order.desc())
        .first()
    )
    order = (max_order[0] or 0) + 1

    act = Act(
        id=str(uuid.uuid4()),
        book_id=book_id,
        title=body.get("title", f"Act {order}"),
        order=order,
    )
    session.add(act)
    session.commit()
    session.refresh(act)
    return {
        "id": act.id, "title": act.title, "order": act.order,
        "entryNodeIds": act.entryNodeIds, "exitNodeIds": act.exitNodeIds,
        "nodeIds": act.nodeIds, "hasEndings": bool(act.hasEndings),
    }


@router.put("/{book_id}/acts/{act_id}", response_model=dict)
def update_act(
    book_id: str,
    act_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Update an act's title, order, entry/exit nodes, or ending flag."""
    act = session.query(Act).filter(Act.id == act_id).first()
    if not act or act.book_id != book_id:
        raise HTTPException(status_code=404, detail="Act not found")

    for field in ("title", "order", "hasEndings"):
        if field in body:
            setattr(act, field, body[field])

    # Handle entry/exit nodes and nodeIds as JSON arrays
    for field in ("entryNodeIds", "exitNodeIds", "nodeIds"):
        if field in body:
            val = body[field]
            if isinstance(val, list):
                setattr(act, field, json.dumps(val))
            elif isinstance(val, str):
                setattr(act, field, val)

    session.commit()
    session.refresh(act)
    return {
        "id": act.id, "title": act.title, "order": act.order,
        "entryNodeIds": act.entryNodeIds, "exitNodeIds": act.exitNodeIds,
        "nodeIds": act.nodeIds, "hasEndings": bool(act.hasEndings),
    }


@router.delete("/{book_id}/acts/{act_id}")
def delete_act(
    book_id: str,
    act_id: str,
    session: Session = Depends(get_session),
):
    """Delete an act. Does NOT cascade to nodes — nodes are orphaned."""
    act = session.query(Act).filter(Act.id == act_id).first()
    if not act or act.book_id != book_id:
        raise HTTPException(status_code=404, detail="Act not found")

    session.delete(act)
    session.commit()
    return {"status": "deleted"}
