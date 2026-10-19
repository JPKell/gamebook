# ADR 0014: Character progression

**Status:** Accepted (2026-10-19)

## Context
Authors asked for:
- class stat bonuses
- starting gear
- experience from fights that depends on the enemy's level against the reader's
- levelling up

The engine has to stay deterministic and printable, and identical in Python and TypeScript.

## Decision
- **Progression lives in the rule tier** (`progression`). Each field inherits separately,
  like combat.
  - XP and level are ordinary player stats, chosen by key. They print on the
    adventure sheet, work in conditions (`LEVEL >= 3`) and can be changed by effects.
  - The formulas are gbx:
    - `xp_award` uses `enemy_level` and `level`.
    - `xp_to_next` uses `level` and allows no dice, so a printed book can tabulate it.
    - Level-up bonuses use `level`.
- **XP is spent on levelling up** (whatever is left carries over), rather than being a
  running total compared with thresholds. "Cross out 100 XP and add 1 to your LEVEL" is
  easy to do with a pencil.
- **Level-ups happen whenever the XP stat changes**, not only after fights, so
  `modify XP 50` rewards work too. A non-positive or broken `xp_to_next` stops
  levelling, and at most 100 levels are gained per change, so a bad formula can't hang
  the game.
- **Class bonuses are one-off at creation**, not ongoing modifiers. They raise the
  starting value, and the maximum when the maximum is the starting value. This matches
  the paper procedure ("add 1 to your SKILL"). Item modifiers stay the ongoing kind.
- **Starting gear accumulates down the tiers**, then the class's is added. Gear names
  item keys, which are checked against each book (a warning, because items belong to
  books while rules belong to the series). An unknown item at runtime is a content-error
  event.

## Consequences
- The default template gains XP and LEVEL at Medium and class bonuses at Advanced.
  Existing series keep their stored rule systems, and the designer's "Set up experience
  & levels" adds the defaults to one.
- New events: `xp_gained` and `level_up`. Start gear is logged as `effect` events with
  source `start`, and level-up bonuses with source `level_up`. The golden traces and the
  parity corpus were regenerated; the corpus's edge book exercises cheap levels,
  starting gear and broken formulas.
- Bundles from before this change load in the TypeScript player, because the missing
  fields default to empty.
