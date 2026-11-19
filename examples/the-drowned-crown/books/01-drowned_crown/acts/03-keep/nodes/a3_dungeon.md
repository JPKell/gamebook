---
id: 1547c82f-b3a7-5056-9532-56e708ec2162
key: a3_dungeon
title: The Gaol
summary: The gaol is the only part of the keep that is old, and cold, and real.
location: hollow_keep
variants:
- id: 7bd24ba3-39fd-5ab7-af0d-76642fe76445
  label: Default
encounters:
- id: e9944303-79cc-52b2-a4ab-0702140632d8
  label: The cultist gaoler
  enemies:
  - enemy: cultist
    level: 2
    count: 1
choices:
- id: 8da70486-6967-5af7-ab14-d5199162623e
  label: Fight the cultist gaoler
  kind: combat
  encounter: e9944303-79cc-52b2-a4ab-0702140632d8
  outcomes:
  - key: win
    target: a3_prisoner
  - key: lose
    target: a3_death_dungeon
- id: 34de2241-778f-54d2-a066-6a73e648527d
  label: Slip past while he shuffles
  condition: skill(STEALTH)
  min_tier: advanced
  outcomes:
  - key: default
    target: a3_prisoner
layout:
  x: 6720.0
  y: 340.0
prose:
- variant: 7bd24ba3-39fd-5ab7-af0d-76642fe76445
  text: |-
    The gaol is the only part of the keep that is old, and cold, and real. Iron-barred cells line a long vaulted corridor. At the far end a single lamp burns.

    A man in a robe sits at a table beneath the lamp, playing patience with a deck of black cards. He rises as you approach and shakes out his sleeves, and they are the sleeves of a Bell cultist: hooked knife and all.

    "The gaoler," he says, quite cheerfully, "is dead. I'm his replacement. Do you mind awfully if I kill you?"
  summary: The gaol is the only part of the keep that is old, and cold, and real.
  inputs_hash: 0bcaa5162a7233f47649d2a5276542706d6460e8acc962c3a55e671c1e31112d
---
Sneaking works for Rogues. Everyone else has to fight.
