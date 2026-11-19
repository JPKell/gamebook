---
id: 09b0f2e5-d6b5-59ab-a622-beecb8f9e092
key: a3_final
title: What Becomes of the Crown
summary: The crown lies in your hands, cold and heavy and humming faintly.
location: hollow_keep
variants:
- id: 53e529df-8d5c-5e45-87ed-2910237ff481
  label: Default
choices:
- id: 627e7299-18ff-5f53-ba60-8a08c39442d7
  label: Reforge the crown with all three shards and let it protect, not trap
  condition: count(crown_shard) >= 3
  outcomes:
  - key: default
    target: a3_end_restore
- id: 06785bb1-e421-53ec-95d5-5adae2d7c513
  label: Free Isolde and Oswin, and unmake the crown together
  condition: count(crown_shard) >= 3 and flag(GHOST_FRIEND) and flag(LORE_KNOWN)
  outcomes:
  - key: default
    target: a3_end_secret
- id: 11f637da-44f1-57d5-9c16-6b38cb930190
  label: Smash the crown and scatter the shards
  outcomes:
  - key: default
    target: a3_end_destroy
- id: f5cd5432-24ca-5a71-9565-72273958451f
  label: Put the crown on
  outcomes:
  - key: default
    target: a3_end_crowned
layout:
  x: 8960.0
  y: 0.0
prose:
- variant: 53e529df-8d5c-5e45-87ed-2910237ff481
  text: |-
    The crown lies in your hands, cold and heavy and humming faintly. If you carry the shards you have gathered, they hum louder, straining toward its gaps like iron to a lodestone.

    Everything the crown has done, it did because someone wished it. It will do whatever it is asked, now, by whoever holds it.

    You could make it whole, and make it kind. You could break it for good. You could put it on. And if you know what the queen knew, you could set it free.
  summary: The crown lies in your hands, cold and heavy and humming faintly.
  inputs_hash: c7f90c1a93befb5a6000ea7d49e0b4e3e54e801dd4618acb2a8f87d8bdaef6e0
---
The final choice. The secret ending needs three shards, the ghost's friendship and the lore.
