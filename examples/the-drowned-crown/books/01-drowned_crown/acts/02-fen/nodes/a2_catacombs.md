---
id: ce2bde94-7af8-5b70-95fb-6546cf3b1087
key: a2_catacombs
title: The Catacombs
summary: The catacombs are a maze of low vaults, cold and dry.
location: sunken_abbey
variants:
- id: 4e3fe4a6-51c1-5d6e-ba81-15beaf05b99e
  label: Default
choices:
- id: c729393a-7ad4-5f59-92b9-df98f23300cf
  label: Take the east passage to the ossuary
  outcomes:
  - key: default
    target: a2_ossuary
- id: 3922fc60-5677-5cb9-a952-f7b6b39bc45e
  label: Wade the west passage to the flooded crypt
  outcomes:
  - key: default
    target: a2_flooded_crypt
- id: 8a4eb344-db59-5ddf-a387-d6604d5e2570
  label: Follow the grinding sound down
  outcomes:
  - key: default
    target: a2_guardian
layout:
  x: 5120.0
  y: 510.0
prose:
- variant: 4e3fe4a6-51c1-5d6e-ba81-15beaf05b99e
  text: |-
    The catacombs are a maze of low vaults, cold and dry. Niches line the walls, each holding a shrouded body or the dust of one. Your light reaches ten feet in any direction and no further.

    You find three passages. One leads east toward a gaping ossuary, the air heavy with the smell of old bone. One leads west to a drowned vault where water gleams. One leads steadily down, and from it comes a faint, repetitive grinding, like a great stone door being slowly opened.
  summary: The catacombs are a maze of low vaults, cold and dry.
  inputs_hash: 6cb972af24c1ba5dc97dce9647802c58440feeff9c5470ae4d698a73dd5a25cc
---
Hub of the catacombs. Ossuary (fight), crypt (the queen's shard), guardian (the way on).
