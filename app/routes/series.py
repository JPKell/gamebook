"""
Series routes.

API endpoints for creating, reading, updating, and deleting Series.
Also handles listing all books within a series and exporting the full
series (with all books) as a JSON file.

Endpoints:
  GET    /api/series/            — List all series.
  POST   /api/series/            — Create a new series.
  GET    /api/series/{id}        — Get a series by ID (with books).
  PUT    /api/series/{id}        — Update a series.
  DELETE /api/series/{id}        — Delete a series and all its books.
  POST   /api/series/{id}/export — Export the series as a JSON file.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_session, Base, engine
from app.models.series import Series
from app.models.book import Book
from app.models.location import Location
from app.models.item import Item
from app.models.encounter import Encounter

router = APIRouter()


@router.get("/", response_model=List[dict])
def list_series(session: Session = Depends(get_session)):
    """Return all series."""
    return [
        {
            "id": s.id,
            "title": s.title,
            "description": s.description,
            "tone": s.tone,
            "createdAt": s.createdAt.isoformat(),
        }
        for s in session.query(Series).order_by(Series.createdAt.desc()).all()
    ]


@router.post("/", response_model=dict)
def create_series(
    body: dict,
    session: Session = Depends(get_session),
):
    """
    Create a new series.

    Expects a JSON body with at least 'title'. Optional fields:
    description, tone, worldGuidelines.
    """
    title = body.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    import uuid
    series = Series(
        id=str(uuid.uuid4()),
        title=title,
        description=body.get("description"),
        tone=body.get("tone"),
        worldGuidelines=body.get("worldGuidelines"),
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    return {
        "id": series.id,
        "title": series.title,
        "description": series.description,
        "tone": series.tone,
        "createdAt": series.createdAt.isoformat(),
    }


@router.get("/{series_id}", response_model=dict)
def get_series(series_id: str, session: Session = Depends(get_session)):
    """
    Get a series by ID, including its books, shared locations,
    shared items, and shared encounters.
    """
    series = session.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    books = session.query(Book).filter(Book.series_id == series_id).all()

    shared_locations = (
        session.query(Location)
        .filter(Location.series_id == series_id)
        .filter(Location.book_id.is_(None))
        .all()
    )
    shared_items = (
        session.query(Item)
        .filter(Item.series_id == series_id)
        .filter(Item.book_id.is_(None))
        .all()
    )
    shared_encounters = (
        session.query(Encounter)
        .filter(Encounter.series_id == series_id)
        .filter(Encounter.book_id.is_(None))
        .all()
    )

    def _serialize(obj, kind):
        data = {"id": obj.id, "name": obj.name, "description": obj.description}
        if kind == "item" and hasattr(obj, "effect"):
            data["effect"] = obj.effect
        if kind == "encounter" and hasattr(obj, "stats"):
            data["stats"] = obj.stats
            data["recurring"] = bool(obj.recurring)
        return data

    return {
        "id": series.id,
        "title": series.title,
        "description": series.description,
        "tone": series.tone,
        "worldGuidelines": series.worldGuidelines,
        "createdAt": series.createdAt.isoformat(),
        "books": [{"id": b.id, "title": b.title, "number": b.number} for b in books],
        "sharedLocations": [_serialize(l, "location") for l in shared_locations],
        "sharedItems": [_serialize(i, "item") for i in shared_items],
        "sharedEncounters": [_serialize(e, "encounter") for e in shared_encounters],
    }


@router.put("/{series_id}", response_model=dict)
def update_series(
    series_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    """Update a series. Only provided fields are changed."""
    series = session.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    for field in ("title", "description", "tone", "worldGuidelines"):
        if field in body:
            setattr(series, field, body[field])

    session.commit()
    session.refresh(series)
    return {"id": series.id, "title": series.title}


@router.delete("/{series_id}")
def delete_series(series_id: str, session: Session = Depends(get_session)):
    """Delete a series and cascade to all books, acts, nodes, etc."""
    series = session.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    session.delete(series)
    session.commit()
    return {"status": "deleted"}


@router.post("/{series_id}/export")
def export_series(series_id: str, session: Session = Depends(get_session)):
    """
    Export the full series as a JSON object including all books,
    nodes, acts, and entities. Used by the frontend's "Download JSON"
    button.
    """
    from app.models.book import Book
    from app.models.act import Act
    from app.models.node import Node
    from app.models.choice import Choice
    from app.models.location import Location
    from app.models.item import Item
    from app.models.encounter import Encounter

    series = session.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")

    books = session.query(Book).filter(Book.series_id == series_id).all()
    book_data = []
    for book in books:
        acts = session.query(Act).filter(Act.book_id == book.id).all()
        nodes = session.query(Node).filter(Node.book_id == book.id).all()
        choices = (
            session.query(Choice).filter(Choice.source_node_id.in_(
                [n.id for n in nodes]
            )).all()
        )
        book_locations = session.query(Location).filter(
            Location.book_id == book.id
        ).all()
        book_items = session.query(Item).filter(
            Item.book_id == book.id
        ).all()
        book_encounters = session.query(Encounter).filter(
            Encounter.book_id == book.id
        ).all()

        book_data.append({
            "id": book.id,
            "title": book.title,
            "number": book.number,
            "description": book.description,
            "acts": [
                {"id": a.id, "title": a.title, "order": a.order,
                 "entryNodeIds": a.entryNodeIds, "exitNodeIds": a.exitNodeIds,
                 "nodeIds": a.nodeIds, "hasEndings": a.hasEndings}
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
            "bookLocations": [_serialize_loc(l) for l in book_locations],
            "bookItems": [_serialize_item(i) for i in book_items],
            "bookEncounters": [_serialize_enc(e) for e in book_encounters],
        })

    shared_locations = (
        session.query(Location).filter(
            Location.series_id == series_id, Location.book_id.is_(None)
        ).all()
    )
    shared_items = (
        session.query(Item).filter(
            Item.series_id == series_id, Item.book_id.is_(None)
        ).all()
    )
    shared_encounters = (
        session.query(Encounter).filter(
            Encounter.series_id == series_id, Encounter.book_id.is_(None)
        ).all()
    )

    export_data = {
        "version": 1,
        "series": {
            "id": series.id,
            "title": series.title,
            "description": series.description,
            "tone": series.tone,
            "worldGuidelines": series.worldGuidelines,
            "sharedLocations": [_serialize_loc(l) for l in shared_locations],
            "sharedItems": [_serialize_item(i) for i in shared_items],
            "sharedEncounters": [_serialize_enc(e) for e in shared_encounters],
        },
        "books": book_data,
    }

    return export_data


def _serialize_loc(obj):
    return {"id": obj.id, "name": obj.name, "description": obj.description}

def _serialize_item(obj):
    return {"id": obj.id, "name": obj.name, "description": obj.description, "effect": obj.effect}

def _serialize_enc(obj):
    return {
        "id": obj.id, "name": obj.name, "description": obj.description,
        "stats": obj.stats, "recurring": bool(obj.recurring),
    }
