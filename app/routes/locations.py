"""
Location routes.

API endpoints for managing locations. Two sets of endpoints:
  - Series-level: manage shared locations (series_id set, book_id null).
  - Book-level: manage book-specific locations (book_id set, series_id null).

Endpoints:
  GET    /api/series/{series_id}/locations        — List shared locations.
  POST   /api/series/{series_id}/locations        — Create a shared location.
  GET    /api/books/{book_id}/locations           — List book-specific locations.
  POST   /api/books/{book_id}/locations           — Create a book-specific location.
  PUT    /api/locations/{location_id}             — Update any location.
  DELETE /api/locations/{location_id}             — Delete any location.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models.location import Location
from app.models.book import Book
from app.models.series import Series

router = APIRouter()


@router.get("/series/{series_id}/locations", response_model=list[dict])
def list_shared_locations(series_id: str, session: Session = Depends(get_session)):
    """Return locations shared across a series."""
    locations = (
        session.query(Location)
        .filter(Location.series_id == series_id)
        .filter(Location.book_id.is_(None))
        .all()
    )
    return [
        {"id": l.id, "name": l.name, "description": l.description, "shared": True}
        for l in locations
    ]


@router.post("/series/{series_id}/locations", response_model=dict)
def create_shared_location(
    series_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Create a location shared across all books in a series."""
    series = session.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    import uuid
    location = Location(
        id=str(uuid.uuid4()),
        series_id=series_id,
        name=name,
        description=body.get("description"),
    )
    session.add(location)
    session.commit()
    session.refresh(location)
    return {
        "id": location.id,
        "name": location.name,
        "description": location.description,
        "shared": True,
    }


@router.get("/books/{book_id}/locations", response_model=list[dict])
def list_book_locations(book_id: str, session: Session = Depends(get_session)):
    """Return book-specific locations."""
    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    locations = (
        session.query(Location)
        .filter(Location.book_id == book_id)
        .filter(Location.series_id.is_(None))
        .all()
    )
    return [
        {"id": l.id, "name": l.name, "description": l.description, "shared": False}
        for l in locations
    ]


@router.post("/books/{book_id}/locations", response_model=dict)
def create_book_location(
    book_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Create a location specific to one book."""
    book = session.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    import uuid
    location = Location(
        id=str(uuid.uuid4()),
        book_id=book_id,
        name=name,
        description=body.get("description"),
    )
    session.add(location)
    session.commit()
    session.refresh(location)
    return {
        "id": location.id,
        "name": location.name,
        "description": location.description,
        "shared": False,
    }


@router.put("/locations/{location_id}", response_model=dict)
def update_location(
    location_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Update a location's name or description."""
    location = session.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    for field in ("name", "description"):
        if field in body:
            setattr(location, field, body[field])

    session.commit()
    session.refresh(location)
    return {"id": location.id, "name": location.name}


@router.delete("/locations/{location_id}")
def delete_location(location_id: str, session: Session = Depends(get_session)):
    """Delete a location."""
    location = session.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    session.delete(location)
    session.commit()
    return {"status": "deleted"}
