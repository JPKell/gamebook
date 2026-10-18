"""gbx diagnostics."""

from dataclasses import dataclass
from typing import Literal

from gamebook.core.gbx.ast import Span

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    span: Span


class GbxSyntaxError(ValueError):
    def __init__(self, message: str, span: Span) -> None:
        super().__init__(f"{message} (at {span.start})")
        self.message = message
        self.span = span

    def diagnostic(self) -> Diagnostic:
        return Diagnostic("error", "syntax", self.message, self.span)


class GbxEvalError(ValueError):
    """Raised when evaluating an expression that did not pass the checker."""
