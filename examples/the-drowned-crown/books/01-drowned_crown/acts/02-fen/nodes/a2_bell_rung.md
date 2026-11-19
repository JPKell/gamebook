---
id: 3cc7db47-fdfb-5c4d-9977-42400d8b0124
key: a2_bell_rung
title: The Bell Tolls
summary: You pull the rope, and the bell speaks.
location: sunken_abbey
variants:
- id: 77ba53e9-e098-5619-bda1-797673da2326
  label: Default
choices:
- id: 86c20eb1-6281-5b85-bf39-db56769c42e8
  label: Wait at the top of the stair
  kind: roll
  dice: 1d6
  outcomes:
  - key: cultists
    target: a2_ambush
    range:
    - 1
    - 2
  - key: queen
    target: a2_ghost
    range:
    - 3
    - 6
layout:
  x: 5120.0
  y: 340.0
prose:
- variant: 77ba53e9-e098-5619-bda1-797673da2326
  text: |-
    You pull the rope, and the bell speaks. The sound is enormous: a great cracked bass note that shakes the pigeons off the beams and rolls out across the fen like a wave. You feel it in your chest, in your teeth, in the water far below.

    Then, slowly, the sound dies, and in the silence you hear the answer. Footsteps, down in the cloister. Many of them, wet and unhurried. And a soft, pure voice, singing a few notes of a lullaby.

    Someone is coming up the stair.
  summary: You pull the rope, and the bell speaks.
  inputs_hash: 07e3241cdb3e261d05174299af59e8f360e03d6a8f3155523b8e0a1179f3cd83
---
The bell calls whoever is near: a two-in-six chance of the cult. Otherwise the queen's ghost answers.
