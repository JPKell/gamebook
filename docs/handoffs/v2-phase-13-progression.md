# v2 Phase 13 — Character progression

**Status:** Complete · **Date:** 2026-10-19 · **Branch:** `v2` · **ADR:** 0014

Built from author feedback:
- equipment couldn't change stats
- Gold was hard to find and to award
- there was no starting gear
- classes had no stat modifiers
- there was no XP or levelling

## What was built

### Rules (`core/rules/schema.py`)
- `StatBonus{stat, amount}`: gbx, dice allowed, variable `level`.
- `StartingItem{item, qty, equip}`.
- `ClassDef.modifiers` and `ClassDef.starting_items`.
- `TierDef.starting_items`: accumulates down the chain.
- `TierDef.progression` (`ProgressionDef`): `xp_stat`, `level_stat`, `xp_award` (variables `enemy_level` and `level`), `xp_to_next` (variable `level`, no dice), `max_level`, `level_up`. Each field inherits separately.
- `tier_view` adds `progression`, `progression_origin` and `starting_items` (with origin).
- **Default template:**
  - Medium adds XP and LEVEL, plus levelling: `max(1, 10 + 5 * (enemy_level - level))` XP per enemy, `100 * level` XP per level, max level 10, +2 STAMINA per level, +1 SKILL every third level.
  - Advanced classes get stat bonuses.
- **gbx contexts:** `xp_award`, `xp_to_next`, `stat_bonus`.

### Engine (Python and TypeScript, in parity)
- **Creation order:** roll the stats → class skills and bonuses (a bonus also raises a starting-value maximum) → `character_created` → starting gear (tier, then class), logged as `effect` events with source `start`.
- **XP:** winning a fight adds the XP award per enemy (`xp_gained`).
- **Levelling:** checked after any change to the XP stat:
  - it spends XP and raises the level (`level_up`), then applies the bonuses (`effect` events with source `level_up`)
  - it stops at `max_level`, at the level stat's maximum, or when `xp_to_next` is non-positive or broken
  - at most 100 levels per change
- `xp_needed()` / `xpNeeded()` give the XP the next level costs, for display.
- **Regenerated:** the golden traces, and the parity corpus. The corpus's edge book has cheap levels, starting gear, rolled bonuses, unknown items and stats, and a dice `xp_to_next`.

### Validation
- unknown bonus stats
- gbx in bonuses and formulas
- XP or level stats that aren't player stats, or are the same stat
- incomplete levelling (a warning)
- a capped XP stat, or a level stat whose maximum is its starting value (a warning)
- starting items not in the book (a warning, from book validation)

### Authoring UI
- **Item editor:** "Stat modifiers" shows for every category, and says when the item counts (equipped in its slot, or carried).
- **Effects editor:** a quick money field.
  - Node arrival: first time only by default.
  - Choices: every time by default.
- **Mechanics designer:**
  - Classes get stat bonuses and starting gear.
  - A "Starting gear" section.
  - An "Experience & levels" section, with inherit badges and a "Set up experience & levels" button.
- **Adventure sheets** (the playtest player and the web player): a headline with money, level and XP / next. `PlayOut` gains `currency` and `progress`.

### Print
- **"Your Character":**
  - class bonuses (mentioning the maximum when it moves) and class gear
  - starting gear
  - an Experience paragraph phrased from the formulas
- **Fight tables:** show enemy levels when fights give XP.

## Bug pass (independent review)
- **Fixed:**
  - "Set up experience & levels" did nothing for definitions loaded from the API, because their null fields overwrote the defaults. The button now keeps only fields that are set; a test covers it.
  - Printed bonuses didn't say the maximum rises too.
  - The web player's level headline showed when levelling was incomplete. It now uses the server's test.
  - `xp_needed` ignored a level stat's maximum.
  - The quiet flag is now restored rather than reset.
  - The money field no longer saves when it is cleared while empty.
  - "(equipped)" is printed only when the tier has the item's slot.
  - Class descriptions ending in "." no longer print "..".
- **Added:** a warning for capped XP or level stats.
- **Left as is:**
  - The money field uses the first resource across the tiers, not per tier.
  - A fight that earns 0 XP still logs `xp_gained` (both engines).
  - Rule-level warnings repeat for each tier that inherits them.

## Tests
- `tests/core/test_progression.py` (11):
  - class bonuses and maximums
  - rolled and unknown bonuses
  - starting gear: tiers, class, equipping, no slots, unknown items
  - XP by relative level, and none for fleeing, losing or Basic
  - level-ups and their bonuses
  - caps and broken formulas
  - inheritance
  - validation
- **API:** the play view's money and progress, and XP from a won fight; the proof's Experience text, enemy levels, class bonuses and starting gear.
- **Frontend:** `CurrencyQuick` (4), the levelling helpers in `defs` (3), and parity (goldens and corpus).
- **e2e:** the export proof selector allows "ORC (level 1)".

## Notes
- Existing series keep their stored rule systems, so they don't get XP or levels until the author adds them: Mechanics → tier → "Experience & levels" → "Set up experience & levels".
- Item modifiers always applied in the engine to any held item without a slot. Before this phase only the editor hid them.
