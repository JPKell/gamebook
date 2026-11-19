---
id: 5b7276d9-3e86-5f59-bb43-66615a54ac1f
key: a1_beggar_gift
title: A Gift Repaid
summary: She weighs the coin in her palm, bites it, and laughs, a dry sound like a door on a bad hinge.
location: marrowmere
on_enter:
- op: give
  item: marsh_map
  qty: 1
variants:
- id: fe4188a6-70e9-577b-919f-bfd1f87dcd9c
  label: Default
choices:
- id: c950f344-1bc0-5ab2-80c1-06cf94be34b2
  label: Return to the square
  outcomes:
  - key: default
    target: a1_square
layout:
  x: 1280.0
  y: 170.0
prose:
- variant: fe4188a6-70e9-577b-919f-bfd1f87dcd9c
  text: |-
    She weighs the coin in her palm, bites it, and laughs, a dry sound like a door on a bad hinge. Then, from inside the sacks, she draws a square of oilcloth and presses it into your hand.

    "The safe islands," she says. "Where the water's still honest. I drew it when I was young and could still walk it. You'll want to keep to the left of the tall reeds."

    You open your mouth to ask her name. When you look up, the well is only a well and the sacks are only sacks, and a small grey cat is washing itself on the rim.
  summary: She weighs the coin in her palm, bites it, and laughs, a dry sound like a door on a bad hinge.
  inputs_hash: ec3cc311446c893d2e7fc56ebe5c2b8eb13ffb252f60f69995f3453d86983c6a
---
The beggar's map of the fen's safe islands.
