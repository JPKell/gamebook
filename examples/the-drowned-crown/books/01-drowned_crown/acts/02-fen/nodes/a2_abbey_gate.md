---
id: dbddd5a8-b379-58de-844e-ebc490425e5b
key: a2_abbey_gate
title: The Sunken Abbey
summary: The road runs under the water for the last hundred yards, and you wade it knee-deep, feeling
  for the old paving with your boots.
location: sunken_abbey
variants:
- id: 9f2816c9-ac23-563b-a09c-0999b8e0732d
  label: Default
- id: 2c7781e6-f47b-5de3-90aa-556664fb6060
  label: Seal of the Order
  condition: has(abbey_seal)
  priority: 5
choices:
- id: 4bec65d6-24c2-58b0-a4dd-2d839895e4d4
  label: Go in through the nave
  outcomes:
  - key: default
    target: a2_nave
layout:
  x: 3840.0
  y: 510.0
prose:
- variant: 9f2816c9-ac23-563b-a09c-0999b8e0732d
  text: |-
    The road runs under the water for the last hundred yards, and you wade it knee-deep, feeling for the old paving with your boots. The abbey rises from the fen like an enormous grey ship run aground: a long nave, a stub of tower, a cloister of roofless arches.

    Moss grows on the stones like green fur. Over the porch hangs a bell-shaped carving, broken. The great door is open a hand's breadth, and water slides in and out of it with a soft, regular sound, like breathing.

    Inside, something is humming. It is not a monk. It is not a voice. It is the tone of a large bronze bell, cracked, which no one is touching.
  summary: The road runs under the water for the last hundred yards, and you wade it knee-deep, feeling
    for the old paving with your boots.
  inputs_hash: 76748708e81b68a58b61b46bef3d5fbcccde50bb0c99d7e9c9083b7d9a3ed941
- variant: 2c7781e6-f47b-5de3-90aa-556664fb6060
  text: |-
    You hold up the bronze seal as you wade the last hundred yards. For the first time the water seems to part a little, the way a crowd makes room for a bishop.

    The great door swings open of its own accord. A low hum of welcome rises from within, a cracked bronze note that is almost a greeting.
  summary: You hold up the bronze seal as you wade the last hundred yards.
  inputs_hash: 6d9ad2ae23c4513ed6d38ee21db99e845a7dfd945f330b3a4b91f5d550b5b3cc
---
Entrance to the abbey. The hub is the cloister beyond.
