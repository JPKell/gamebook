---
id: 7f23f7e2-b8f5-5c44-992c-77aeb14a43d5
key: a2_flooded_crypt
title: The Queen's Tomb
summary: The west passage ends in a vaulted chamber, flooded to the shoulder.
location: sunken_abbey
characters:
- lady_isolde
variants:
- id: b6177609-9a60-5647-a35b-c0797e6567f8
  label: Default
choices:
- id: 512f7e78-9d96-50b9-8f1d-047e57f3ba2d
  label: Wade out with a rope tied to the doorframe
  condition: has(rope)
  outcomes:
  - key: default
    target: a2_shard_one
- id: fe1bb7d3-2598-5fb0-a4cc-6eccca20b705
  label: Wade out and trust your footing
  kind: test
  effects:
  - op: modify
    stat: STAMINA
    amount: '-1'
  test: luck
  outcomes:
  - key: success
    target: a2_shard_one
  - key: failure
    target: a2_catacombs
- id: 30ee3256-322c-5806-ad18-e14c9a90c5f8
  label: Go back
  outcomes:
  - key: default
    target: a2_catacombs
layout:
  x: 5440.0
  y: 510.0
prose:
- variant: b6177609-9a60-5647-a35b-c0797e6567f8
  text: |-
    The west passage ends in a vaulted chamber, flooded to the shoulder. In the middle, on a stone bier, lies a woman in a wedding dress: serene, dry, perfectly preserved. Her hands are crossed on her breast and between them is a shard of black iron.

    The water between you and the bier is cold and black. The bottom is slick. If you slip, you will not climb out easily.
  summary: The west passage ends in a vaulted chamber, flooded to the shoulder.
  inputs_hash: f87222e79ece14bef3463e27ef1c56a021bf9cb3e9c1ce5171b48b9beb5890c5
---
The first shard. A rope makes it safe, otherwise a Luck test, with a cold ducking as the price of failure.
