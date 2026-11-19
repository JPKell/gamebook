---
id: 4be6e2f5-6c7b-5bfc-8f84-d596d3172cf3
key: a2_guardian
title: The Stone Wardens
summary: 'The grinding is a pair of stone figures: tall, hooded, monk-shaped, standing at either side
  of a great stone door.'
location: sunken_abbey
variants:
- id: ee56b0da-c422-5431-940e-7758285d2d23
  label: Default
encounters:
- id: 03523197-651b-5451-8512-1f7925cce20c
  label: The wardens
  enemies:
  - enemy: stone_warden
    level: 1
    count: 1
choices:
- id: 72760952-f203-56e9-9dfe-2388c469218a
  label: Hold up the Seal of the Abbey
  condition: has(abbey_seal)
  outcomes:
  - key: default
    target: a2_stair
- id: caa0b12f-eec3-5f80-be92-430c0b04c110
  label: Fight the wardens
  kind: combat
  encounter: 03523197-651b-5451-8512-1f7925cce20c
  outcomes:
  - key: win
    target: a2_stair
  - key: lose
    target: a2_death_crypts
- id: 0b451b17-01f2-52c2-b6de-bef3c3de8a47
  label: Back to the catacombs
  outcomes:
  - key: default
    target: a2_catacombs
layout:
  x: 5440.0
  y: 680.0
prose:
- variant: ee56b0da-c422-5431-940e-7758285d2d23
  text: |-
    The grinding is a pair of stone figures: tall, hooded, monk-shaped, standing at either side of a great stone door. They were carved by hands that loved them. They rotate slowly toward you, with the sound of a millstone.

    "None may pass," says one, with a voice like a landslide. "None may go down who is not the Order's."

    Behind them, the door stands ajar, and beyond it lies a dry stair.
  summary: 'The grinding is a pair of stone figures: tall, hooded, monk-shaped, standing at either side
    of a great stone door.'
  inputs_hash: fc358b22d6cef1907fd4edda2ab7239283361a73e95702ff26b94d75acbb88ba
---
The seal makes the fight unnecessary. Otherwise it is the hardest fight of the act.
