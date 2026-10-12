"""
Frontend static shell.

Serves the single-page frontend application. The frontend is a vanilla
JavaScript app (HTML + CSS + JS) that communicates with the FastAPI
API via fetch calls.

The main entry point is app/static/index.html. All other static files
(CSS, JS, images) live under app/static/.

In production, this is served by the FastAPI mount at /static.
In development, you can serve directly with:
  python -m http.server --directory app/static 8001
"""
