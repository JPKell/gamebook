---
id: 67eebb5d-b6a6-52ba-9fe4-3854912e3928
key: a1_river
title: The Mist on the Water
summary: Wick poles the boat out of the shallows.
location: the_fen
characters:
- old_wick
variants:
- id: c2fc7fec-1941-5925-bb84-6a315393d60a
  label: Default
choices:
- id: 0e153b1e-9548-5864-b9be-d43be2a2257c
  label: Trust the ferryman and wait
  kind: roll
  dice: 1d6
  outcomes:
  - key: leeches
    target: a1_river_leeches
    range:
    - 1
    - 2
  - key: quiet
    target: a1_river_end
    range:
    - 3
    - 6
layout:
  x: 1280.0
  y: 1530.0
prose:
- variant: c2fc7fec-1941-5925-bb84-6a315393d60a
  text: |-
    Wick poles the boat out of the shallows. In moments the shore is gone, and the world is a bowl of white. He talks as he works, softly, about his wife and about a storm that came in when he was young. He has told this story many times. It ends differently each time, and he does not seem to know.

    Something knocks, once, on the hull beneath your feet.

    "Don't mind her," Wick says. "She's friendly."
  summary: Wick poles the boat out of the shallows.
  inputs_hash: 671aef6980c76c4cc4f87a4efcae02d0ea0c9622d6822960699ae17fdec317d2
---
A 1d6 roll: a one-in-three chance of leeches in the water.
