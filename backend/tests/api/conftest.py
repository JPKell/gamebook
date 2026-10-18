from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

Json = dict[str, Any]


class Api:
    """Thin helper: asserts status codes and returns JSON."""

    def __init__(self, client: TestClient) -> None:
        self.c = client

    def _do(self, method: str, url: str, expect: int, **kw: Any) -> Any:
        res = self.c.request(method, f"/api{url}", **kw)
        assert res.status_code == expect, f"{method} {url} → {res.status_code}: {res.text}"
        return res.json() if res.content else None

    def get(self, url: str, expect: int = 200, **kw: Any) -> Any:
        return self._do("GET", url, expect, **kw)

    def post(self, url: str, json: Any = None, expect: int = 201, **kw: Any) -> Any:
        return self._do("POST", url, expect, json=json, **kw)

    def patch(self, url: str, json: Any, expect: int = 200) -> Any:
        return self._do("PATCH", url, expect, json=json)

    def put(self, url: str, json: Any, expect: int = 200) -> Any:
        return self._do("PUT", url, expect, json=json)

    def delete(self, url: str, expect: int = 204, **kw: Any) -> Any:
        return self._do("DELETE", url, expect, **kw)


@pytest.fixture
def api(client: TestClient) -> Api:
    return Api(client)


@pytest.fixture
def series(api: Api) -> Json:
    s: Json = api.post("/series", {"title": "The Ashen Cycle"})
    return s


@pytest.fixture
def book(api: Api, series: Json) -> Json:
    b: Json = api.post(f"/series/{series['id']}/books", {"title": "The Haunted Bridge"})
    return b


@pytest.fixture
def graph(api: Api, book: Json) -> Callable[[], Json]:
    def get() -> Json:
        g: Json = api.get(f"/books/{book['id']}/graph")
        return g

    return get
