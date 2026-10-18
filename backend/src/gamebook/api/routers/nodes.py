"""Nodes and their parts."""

from fastapi import APIRouter, status

from gamebook.api.deps import SessionDep
from gamebook.db.models import Choice, Encounter, Node, TextVariant
from gamebook.schemas.common import Reorder
from gamebook.schemas.node import (
    ChoiceCreate,
    ChoiceOut,
    ChoiceUpdate,
    EncounterIn,
    EncounterOut,
    NodeCreate,
    NodeOut,
    NodeUpdate,
    PlacementIn,
    ShopIn,
    VariantIn,
    VariantOut,
    VariantUpdate,
)
from gamebook.services import history
from gamebook.services import nodes as svc
from gamebook.services.common import require

router = APIRouter(tags=["nodes"])


def _node_label(session: SessionDep, node_id: str, data: NodeUpdate) -> str:
    fields = data.model_fields_set
    if fields <= {"x", "y"}:
        return "Move node"
    return f"Edit node '{require(session, Node, node_id).title}'"


def _fresh(session: SessionDep, node: Node) -> Node:
    session.flush()
    session.refresh(node)
    return node


@router.post("/books/{book_id}/nodes", response_model=NodeOut, status_code=status.HTTP_201_CREATED)
def create_node(book_id: str, data: NodeCreate, session: SessionDep) -> Node:
    history.record(session, book_id, f"Add node '{data.title}'")
    return _fresh(session, svc.create_node(session, book_id, data))


@router.get("/nodes/{node_id}", response_model=NodeOut)
def get_node(node_id: str, session: SessionDep) -> Node:
    return require(session, Node, node_id)


@router.patch("/nodes/{node_id}", response_model=NodeOut)
def update_node(node_id: str, data: NodeUpdate, session: SessionDep) -> Node:
    history.record_for(session, Node, node_id, _node_label(session, node_id, data))
    return _fresh(session, svc.update_node(session, node_id, data))


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(node_id: str, session: SessionDep) -> None:
    history.record_for(
        session, Node, node_id, f"Delete node '{require(session, Node, node_id).title}'"
    )
    svc.delete_node(session, node_id)


# ── variants ─────────────────────────────────────────────────────────────


@router.post(
    "/nodes/{node_id}/variants", response_model=VariantOut, status_code=status.HTTP_201_CREATED
)
def create_variant(node_id: str, data: VariantIn, session: SessionDep) -> TextVariant:
    history.record_for(session, Node, node_id, "Add text variant")
    return svc.create_variant(session, node_id, data)


@router.put("/nodes/{node_id}/variants/order", response_model=list[VariantOut])
def reorder_variants(node_id: str, data: Reorder, session: SessionDep) -> list[TextVariant]:
    history.record_for(session, Node, node_id, "Reorder text variants")
    return svc.reorder_variants(session, node_id, data.ids)


@router.patch("/variants/{variant_id}", response_model=VariantOut)
def update_variant(variant_id: str, data: VariantUpdate, session: SessionDep) -> TextVariant:
    history.record_for(session, TextVariant, variant_id, "Edit text variant")
    return svc.update_variant(session, variant_id, data)


@router.delete("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(variant_id: str, session: SessionDep) -> None:
    history.record_for(session, TextVariant, variant_id, "Delete text variant")
    svc.delete_variant(session, variant_id)


# ── choices ──────────────────────────────────────────────────────────────


@router.post(
    "/nodes/{node_id}/choices", response_model=ChoiceOut, status_code=status.HTTP_201_CREATED
)
def create_choice(node_id: str, data: ChoiceCreate, session: SessionDep) -> Choice:
    history.record_for(session, Node, node_id, "Add choice")
    return svc.create_choice(session, node_id, data)


@router.put("/nodes/{node_id}/choices/order", response_model=list[ChoiceOut])
def reorder_choices(node_id: str, data: Reorder, session: SessionDep) -> list[Choice]:
    history.record_for(session, Node, node_id, "Reorder choices")
    return svc.reorder_choices(session, node_id, data.ids)


@router.patch("/choices/{choice_id}", response_model=ChoiceOut)
def update_choice(choice_id: str, data: ChoiceUpdate, session: SessionDep) -> Choice:
    history.record_for(session, Choice, choice_id, "Edit choice")
    return svc.update_choice(session, choice_id, data)


@router.delete("/choices/{choice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_choice(choice_id: str, session: SessionDep) -> None:
    history.record_for(session, Choice, choice_id, "Delete choice")
    svc.delete_choice(session, choice_id)


# ── encounters, items, shop ──────────────────────────────────────────────


@router.post(
    "/nodes/{node_id}/encounters", response_model=EncounterOut, status_code=status.HTTP_201_CREATED
)
def create_encounter(node_id: str, data: EncounterIn, session: SessionDep) -> Encounter:
    history.record_for(session, Node, node_id, "Add encounter")
    return svc.create_encounter(session, node_id, data)


@router.put("/encounters/{encounter_id}", response_model=EncounterOut)
def update_encounter(encounter_id: str, data: EncounterIn, session: SessionDep) -> Encounter:
    history.record_for(session, Encounter, encounter_id, "Edit encounter")
    return svc.update_encounter(session, encounter_id, data)


@router.delete("/encounters/{encounter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_encounter(encounter_id: str, session: SessionDep) -> None:
    history.record_for(session, Encounter, encounter_id, "Delete encounter")
    svc.delete_encounter(session, encounter_id)


@router.put("/nodes/{node_id}/items", response_model=NodeOut)
def set_node_items(node_id: str, data: list[PlacementIn], session: SessionDep) -> Node:
    history.record_for(session, Node, node_id, "Edit items found")
    return _fresh(session, svc.set_placements(session, node_id, data))


@router.put("/nodes/{node_id}/shop", response_model=NodeOut)
def set_node_shop(node_id: str, data: ShopIn, session: SessionDep) -> Node:
    history.record_for(session, Node, node_id, "Edit shop")
    return _fresh(session, svc.set_shop(session, node_id, data))
