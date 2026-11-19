---
id: 2abe9f0a-bc2c-5ea7-bf53-ab7473d633ea
key: a1_chandler
title: The Chandler's Shop
summary: 'Rope, lamp oil, candles, hooks, tallow, bandages: the shop sells everything a flooded town runs
  out of.'
location: marrowmere
shop:
  enabled: true
  sell_rate: 50
  items:
  - item: rope
    price: 3
  - item: lantern
    price: 5
  - item: healing_draught
    price: 6
    stock: 3
  - item: ration
    price: 1
    stock: 5
  - item: holy_water
    price: 4
    stock: 3
variants:
- id: e794c9d3-d28a-56fb-913a-7ec74b970749
  label: Default
choices:
- id: e13a7c04-d07d-546e-a9ca-04433e5d559d
  label: Back to the square
  outcomes:
  - key: default
    target: a1_square
layout:
  x: 960.0
  y: 340.0
prose:
- variant: e794c9d3-d28a-56fb-913a-7ec74b970749
  text: |-
    Rope, lamp oil, candles, hooks, tallow, bandages: the shop sells everything a flooded town runs out of. The chandler is a thin, stooped man who does not look up from his ledger.

    "Rope's three," he says. "Lantern's five. If you're going below ground, you'll want the lantern. And holy water, if you can stomach what the abbey did to it."

    The shelves are very full. Few people in Marrowmere are going anywhere.
  summary: 'Rope, lamp oil, candles, hooks, tallow, bandages: the shop sells everything a flooded town
    runs out of.'
  inputs_hash: b8d30a34ee6da3a1517dddf207b9fbe3df44bee31832ff48243232832aa80ff9
---
General store: rope, lantern, healing, rations, holy water. Hints at the abbey.
