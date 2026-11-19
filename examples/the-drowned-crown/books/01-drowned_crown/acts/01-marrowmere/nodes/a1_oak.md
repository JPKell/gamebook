---
id: 708d5900-7f79-5ce8-ade0-a91729559614
key: a1_oak
title: The Hanged Oak
summary: An oak stands alone in a clearing, and from its biggest branch a rope still hangs, long past
  rotting.
location: greywood
variants:
- id: 5efd1938-1594-53b1-888e-32436cbf414e
  label: Default
choices:
- id: 12ff9f47-3073-5f8a-8322-4a2a501b49be
  label: Walk into the camp
  outcomes:
  - key: default
    target: a1_bandit_camp
- id: df54846d-195e-5063-90e7-587148b28144
  label: Follow the game trail to avoid the camp
  condition: has(marsh_map)
  print_text: If you have the Marsh Map, you can follow the game trail around the camp.
  outcomes:
  - key: default
    target: a1_woods_exit
layout:
  x: 1280.0
  y: 1360.0
prose:
- variant: 5efd1938-1594-53b1-888e-32436cbf414e
  text: |-
    An oak stands alone in a clearing, and from its biggest branch a rope still hangs, long past rotting. Beneath it the ground is bare. Nothing grows in a circle ten paces wide.

    Smoke rises from beyond the oak, thin and untroubled. Someone has made a camp there, and they are not hiding. A hand-painted sign nailed to the trunk says, politely, TOLL: 10 GOLD.

    A game trail leads away to the right, around the camp, toward the fen.
  summary: An oak stands alone in a clearing, and from its biggest branch a rope still hangs, long past
    rotting.
  inputs_hash: f5c6ab80da485849d36b5cbd444f4c7cc3312c37e19599d584593ff931a650d8
---
Bandit toll. The marsh map lets careful readers skip the camp.
