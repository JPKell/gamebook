# Gamebook Authoring Tool

A visual web application for authoring interactive gamebooks organized into **series** and **books**. Each series represents a shared world with locations, items, and enemies. Each book within a series has its own story graph of acts containing nodes.

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL (SQLite for dev)
- **Frontend:** Vanilla JS + Canvas API (no framework)
- **AI:** External inference endpoint (LoadCoach or OpenAI-compatible)
- **Migration:** Alembic

## Data Model

```
Series ──< Book >── Act >── Node ──< Choice
  │                    │       │
  │                    │       └── Items/Encounters (JSON)
  │
  └── Shared Locations, Items, Encounters
```

Each entity (Location, Item, Encounter) can be **shared** (owned by the series) or **book-specific**. The shared flag is tracked via `series_id` vs `book_id` columns.

## Project Structure

```
app/
  __init__.py          # FastAPI app factory, lifespan, middleware
  config.py            # Settings from config.yaml + env vars
  database.py          # SQLAlchemy engine, session, Base class
  models/              # ORM model classes
    series.py          # Series table (top-level container)
    book.py            # Book table (FK to Series)
    act.py             # Act table (FK to Book)
    node.py            # Node table (FK to Book, story* fields)
    choice.py          # Choice table (FK to Node x2)
    location.py        # Location table (seriesId + bookId for shared/specific)
    item.py            # Item table (seriesId + bookId)
    encounter.py       # Encounter table (seriesId + bookId)
  routes/              # API route handlers
    series.py          # Series CRUD + export
    books.py           # Book CRUD (scoped to series)
    acts.py            # Act CRUD + node assignment
    nodes.py           # Node CRUD + choices
    locations.py       # Locations (series + book endpoints)
    items.py           # Items (series + book endpoints)
    encounters.py      # Encounters (series + book endpoints)
  services/            # Business logic
    inference.py       # HTTP client to external inference endpoint
    validation.py      # Graph validation rules
  static/              # Frontend files
    index.html         # Single-page app shell with modals
    css/style.css      # Dark theme styles
    js/app.js          # Vanilla JS: state, API, canvas, events
migrations/            # Alembic migrations
tests/                 # Integration tests (FastAPI TestClient)
config.example.yaml    # Template configuration
requirements.txt       # Dependencies
spec.md               # Full specification document
plan.md               # Phased work plan
```

## Quick Start

```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations (creates tables in SQLite)
cd migrations
alembic upgrade head
cd ..

# Start the development server
uvicorn app:create_app --reload --port 8000

# Run tests
pytest tests/ -v
```

The app will be available at `http://localhost:8000`.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/series/` | List all series |
| POST | `/api/series/` | Create a series |
| GET | `/api/series/{id}` | Get series (with books, shared entities) |
| PUT | `/api/series/{id}` | Update a series |
| DELETE | `/api/series/{id}` | Delete a series |
| POST | `/api/series/{id}/export` | Export series as JSON |
| GET | `/api/series/{id}/books` | List books in a series |
| POST | `/api/series/{id}/books` | Create a book |
| GET | `/api/books/{id}` | Get book with all data |
| PUT | `/api/books/{id}` | Update a book |
| DELETE | `/api/books/{id}` | Delete a book |
| GET | `/api/books/{id}/acts` | List acts in a book |
| POST | `/api/books/{id}/acts` | Create an act |
| PUT | `/api/books/{id}/acts/{id}` | Update an act |
| DELETE | `/api/books/{id}/acts/{id}` | Delete an act |
| GET | `/api/books/{id}/nodes` | List nodes in a book |
| POST | `/api/books/{id}/nodes` | Create a node |
| GET | `/api/books/{id}/nodes/{id}` | Get a node with choices |
| PUT | `/api/books/{id}/nodes/{id}` | Update a node |
| DELETE | `/api/books/{id}/nodes/{id}` | Delete a node |
| POST | `/api/books/{id}/nodes/{id}/choices` | Add a choice |
| DELETE | `/api/books/{id}/choices/{id}` | Delete a choice |
| GET | `/api/series/{id}/locations` | List shared locations |
| POST | `/api/series/{id}/locations` | Create a shared location |
| GET | `/api/books/{id}/locations` | List book locations |
| POST | `/api/books/{id}/locations` | Create a book location |
| PUT | `/api/locations/{id}` | Update a location |
| DELETE | `/api/locations/{id}` | Delete a location |
| GET | `/api/series/{id}/items` | List shared items |
| POST | `/api/series/{id}/items` | Create a shared item |
| GET | `/api/books/{id}/items` | List book items |
| POST | `/api/books/{id}/items` | Create a book item |
| PUT | `/api/items/{id}` | Update an item |
| DELETE | `/api/items/{id}` | Delete an item |
| GET | `/api/series/{id}/encounters` | List shared encounters |
| POST | `/api/series/{id}/encounters` | Create a shared encounter |
| GET | `/api/books/{id}/encounters` | List book encounters |
| POST | `/api/books/{id}/encounters` | Create a book encounter |
| PUT | `/api/encounters/{id}` | Update an encounter |
| DELETE | `/api/encounters/{id}` | Delete an encounter |

## Phases

See `plan.md` for the full phased work plan. Current phase: **Phase 1–3** (API scaffolding, routes, frontend shell).

Future phases (7+):
- AI story generation from node data
- AI playthrough simulation and evaluation
- Assembly output (PDF/EPUB/HTML)
