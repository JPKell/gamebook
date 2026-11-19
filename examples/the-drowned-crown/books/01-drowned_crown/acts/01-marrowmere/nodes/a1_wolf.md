---
id: 4e6215a4-1b21-5b10-b3bd-4cfb404725e6
key: a1_wolf
title: Wolf in the Bracken
summary: It comes out of the bracken low and silent, a rangy grey wolf with mud to the shoulder and ribs
  standing out like a barrel's hoops.
location: greywood
variants:
- id: 51c849c8-6110-5a73-b1b4-c84543a73c3f
  label: Default
encounters:
- id: a009f85e-82a2-5e47-9dbf-daeda72b70f7
  label: The bog wolf
  enemies:
  - enemy: bog_wolf
    level: 1
    count: 1
choices:
- id: 30ffa529-cde2-5387-bcfc-ff306c363db4
  label: Defend yourself
  kind: combat
  encounter: a009f85e-82a2-5e47-9dbf-daeda72b70f7
  flee_allowed: true
  outcomes:
  - key: win
    target: a1_oak
  - key: lose
    target: a1_death_wolf
  - key: flee
    target: a1_oak
layout:
  x: 1280.0
  y: 1190.0
prose:
- variant: 51c849c8-6110-5a73-b1b4-c84543a73c3f
  text: |-
    It comes out of the bracken low and silent, a rangy grey wolf with mud to the shoulder and ribs standing out like a barrel's hoops. It is starving, and the fen has made it strange. Its eyes are the green of marsh gas.

    It does not growl. It simply waits for you to look away.
  summary: It comes out of the bracken low and silent, a rangy grey wolf with mud to the shoulder and
    ribs standing out like a barrel's hoops.
  inputs_hash: 42c6a48b337cd55ecf177f8c36d2687b5419868c22b41a42296c89796973d085
---
Wolf fight. Winning or fleeing both lead on to the oak.
