"""
Item routes.

API endpoints for managing items. Two sets of endpoints:
  - Series-level: manage shared items (series_id set, book_id null).
  - Book-level: manage book-specific items (book_id set, series_id null).

Endpoints:
  GET    /api/series/{series_id}/items            — List shared items.
  POST   /api/series/{series_id}/items            — Create a shared item.
  GET    /api/books/{book_id}/items               — List book-specific items.
  POST   /api/books/{book_id}/items               — Create a book-specific item.
  PUT    /api/items/{item_id}                     — Update any item.
  DELETE /api/items/{item_id}                     — Delete any item.
"""

import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models.item import Item
from app.models.book import Book
from app.models.series import Series

router = APIRouter()


@router.get("/series/{series_id}/items", response_model=list[dict])
def list_shared_items(series_id: str, session: Session = Depends(get_session)):
    """Return items shared across a series."""
    items = (
        session.query(Item)
        .filter(Item.series_id == series_id)
        .filter(Item.book_id.is_(None))
        .all()
    )
    return [
        {
            "id": i.id, "name": i.name, "description": i.description,
            "effect": i.effect, "shared": True,
        }
        for i in items
    ]


@router.post("/series/{series_id}/items", response_model=dict)
def create_shared_item(
    series_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Create an item shared across all books in a series."""
    series = session.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    import uuid
    item = Item(
        id=str(uuid.uuid4()),
        series_id=series_id,
        name=name,
        description=body.get("description"),
        effect=json.dumps(body.get("effect")) if body.get("effect") else None,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "effect": json.loads(item.effect) if item.effect else None,
        "shared": True,
    }


@router.get("/books/{book_id}/items", response_model=list[dict])
def list_book_items(book_id: str, session: Session = Depends(get_session)):
    """Return book-specific items."""
    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    items = (
        session.query(Item)
        .filter(Item.book_id == book_id)
        .filter(Item.series_id.is_(None))
        .all()
    )
    return [
        {
            "id": i.id, "name": i.name, "description": i.description,
            "effect": i.effect, "shared": False,
        }
        for i in items
    ]


@router.post("/books/{book_id}/items", response_model=dict)
def create_book_item(
    book_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Create an item specific to one book."""
    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    import uuid
    item = Item(
        id=str(uuid.uuid4()),
        book_id=book_id,
        name=name,
        description=body.get("description"),
        effect=json.dumps(body.get("effect")) if body.get("effect") else None,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "effect": json.loads(item.effect) if item.effect else None,
        "shared": False,
    }


@router.put("/items/{item_id}", response_model=dict)
def update_item(
    item_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Update an item's name, description, or effect."""
    item = session.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    for field in ("name", "description"):
        if field in body:
            setattr(item, field, body[field])

    if "effect" in body:
        item.effect = json.dumps(body["effect"]) if isinstance(body["effect"], dict) else body["effect"]

    session.commit()
    session.refresh(item)
    return {"id": item.id, "name": item.name}


@router.delete("/items/{item_id}")
def delete_item(item_id: str, session: Session = Depends(get_session)):
    """Delete an item."""
    item = session.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    session.delete(item)
    session.commit()
    return {"status": "deleted"}
