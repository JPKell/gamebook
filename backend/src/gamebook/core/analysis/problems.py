"""Validation results."""

from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning", "info"]
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class Problem:
    severity: Severity
    code: str
    message: str
    act_id: str | None = None
    node_id: str | None = None
    choice_id: str | None = None
    #: For entity problems: "item", "enemy", "table", "rule_system", ...
    entity_type: str | None = None
    entity_id: str | None = None
    #: Dotted path to the offending field, e.g. "condition", "effects[1].amount".
    field: str | None = None
