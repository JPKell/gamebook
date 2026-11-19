---
id: 8df1db06-29b4-50b8-b4b5-2f5011e45c22
key: a2_ossuary
title: The Ossuary
summary: The walls here are built of bones.
location: sunken_abbey
items:
- item: old_coin
  qty: 3
variants:
- id: 20b434dc-e159-573c-98e4-7dff5d1050b6
  label: Default
encounters:
- id: bc44e194-c108-52e6-b406-475ba485bc03
  label: The ghoul
  enemies:
  - enemy: crypt_ghoul
    level: 1
    count: 1
choices:
- id: f7b4212c-2b93-51bf-b853-aff74f2212a9
  label: Fight the ghoul
  kind: combat
  encounter: bc44e194-c108-52e6-b406-475ba485bc03
  outcomes:
  - key: win
    target: a2_catacombs
  - key: lose
    target: a2_death_crypts
- id: fac26b61-a321-51c5-bc93-85961918eb57
  label: Throw holy water and drive it off
  condition: has(holy_water)
  effects:
  - op: take
    item: holy_water
    qty: 1
  outcomes:
  - key: default
    target: a2_catacombs
layout:
  x: 5440.0
  y: 340.0
prose:
- variant: 20b434dc-e159-573c-98e4-7dff5d1050b6
  text: |-
    The walls here are built of bones. Skulls and thighbones in patterns that were once beautiful, mortared with grey clay. In the middle of the floor lies a heap of the older, uglier sort of bones, as though something had been using them for a bed.

    Something rises from the heap. It is long-armed and hairless, with a jaw too wide for its face and the grey patient eyes of a creature that has been very hungry for a very long time.
  summary: The walls here are built of bones.
  inputs_hash: eb8b33260102b0d14f8871246656395df3bb5cbd56abcfdd598dfbfc53a50a84
---
Holy water drives it off, if the reader thought to buy or be given some.
