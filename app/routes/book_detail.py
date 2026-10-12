"""
Book detail routes (standalone).

Endpoints for getting, updating, and deleting a book by ID.
These routes live under /api/books/{book_id} — separate from the
series-scoped book listing/creation in books.py.

Endpoints:
  GET    /api/books/{book_id}                        — Get a book with all data.
  PUT    /api/books/{book_id}                        — Update a book.
  DELETE /api/books/{book_id}                        — Delete a book.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models.book import Book

router = APIRouter()


@router.get("/{book_id}", response_model=dict)
def get_book(book_id: str, session: Session = Depends(get_session)):
    """
    Get a book with all its acts, nodes, choices, locations, items,
    and encounters (both series-shared and book-specific).
    """
    from app.models.act import Act
    from app.models.node import Node
    from app.models.choice import Choice
    from app.models.location import Location
    from app.models.item import Item
    from app.models.encounter import Encounter

    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    acts = session.query(Act).filter(Act.book_id == book_id).all()
    nodes = session.query(Node).filter(Node.book_id == book_id).all()
    choice_ids = [n.id for n in nodes]
    choices = (
        session.query(Choice)
        .filter(Choice.source_node_id.in_(choice_ids))
        .all()
    )
    shared_locs = (
        session.query(Location).filter(Location.series_id == book.series_id)
        .filter(Location.book_id.is_(None)).all()
    )
    book_locs = (
        session.query(Location).filter(Location.book_id == book_id).all()
    )
    shared_items = (
        session.query(Item).filter(Item.series_id == book.series_id)
        .filter(Item.book_id.is_(None)).all()
    )
    book_items = (
        session.query(Item).filter(Item.book_id == book_id).all()
    )
    shared_encs = (
        session.query(Encounter).filter(Encounter.series_id == book.series_id)
        .filter(Encounter.book_id.is_(None)).all()
    )
    book_encs = (
        session.query(Encounter).filter(Encounter.book_id == book_id).all()
    )

    def _loc(o):
        return {"id": o.id, "name": o.name, "description": o.description,
                "shared": o.series_id is not None}

    def _item(o):
        return {"id": o.id, "name": o.name, "description": o.description,
                "effect": o.effect, "shared": o.series_id is not None}

    def _enc(o):
        return {"id": o.id, "name": o.name, "description": o.description,
                "stats": o.stats, "recurring": bool(o.recurring),
                "shared": o.series_id is not None}

    return {
        "id": book.id,
        "seriesId": book.series_id,
        "title": book.title,
        "number": book.number,
        "description": book.description,
        "acts": [
            {"id": a.id, "title": a.title, "order": a.order,
             "entryNodeIds": a.entryNodeIds, "exitNodeIds": a.exitNodeIds,
             "nodeIds": a.nodeIds, "hasEndings": bool(a.hasEndings)}
            for a in acts
        ],
        "nodes": [
            {
                "id": n.id, "title": n.title, "description": n.description,
                "locationId": n.locationId, "items": n.items,
                "encounters": n.encounters, "type": n.type,
                "actId": n.act_id, "choices": n.choices,
                "x": n.x, "y": n.y,
                "storyText": n.storyText, "storyStatus": n.storyStatus,
                "storyModel": n.storyModel, "storyPrompt": n.storyPrompt,
            }
            for n in nodes
        ],
        "choices": [
            {"id": c.id, "sourceNodeId": c.source_node_id,
             "targetId": c.target_id, "text": c.text}
            for c in choices
        ],
        "sharedLocations": [_loc(l) for l in shared_locs],
        "sharedItems": [_item(i) for i in shared_items],
        "sharedEncounters": [_enc(e) for e in shared_encs],
        "bookLocations": [_loc(l) for l in book_locs],
        "bookItems": [_item(i) for i in book_items],
        "bookEncounters": [_enc(e) for e in book_encs],
    }


@router.put("/{book_id}", response_model=dict)
def update_book(
    book_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Update a book. Only provided fields are changed."""
    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    for field in ("title", "description", "number"):
        if field in body:
            setattr(book, field, body[field])

    session.commit()
    session.refresh(book)
    return {"id": book.id, "title": book.title}


@router.delete("/{book_id}")
def delete_book(book_id: str, session: Session = Depends(get_session)):
    """Delete a book and cascade to acts, nodes, etc."""
    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    session.delete(book)
    session.commit()
    return {"status": "deleted"}
