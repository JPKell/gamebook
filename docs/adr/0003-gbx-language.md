# ADR 0003 — gbx: one small expression language

**Status:** Accepted (2026-10-17); implemented in Phase 1 (`backend/src/gamebook/core/gbx/`)

## Context
Dice rolls, enemy stat formulas per level, choice conditions, effect amounts and
combat hooks all need user-authored expressions. They must be safe, statically
checkable, printable as plain English for print editions, and portable to TypeScript.

## Decision
A hand-written lexer + Pratt parser producing a JSON-serialisable AST; a type
checker with per-use contexts (`level` in enemy formulas, `damage` in combat hooks,
…); an evaluator with an injected seeded RNG; and a print renderer for every node
type. Never Python `eval`. Effects are structured data, not free-form expressions.

Numbers are exact fractions so `level / 3` is predictable; anything that must be an
integer (stats, damage) is rounded down, and the checker nudges authors to write
`floor()`/`ceil()`/`round()` explicitly. Rename is span-based so author formatting survives.

## Consequences
One syntax for the author to learn and one editor component (CodeMirror with
autocomplete/lint). The language is deliberately small; new features need a
printer and a TS evaluator update.
