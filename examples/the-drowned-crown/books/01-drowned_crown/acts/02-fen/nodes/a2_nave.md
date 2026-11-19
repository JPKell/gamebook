---
id: 31cc9593-7741-58cf-bbf4-280314c50447
key: a2_nave
title: The Flooded Nave
summary: The nave is a long flooded hall lit through broken windows by ghostly green light.
location: sunken_abbey
variants:
- id: 52a92a3c-1359-524d-97f9-9c2f20c496ba
  label: Default
encounters:
- id: 056ddc13-6481-5eb1-bae0-ec6d77d22785
  label: The drowned monk
  enemies:
  - enemy: drowned_man
    level: 2
    count: 1
choices:
- id: a099f7b1-696f-52c9-8e55-5387b6140ba1
  label: Fight the drowned monk
  kind: combat
  encounter: 056ddc13-6481-5eb1-bae0-ec6d77d22785
  outcomes:
  - key: win
    target: a2_cloister
  - key: lose
    target: a2_death_crypts
- id: 2e5f0269-c5a6-57e7-a142-d2386f4c8d89
  label: Pass him quietly
  condition: skill(STEALTH)
  min_tier: advanced
  outcomes:
  - key: default
    target: a2_cloister
layout:
  x: 4160.0
  y: 680.0
prose:
- variant: 52a92a3c-1359-524d-97f9-9c2f20c496ba
  text: |-
    The nave is a long flooded hall lit through broken windows by ghostly green light. Pews stand in the water like the ribs of drowned animals. At the far end the altar is a dry island in the flood, and on the island stands a robed figure with its back to you, perfectly still.

    You wade up the centre aisle. The water laps at your knees. The robed figure turns, and its face is a swollen grey thing with slack fish-white eyes.

    A drowned monk, still keeping his watch.
  summary: The nave is a long flooded hall lit through broken windows by ghostly green light.
  inputs_hash: 23c9e67e653b77c7d21f58f1afff64897f151066b271cf2e0d5f5ab0f6305240
---
Guardian of the nave. Advanced-tier Rogues can slip past.
