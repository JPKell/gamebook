---
id: 64effd66-cdd1-5f1c-a32e-3fc6d893dead
key: a1_bandit_loot
title: The Captain's Cache
summary: Brandt goes down on one knee and drops his sabre.
location: greywood
characters:
- captain_brandt
on_enter:
- op: modify
  stat: GOLD
  amount: '18'
  once: true
items:
- item: silver_dagger
  qty: 1
- item: ration
  qty: 2
variants:
- id: 2d93ee65-be39-5ab3-8d0c-c2b5abd0cf68
  label: Default
choices:
- id: 92a04fbb-9b00-5a77-8ea4-a63104e67fe5
  label: Continue toward the fen
  outcomes:
  - key: default
    target: a1_woods_exit
layout:
  x: 1920.0
  y: 0.0
prose:
- variant: 2d93ee65-be39-5ab3-8d0c-c2b5abd0cf68
  text: |-
    Brandt goes down on one knee and drops his sabre. The rest of the gang take one look at you and scatter into the trees.

    Under the captain's bedroll is a tarred sack with a strongbox in it. It is full of other people's coin, and beneath that, wrapped in cloth, a dagger of dull silver. The hilt is stamped with a tiny bell.

    You take both, and a few strips of dried rabbit for the road.
  summary: Brandt goes down on one knee and drops his sabre.
  inputs_hash: c4f3e3f5145f4b4c7ef7c3b5d23285ae4a78c3fc1c1db0c62bfd2a1eb2d27ba4
---
Reward for beating Brandt: 18 gold, the silver dagger, rations.
