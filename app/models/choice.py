"""
Choice model.

Defines the Choice table — a single branching option on a node that
points to a destination node. Choices are the edges of the story graph.

Constraints:
  - A choice's target node must belong to the same book as the source
    node (enforced at the API layer, not the database).
  - A node cannot choose itself (enforced at the API layer).
  - Choices are stored as a JSON array in the Node model for fast
    canvas rendering; this model provides an explicit table for
    validation, deletion, and AI playthrough tracking.

Relationships:
  - Choice.source_node: Many-to-one to Node (where choice.source_node_id = node.id).
  - Choice.target_node: Many-to-one to Node (where choice.target_id = node.id).
"""

from typing import Optional

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Choice(Base):
    __tablename__ = "choice"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("node.id"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("node.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(String, nullable=False)

    # Relationships
    source_node: Mapped["app.models.node.Node"] = relationship(
        "Node", back_populates="choices_list", foreign_keys=[source_node_id]
    )
    target_node: Mapped["app.models.node.Node"] = relationship(
        "Node", foreign_keys=[target_id]
    )
