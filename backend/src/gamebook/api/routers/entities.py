"""CRUD for series entities, generated per kind with typed schemas."""

from typing import Any

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from gamebook.api.deps import SessionDep
from gamebook.schemas import entities as s
from gamebook.services import entities as svc
from gamebook.services.common import require

router = APIRouter(tags=["entities"])

# kind, plural path, singular name, create, update, out
_SPECS: list[tuple[str, str, str, type[BaseModel], type[BaseModel], type[BaseModel]]] = [
    ("enemy", "enemies", "enemy", s.EnemyCreate, s.EnemyUpdate, s.EnemyOut),
    ("item", "items", "item", s.ItemCreate, s.ItemUpdate, s.ItemOut),
    ("table", "tables", "table", s.TableCreate, s.TableUpdate, s.TableOut),
    ("character", "characters", "character", s.CharacterCreate, s.CharacterUpdate, s.CharacterOut),
    ("lore", "lore", "lore_entry", s.LoreCreate, s.LoreUpdate, s.LoreOut),
]


def _register(
    kind_name: str,
    plural: str,
    singular: str,
    create_model: type[BaseModel],
    update_model: type[BaseModel],
    out_model: type[BaseModel],
) -> None:
    kind = svc.KINDS[kind_name]

    def list_(
        series_id: str,
        session: SessionDep,
        book_id: str | None = Query(default=None, description="Only entities usable in this book"),
    ) -> list[Any]:
        return svc.list_entities(session, kind, series_id, book_id)

    def create(series_id: str, data: create_model, session: SessionDep) -> Any:  # type: ignore[valid-type]
        return svc.create_entity(session, kind, series_id, data)

    def get(entity_id: str, session: SessionDep) -> Any:
        return require(session, kind.model, entity_id)

    def update(entity_id: str, data: update_model, session: SessionDep) -> Any:  # type: ignore[valid-type]
        return svc.update_entity(session, kind, entity_id, data)

    def delete(entity_id: str, session: SessionDep, force: bool = Query(default=False)) -> None:
        svc.delete_entity(session, kind, entity_id, force=force)

    list_model: Any = list[out_model]  # type: ignore[valid-type]
    router.add_api_route(
        f"/series/{{series_id}}/{plural}",
        list_,
        methods=["GET"],
        response_model=list_model,
        name=f"list_{plural}",
    )
    router.add_api_route(
        f"/series/{{series_id}}/{plural}",
        create,
        methods=["POST"],
        response_model=out_model,
        status_code=status.HTTP_201_CREATED,
        name=f"create_{singular}",
    )
    router.add_api_route(
        f"/{plural}/{{entity_id}}",
        get,
        methods=["GET"],
        response_model=out_model,
        name=f"get_{singular}",
    )
    router.add_api_route(
        f"/{plural}/{{entity_id}}",
        update,
        methods=["PATCH"],
        response_model=out_model,
        name=f"update_{singular}",
    )
    router.add_api_route(
        f"/{plural}/{{entity_id}}",
        delete,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
        name=f"delete_{singular}",
    )


for _spec in _SPECS:
    _register(*_spec)
