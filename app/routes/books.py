"""
Book routes (series-scoped).

Endpoints for listing and creating books within a series.
These routes live under /api/series/{series_id}/books.

Endpoints:
  GET    /api/series/{series_id}/books              — List books in a series.
  POST   /api/series/{series_id}/books              — Create a new book.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session
from app.models.book import Book
from app.models.series import Series

# The series_id is embedded in the route path, not the prefix.
router = APIRouter()


@router.get("/{series_id}/books", response_model=list[dict])
def list_books(series_id: str, session: Session = Depends(get_session)):
    """Return all books in a series."""
    books = (
        session.query(Book)
        .filter(Book.series_id == series_id)
        .order_by(Book.number)
        .all()
    )
    return [
        {"id": b.id, "title": b.title, "number": b.number,
         "description": b.description}
        for b in books
    ]


@router.post("/{series_id}/books", response_model=dict)
def create_book(
    series_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Create a new book within a series."""
    series = session.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    title = body.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    import uuid
    book = Book(
        id=str(uuid.uuid4()),
        series_id=series_id,
        title=title,
        description=body.get("description"),
        number=body.get("number"),
    )
    session.add(book)
    session.commit()
    session.refresh(book)
    return {"id": book.id, "title": book.title, "number": book.number}
