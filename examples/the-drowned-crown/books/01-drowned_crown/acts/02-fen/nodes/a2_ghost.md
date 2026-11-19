---
id: 356eeb8d-35e2-58a0-9f9d-c19dd36d62f7
key: a2_ghost
title: Lady Isolde
summary: A woman in a drowned wedding dress stands at the top of the stair.
location: sunken_abbey
characters:
- lady_isolde
variants:
- id: 96a4e86f-5c63-5ea3-aff4-e0e20615ce7d
  label: Default
choices:
- id: f20881f5-3796-5fdc-8b8f-4fdc3fdf1107
  label: Take the shard and thank her
  effects:
  - op: set_flag
    flag: GHOST_FRIEND
  - op: give
    item: crown_shard
    qty: 1
  outcomes:
  - key: default
    target: a2_cloister
layout:
  x: 5440.0
  y: 170.0
prose:
- variant: 96a4e86f-5c63-5ea3-aff4-e0e20615ce7d
  text: |-
    A woman in a drowned wedding dress stands at the top of the stair. Water runs from her hair and from her sleeves, and where it falls it makes no sound. She is transparent at the edges, like breath on glass.

    "You rang the bell," she says. "Nobody has, for a hundred years. I thought I had forgotten the sound."

    She looks at the bronze seal, or the mark on your wrist, or your face, and her own face changes. "My husband will know you are here," she says. "But there is a thing I must give you before he does."

    In her cold hand lies a fragment of black iron.
  summary: A woman in a drowned wedding dress stands at the top of the stair.
  inputs_hash: 476cac750eb8867e3aa038594af957294ceb2de92e4c42c4a699e577679699b7
---
The second shard. Isolde gives it to anyone who rings the bell. GHOST_FRIEND unlocks the secret ending.
