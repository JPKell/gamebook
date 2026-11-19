---
id: 3fcfd333-2bb7-50fc-8ff9-d6ef03efc4c7
key: a1_alley
title: Fishgut Alley
summary: The alley is a gutter between two blind walls, stinking of fish and wet brick.
location: marrowmere
variants:
- id: 4e1ab75e-c98b-5c59-8c11-59e832a6eda0
  label: Default
encounters:
- id: 724f4264-9cf9-5c5c-b395-0d55a33a3cd0
  label: The cutpurse
  enemies:
  - enemy: cutpurse
    level: 1
    count: 1
choices:
- id: 2e52ffef-5bb3-51d4-a457-dbbd33f8577f
  label: Fight the cutpurse
  kind: combat
  encounter: 724f4264-9cf9-5c5c-b395-0d55a33a3cd0
  flee_allowed: true
  outcomes:
  - key: win
    target: a1_square
  - key: lose
    target: a1_death_alley
  - key: flee
    target: a1_square
- id: a1a5c404-c688-5ecb-b479-f5052b7f5d85
  label: Back away to the square
  outcomes:
  - key: default
    target: a1_square
layout:
  x: 960.0
  y: 680.0
prose:
- variant: 4e1ab75e-c98b-5c59-8c11-59e832a6eda0
  text: |-
    The alley is a gutter between two blind walls, stinking of fish and wet brick. Halfway down, a figure steps out of a doorway. He is young, thin and badly frightened, and he holds a long knife in a hand that shakes.

    "Your purse," he says. "Please."

    The word *please* makes it worse. He does not want to do this, and that makes him dangerous.
  summary: The alley is a gutter between two blind walls, stinking of fish and wet brick.
  inputs_hash: 53ef85622102f88dbd644593aea9d82c1da6b046d6e39eac90b7b4713616106b
---
A quick early fight to test the player's combat. Fleeing is allowed and costs 2 STAMINA.
