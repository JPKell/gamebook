---
id: 11dd5831-e045-5ed5-8115-e34f504ecf44
key: a3_trap
title: Needles
summary: The rings spin wrong.
location: hollow_keep
variants:
- id: 82339c14-2c3a-5019-8916-518ab79c39d3
  label: Default
choices:
- id: 333ba04d-bc4b-5dae-b499-770627e891bb
  label: Stagger through the open door
  effects:
  - op: modify
    stat: STAMINA
    amount: '-3'
  outcomes:
  - key: default
    target: a3_vault
layout:
  x: 8320.0
  y: 0.0
prose:
- variant: 82339c14-2c3a-5019-8916-518ab79c39d3
  text: |-
    The rings spin wrong. Something clicks in the door, and a dozen needles slide out of the wood, quick as snake-tongues, tipped with a grey paste that smells of almonds.

    You throw yourself sideways, but not far enough. One finds your arm. The wound burns, then numbs, and the door, as if satisfied, swings open anyway.
  summary: The rings spin wrong.
  inputs_hash: aacebae5a54813993570fa621c3e8f13152ef2a0ea7df0992e96ae6c788da62c
---
A wrong guess costs 3 STAMINA, but the door opens anyway.
