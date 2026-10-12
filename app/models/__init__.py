"""
SQLAlchemy ORM models.

Each file defines one or more model classes that map to database tables.
Models follow the hierarchy:

    Series ──< Book >── Act >── Node ──< Choice
      │                    │       │
      │                    │       └── Items (many-to-many via junction table)
      │                    │       └── Encounters (many-to-many via junction table)
      │
      └── Locations, Items, Encounters (shared when series_id is set)

Foreign keys enforce referential integrity:
  - Book.series_id → Series.id
  - Act.book_id → Book.id
  - Node.book_id → Book.id
  - Choice.source_node_id → Node.id
  - Choice.target_id → Node.id (must be in the same book)

Shared entities (Location, Item, Encounter) have nullable series_id
and book_id columns. If series_id is set, the entity is shared across
all books in that series. If only book_id is set, it is book-specific.
"""

from app.models.series import Series
from app.models.book import Book
from app.models.act import Act
from app.models.node import Node
from app.models.choice import Choice
from app.models.location import Location
from app.models.item import Item
from app.models.encounter import Encounter

__all__ = [
    "Series",
    "Book",
    "Act",
    "Node",
    "Choice",
    "Location",
    "Item",
    "Encounter",
]
