---
id: c49f5ad3-6e7e-5395-bc48-eb64e2181293
key: a1_inn
title: The Salted Eel
summary: The common room smells of woodsmoke, wet dog and frying eel.
location: marrowmere
characters:
- mara_venn
variants:
- id: ef5dce4d-ab27-556b-a04b-61087ad00ff8
  label: Default
choices:
- id: b6734cb9-0b2a-5412-9361-2f6704f92e01
  label: Rent a bed for the night (3 Gold)
  condition: GOLD >= 3
  outcomes:
  - key: default
    target: a1_inn_room
- id: 7e46ba16-d3d4-5275-a1c5-0ec6941ed36a
  label: Buy a drink and listen (1 Gold)
  condition: GOLD >= 1 and not flag(RUMOUR)
  print_text: Spend 1 Gold on a drink to hear the gossip. Then return here.
  effects:
  - op: modify
    stat: GOLD
    amount: '-1'
  - op: set_flag
    flag: RUMOUR
  outcomes:
  - key: default
    target: a1_inn
- id: 449d170d-8008-5229-9775-dff74939f3cf
  label: Back out into the square
  outcomes:
  - key: default
    target: a1_square
layout:
  x: 960.0
  y: 0.0
prose:
- variant: ef5dce4d-ab27-556b-a04b-61087ad00ff8
  text: |-
    The common room smells of woodsmoke, wet dog and frying eel. A dozen fishermen sit shoulder to shoulder, saying little. Behind the bar, a broad woman with scarred forearms is arguing with a barrel.

    "Mara Venn," she announces, without looking up. "I own it, I pour it, and I'll thank you not to drip on the floor. Beds are three gold. Gossip is free, if you buy something."

    A crooked stair leads up to the rooms. The fire is the first warm thing you have seen in days.
  summary: The common room smells of woodsmoke, wet dog and frying eel.
  inputs_hash: 716f17e1cfc9672ab281d43d33aac44a40eb3c4e9d35ebd36e9f0f375d5301a8
---
Inn. Rest costs 3 gold. Gossip sets RUMOUR. Mara's late husband was a lay-brother (brass key hint).
