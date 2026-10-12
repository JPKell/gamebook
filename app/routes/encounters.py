"""
Encounter routes.

API endpoints for managing encounters (enemies/events). Two sets of
endpoints:
  - Series-level: manage shared encounters (series_id set, book_id null).
  - Book-level: manage book-specific encounters (book_id set, series_id null).

Endpoints:
  GET    /api/series/{series_id}/encounters       — List shared encounters.
  POST   /api/series/{series_id}/encounters       — Create a shared encounter.
  GET    /api/books/{book_id}/encounters          — List book-specific encounters.
  POST   /api/books/{book_id}/encounters          — Create a book-specific encounter.
  PUT    /api/encounters/{encounter_id}           — Update any encounter.
  DELETE /api/encounters/{encounter_id}           — Delete any encounter.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models.encounter import Encounter
from app.models.book import Book
from app.models.series import Series
import json
import uuid

router = APIRouter()


@router.get("/series/{series_id}/encounters", response_model=list[dict])
def list_shared_encounters(series_id: str, session: Session = Depends(get_session)):
    """Return encounters shared across a series."""
    encounters = (
        session.query(Encounter)
        .filter(Encounter.series_id == series_id)
        .filter(Encounter.book_id.is_(None))
        .all()
    )
    return [
        {
            "id": e.id, "name": e.name, "description": e.description,
            "stats": e.stats, "recurring": bool(e.recurring), "shared": True,
        }
        for e in encounters
    ]


@router.post("/series/{series_id}/encounters", response_model=dict)
def create_shared_encounter(
    series_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Create an encounter shared across all books in a series."""
    series = session.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    encounter = Encounter(
        id=str(uuid.uuid4()),
        series_id=series_id,
        name=name,
        description=body.get("description"),
        stats=json.dumps(body.get("stats")) if body.get("stats") else None,
        recurring=bool(body.get("recurring", False)),
    )
    session.add(encounter)
    session.commit()
    session.refresh(encounter)
    return {
        "id": encounter.id,
        "name": encounter.name,
        "shared": True,
        "seriesId": series_id,
        "stats": json.loads(encounter.stats) if encounter.stats else None,
        "recurring": bool(encounter.recurring),
    }


@router.get("/books/{book_id}/encounters", response_model=list[dict])
def list_book_encounters(book_id: str, session: Session = Depends(get_session)):
    """Return book-specific encounters."""
    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    encounters = (
        session.query(Encounter)
        .filter(Encounter.book_id == book_id)
        .filter(Encounter.series_id.is_(None))
        .all()
    )
    return [
        {
            "id": e.id, "name": e.name, "description": e.description,
            "stats": e.stats, "recurring": bool(e.recurring), "shared": False,
        }
        for e in encounters
    ]


@router.post("/books/{book_id}/encounters", response_model=dict)
def create_book_encounter(
    book_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Create an encounter specific to one book."""
    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    encounter = Encounter(
        id=str(uuid.uuid4()),
        book_id=book_id,
        name=name,
        description=body.get("description"),
        stats=json.dumps(body.get("stats")) if body.get("stats") else None,
        recurring=bool(body.get("recurring", False)),
    )
    session.add(encounter)
    session.commit()
    session.refresh(encounter)
    return {
        "id": encounter.id,
        "name": encounter.name,
        "shared": False,
        "bookId": book_id,
        "stats": json.loads(encounter.stats) if encounter.stats else None,
        "recurring": bool(encounter.recurring),
    }


@router.put("/encounters/{encounter_id}", response_model=dict)
def update_encounter(
    encounter_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Update an encounter's name, description, stats, or recurring flag."""
    encounter = session.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")

    for field in ("name", "description", "stats", "recurring"):
        if field in body:
            setattr(encounter, field, body[field])

    session.commit()
    session.refresh(encounter)
    return {"id": encounter.id, "name": encounter.name}


@router.delete("/encounters/{encounter_id}")
def delete_encounter(encounter_id: str, session: Session = Depends(get_session)):
    """Delete an encounter."""
    encounter = session.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")

    session.delete(encounter)
    session.commit()
    return {"status": "deleted"}
