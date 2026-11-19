---
id: fed0aadf-3097-5af1-bb2b-9d69958e12e6
key: a3_watergate
title: The Water Gate
summary: 'The water gate is a drain: a low brick tunnel, ankle-deep and stinking, that runs under the
  keep''s foundations.'
act_entry: true
location: hollow_keep
variants:
- id: 71a37be9-d4ea-5e96-a8b3-d1a7a19964d2
  label: Default
choices:
- id: f5b50e30-2fd8-5be6-b2d3-2108ce7f71b9
  label: Climb up to the kitchens
  outcomes:
  - key: default
    target: a3_kitchens
- id: 43dcd022-3bb4-562d-a5cc-36ec912e80af
  label: Take the stair down to the dungeons
  outcomes:
  - key: default
    target: a3_dungeon
layout:
  x: 6400.0
  y: 170.0
prose:
- variant: 71a37be9-d4ea-5e96-a8b3-d1a7a19964d2
  text: |-
    The water gate is a drain: a low brick tunnel, ankle-deep and stinking, that runs under the keep's foundations. You crawl on elbows and knees for what feels like a mile, and the dark is complete save for your light, if you have one, and the faint trickle of water.

    At last the tunnel narrows to a slot. You wriggle through, and find yourself in a cellar that smells of ancient wine. A stair leads up to a kitchen. A heavy grated door leads down to the dungeons.
  summary: 'The water gate is a drain: a low brick tunnel, ankle-deep and stinking, that runs under the
    keep''s foundations.'
  inputs_hash: a1ea961bdd46b5b7564d62b394a8cf729092a41369d83def04736a4d5e60c93b
---
Act 3 entry via the water gate: a back way in, past the guards.
