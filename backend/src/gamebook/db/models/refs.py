"""RefIndex: a derived table of every reference in the content.

Rebuilt per source on every write (see ``services/refs.py``). Powers
where-used, item totals, key renames and the "codeword never set" check.
"""

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from gamebook.db.base import Base


class RefIndex(Base):
    __tablename__ = "ref_index"
    __table_args__ = (
        Index("ix_ref_index_source", "source_type", "source_id"),
        Index("ix_ref_index_target_id", "target_type", "target_id"),
        Index("ix_ref_index_target_key", "series_id", "target_type", "target_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"))
    book_id: Mapped[str | None] = mapped_column(ForeignKey("book.id", ondelete="CASCADE"))
    #: node | choice | variant | encounter | enemy | item | table | character | rule_system
    source_type: Mapped[str] = mapped_column(String(16))
    source_id: Mapped[str] = mapped_column(String(36))
    #: Node the reference lives on (for navigation), if any.
    node_id: Mapped[str | None] = mapped_column(String(36))
    #: item | enemy | table | node | flag | skill | class | stat | tier | character | lore
    target_type: Mapped[str] = mapped_column(String(16))
    target_key: Mapped[str] = mapped_column(String(64))
    #: Resolved entity id when the key matches an entity.
    target_id: Mapped[str | None] = mapped_column(String(36))
    #: e.g. "condition", "effect.give", "placement", "shop", "encounter", "outcome"
    role: Mapped[str] = mapped_column(String(32))
    field: Mapped[str] = mapped_column(String(128), default="")
    qty: Mapped[int | None] = mapped_column(Integer)
