---
id: 04dea125-676a-5591-b72e-aabb9b8d696a
key: a2_library
title: The Library of Drowned Books
summary: The library is the only dry room in the abbey.
location: sunken_abbey
on_enter:
- op: set_flag
  flag: LORE_KNOWN
variants:
- id: 1e04cabc-4046-5b8b-9679-449b6edfac2b
  label: Default
choices:
- id: bd52c872-4685-5134-832c-f5584e8779f9
  label: Return to the cloister
  outcomes:
  - key: default
    target: a2_cloister
layout:
  x: 4800.0
  y: 0.0
prose:
- variant: 1e04cabc-4046-5b8b-9679-449b6edfac2b
  text: |-
    The library is the only dry room in the abbey. The shelves have been raised on stilts, and the books are all swollen with damp and gone soft as bread. You can read very few of them. You need a light to read any.

    In the lantern's glow, one book lies open on a lectern, its pages somehow whole. The hand is a monk's and the ink is fresh. It tells how three shards of the Hollow Crown were scattered when the bell cracked: one in the queen's tomb, one in the hands of a ghost, and one in the king's own vault.

    *Whoever holds all three decides what the crown becomes,* it says. *The wise will not wear it.*
  summary: The library is the only dry room in the abbey.
  inputs_hash: a2ddfa308c4eaa2ceee1cd54ca829879caf849dbbb4d8bc3a4cadf5c29370a09
---
Needs a lantern to learn what the crown is. Sets LORE_KNOWN.
