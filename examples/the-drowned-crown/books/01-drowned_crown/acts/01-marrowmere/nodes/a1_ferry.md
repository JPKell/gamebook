---
id: e507bf90-fc4d-5bb1-8bd8-254f75b9d47e
key: a1_ferry
title: Old Wick's Ferry
summary: The ferry landing is a rotted jetty with a flat boat tied to it.
location: marrowmere
characters:
- old_wick
variants:
- id: 334aaaae-1f54-5000-bac5-148647c5cca8
  label: Default
choices:
- id: 703e34f3-a934-5a60-9fa6-f175d9369e70
  label: Pay Wick 2 Gold and cross
  condition: GOLD >= 2
  effects:
  - op: modify
    stat: GOLD
    amount: '-2'
  outcomes:
  - key: default
    target: a1_river
- id: d311e14e-1961-54dc-b562-9702c4a7717a
  label: Show him the bone whistle
  condition: has(bone_whistle) and not flag(WICK_FRIEND)
  print_text: Show Old Wick the bone whistle. He crosses you free and fast. Note the codeword WICK_FRIEND.
  effects:
  - op: set_flag
    flag: WICK_FRIEND
  outcomes:
  - key: default
    target: a1_river_end
- id: 9b5ca768-abdf-5402-ba41-8cd3e0499e72
  label: Go back up to the square
  outcomes:
  - key: default
    target: a1_square
layout:
  x: 960.0
  y: 1360.0
prose:
- variant: 334aaaae-1f54-5000-bac5-148647c5cca8
  text: |-
    The ferry landing is a rotted jetty with a flat boat tied to it. A bald man sits in the stern, smoking a pipe that has no tobacco in it, talking quietly to the boat.

    "She doesn't like the dark," he says, nodding to you, then the boat. "Two gold across, and I don't ask what you're doing. It's a policy."

    His smile is friendly and his hands are very white. The water around the boat is perfectly still. It does not rock, though the wind blows.
  summary: The ferry landing is a rotted jetty with a flat boat tied to it.
  inputs_hash: 6684c20ae1068716d179c30d88093db5d64f04ee030c018ca59dc3ba1259e889
---
Wick is dead and doesn't know it. The whistle lets you skip the crossing as a friend.
