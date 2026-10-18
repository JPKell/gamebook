"""Generic repository base.

Concrete repositories subclass ``Repository[Model]`` and add domain queries.
Repositories never commit; the caller's unit of work (``Database.session()``
or the request-scoped session) owns the transaction.
"""

from collections.abc import Sequence
from typing import Any, ClassVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session


class NotFoundError(LookupError):
    def __init__(self, model: type, id_: str) -> None:
        super().__init__(f"{model.__name__} {id_} not found")
        self.model = model
        self.id = id_


class Repository[ModelT]:
    model: ClassVar[type[Any]]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, id_: str) -> ModelT | None:
        return self.session.get(self.model, id_)

    def require(self, id_: str) -> ModelT:
        obj = self.get(id_)
        if obj is None:
            raise NotFoundError(self.model, id_)
        return obj

    def list(self, *, limit: int | None = None, offset: int = 0) -> Sequence[ModelT]:
        stmt = select(self.model).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return self.session.scalars(stmt).all()

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(self.model)) or 0

    def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        self.session.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.session.delete(obj)
        self.session.flush()
