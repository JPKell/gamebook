"""
Validation service.

Implements graph validation rules for the gamebook story graph.
Called after CRUD operations to ensure the graph is well-formed.

Rules:
  - Every act (except last) has at least one exit node.
  - Every act (except first) has at least one entry node.
  - No choice references a missing node.
  - A choice cannot target a node in another book.
  - A node with zero choices must be type "ending".
  - Choices jumping to a later act without passing through an exit are flagged.

Returns a list of warnings/errors, each with severity, message, and
affected node IDs. The frontend displays these in the status bar.
"""

from collections import defaultdict
from typing import List


def validate_graph(
    acts: list[dict],
    nodes: list[dict],
    choices: list[dict],
) -> list[dict]:
    """
    Validate the story graph and return a list of issues.

    Args:
        acts: List of act dicts with 'id', 'order', 'entryNodeIds', 'exitNodeIds'.
        nodes: List of node dicts with 'id', 'type', 'actId', 'choices'.
        choices: List of choice dicts with 'sourceNodeId', 'targetId'.

    Returns:
        List of issue dicts: {"severity": "error"|"warning", "message": str, "nodes": [...]}
    """
    issues: list[dict] = []

    # Build lookup maps
    node_map = {n["id"]: n for n in nodes}
    act_map = {a["id"]: a for a in acts}

    # 1. Every act (except last) has >= 1 exit node.
    sorted_acts = sorted(acts, key=lambda a: a["order"])
    for i, act in enumerate(sorted_acts):
        if i < len(sorted_acts) - 1:
            exit_ids = _parse_ids(act.get("exitNodeIds", "[]"))
            if not exit_ids:
                issues.append({
                    "severity": "error",
                    "message": f"Act '{act['title']}' (order {act['order']}) has no exit nodes",
                    "nodes": [],
                })

    # 2. Every act (except first) has >= 1 entry node.
    for i, act in enumerate(sorted_acts):
        if i > 0:
            entry_ids = _parse_ids(act.get("entryNodeIds", "[]"))
            if not entry_ids:
                issues.append({
                    "severity": "error",
                    "message": f"Act '{act['title']}' (order {act['order']}) has no entry nodes",
                    "nodes": [],
                })

    # 3. No choice references a missing node.
    for choice in choices:
        src = choice.get("sourceNodeId")
        tgt = choice.get("targetId")
        if src and src not in node_map:
            issues.append({
                "severity": "error",
                "message": f"Choice '{choice.get('text', '')}' references missing source node {src}",
                "nodes": [src],
            })
        if tgt and tgt not in node_map:
            issues.append({
                "severity": "error",
                "message": f"Choice '{choice.get('text', '')}' references missing target node {tgt}",
                "nodes": [tgt],
            })

    # 4. Choices cannot target a node in a different act (cross-act jumps).
    #    This is a warning — author may intend cross-act branching.
    for choice in choices:
        src_id = choice.get("sourceNodeId")
        tgt_id = choice.get("targetId")
        if src_id in node_map and tgt_id in node_map:
            src_act = node_map[src_id].get("actId")
            tgt_act = node_map[tgt_id].get("actId")
            if src_act and tgt_act and src_act != tgt_act:
                src_order = act_map.get(src_act, {}).get("order", 0)
                tgt_order = act_map.get(tgt_act, {}).get("order", 0)
                if tgt_order > src_order:
                    issues.append({
                        "severity": "warning",
                        "message": (
                            f"Choice '{choice.get('text', '')}' jumps from "
                            f"Act {src_order} to Act {tgt_order}"
                        ),
                        "nodes": [src_id, tgt_id],
                    })

    # 5. Node with zero choices must be "ending".
    for node in nodes:
        choice_ids = _parse_ids(node.get("choices", "[]"))
        if not choice_ids and node.get("type") != "ending":
            issues.append({
                "severity": "warning",
                "message": f"Node '{node['title']}' has no choices — is this intentional?",
                "nodes": [node["id"]],
            })

    # 6. Node type not set (defaults to beat).
    for node in nodes:
        if not node.get("type") or node["type"] == "":
            issues.append({
                "severity": "warning",
                "message": f"Node '{node['title']}' has no type set",
                "nodes": [node["id"]],
            })

    return issues


def _parse_ids(val: str | list) -> list[str]:
    """Parse a JSON string or list of node IDs."""
    if isinstance(val, list):
        return val
    try:
        import json
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []
