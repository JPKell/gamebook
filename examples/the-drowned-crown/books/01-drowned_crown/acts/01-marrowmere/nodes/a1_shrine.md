---
id: 467a5fd3-9be2-5d3b-aba2-f00104a67816
key: a1_shrine
title: The Roadside Shrine
summary: 'The shrine is a stone no taller than your knee, carved with a bell and ringed with offerings:
  fish hooks, a baby''s shoe, strings of green glass beads.'
location: marrowmere
variants:
- id: 78e7f31e-1ea3-59cf-9ccd-d8dd817c862f
  label: Default
choices:
- id: b924855d-273c-5d7b-9e9d-180d17644382
  label: Leave 2 Gold and ask for luck
  kind: test
  condition: GOLD >= 2
  effects:
  - op: modify
    stat: GOLD
    amount: '-2'
  test: luck
  outcomes:
  - key: success
    target: a1_shrine_blessed
  - key: failure
    target: a1_shrine_cold
- id: fe38a8a6-151a-521e-8af9-f887d4e79de0
  label: Walk on to the gate
  outcomes:
  - key: default
    target: a1_gate
layout:
  x: 320.0
  y: 0.0
prose:
- variant: 78e7f31e-1ea3-59cf-9ccd-d8dd817c862f
  text: |-
    The shrine is a stone no taller than your knee, carved with a bell and ringed with offerings: fish hooks, a baby's shoe, strings of green glass beads. Rainwater runs from the bell's carved lip into a hollow worn by a century of prayers.

    A line of verse is cut around the base. *When the bell is silent, the water is awake.*

    You could leave a coin and hope the old charm still listens, or save your gold for a town where it buys more than hope.
  summary: 'The shrine is a stone no taller than your knee, carved with a bell and ringed with offerings:
    fish hooks, a baby''s shoe, strings of green glass beads.'
  inputs_hash: d83f38649efbfb8e7cc8d4120298b6076dbaf406c3f9a9fc46ef22013f71f715
---
Optional luck beat. Costs 2 gold.
