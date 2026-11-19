---
id: 642259b4-ab28-54df-bd9c-76d825018689
key: a2_causeway
title: The Old Causeway
summary: Midway across the fen the mist thickens into a wet wall.
location: the_fen
variants:
- id: 4961bd3a-f8af-506d-98fa-c382ea2877dc
  label: Default
encounters:
- id: e63fa7d8-b696-5391-9402-7254a5448074
  label: Whatever the fen sends
  mode: table
  table: fen_wanderers
choices:
- id: dcc56f23-e2c3-5293-9b4f-57972b8e1f32
  label: Stand your ground on the causeway
  kind: combat
  encounter: e63fa7d8-b696-5391-9402-7254a5448074
  outcomes:
  - key: win
    target: a2_wisps
  - key: lose
    target: a2_death_fen
- id: 4d7a4916-2972-5557-a98a-282fd983e75d
  label: Slip into the reeds and hurry on
  effects:
  - op: modify
    stat: STAMINA
    amount: '-2'
  outcomes:
  - key: default
    target: a2_wisps
layout:
  x: 2880.0
  y: 0.0
prose:
- variant: 4961bd3a-f8af-506d-98fa-c382ea2877dc
  text: |-
    Midway across the fen the mist thickens into a wet wall. The causeway narrows. You walk by feel, with one hand on the broken parapet, and the stones are slick underfoot.

    Ahead, the water stirs. Something comes up the road toward you, in no hurry, wading where there is no water.

    You could meet it, or you could slip off the path into the reeds and trust the mist to hide you. Neither, you suspect, is as safe as it sounds.
  summary: Midway across the fen the mist thickens into a wet wall.
  inputs_hash: d0af2bd319d6a28d23c75c728c5be7364df88b8e738935f0e07dd658286ca60e
---
Table encounter. The fen sends a different visitor each time (see the Fen Wanderers table). Slipping away costs 2 STAMINA in cold and mud.
