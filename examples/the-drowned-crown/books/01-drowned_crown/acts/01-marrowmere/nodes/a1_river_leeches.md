---
id: bc8440ae-0e32-5390-8707-43ced9f5a120
key: a1_river_leeches
title: Leeches in the Hull
summary: The knocking becomes a splash.
location: the_fen
characters:
- old_wick
variants:
- id: a78949a7-1403-5441-bbf8-6f267542f844
  label: Default
encounters:
- id: f04233f9-ea24-5d8c-8f0b-d848d92db456
  label: The leeches
  fight: simultaneous
  enemies:
  - enemy: giant_leech
    level: 1
    count: 2
choices:
- id: 3afc878a-6f99-5b42-a4a1-c88a3e5a9d88
  label: Beat them back
  kind: combat
  encounter: f04233f9-ea24-5d8c-8f0b-d848d92db456
  outcomes:
  - key: win
    target: a1_river_end
  - key: lose
    target: a1_death_river
layout:
  x: 1600.0
  y: 510.0
prose:
- variant: a78949a7-1403-5441-bbf8-6f267542f844
  text: |-
    The knocking becomes a splash. A black rope as thick as your wrist whips up over the gunwale, then another. The water churns with long, glistening bodies that ripple like tongues.

    Wick does not stop poling. "They only want the warm," he says calmly. "Mind your ankles."

    One lashes round your boot.
  summary: The knocking becomes a splash.
  inputs_hash: abc36b24da0a03a01cf2883d9d49a17b2cb7fa7bf0ed82cc488e48cd730fe01b
---
Two leeches fight at once. A short, nasty fight in a boat.
