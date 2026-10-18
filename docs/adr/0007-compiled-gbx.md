# ADR 0007 — Compiled gbx for hot paths

**Status:** Accepted (2026-10-18)

## Context
The combat lab runs tens of thousands of fights per request; tree-walking evaluation
with exact `Fraction` arithmetic cost ~0.25 ms per fight.

## Decision
`gbx.compiler` compiles an AST once into nested closures that use plain ints and only
switch to `Fraction` when a division doesn't divide; runtime type checks are emitted
only for nodes whose type isn't fixed by construction. The engine caches compiled
closures per source string. The tree-walking `evaluator` stays the reference
implementation; a Hypothesis property test asserts both agree on generated
expressions, and the golden traces were unchanged by the switch.

## Consequences
~2–3× faster simulations (10k basic fights ≈ 1 s). Two implementations to keep in
step, guarded by the equivalence test.
