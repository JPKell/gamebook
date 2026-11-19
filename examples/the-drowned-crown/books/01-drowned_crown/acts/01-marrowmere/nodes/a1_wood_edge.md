---
id: 61d3fdde-f7f2-5dd0-9030-4605fd473f2c
key: a1_wood_edge
title: The Edge of the Greywood
summary: North of Marrowmere the road gives up and becomes a track, and the track becomes a gap between
  trees.
location: greywood
variants:
- id: fe14c43b-b9e0-5b17-93d3-9af77bcaa66c
  label: Default
choices:
- id: cf5e1c79-8b3e-5013-9591-2d11a42b9cfd
  label: Walk on and see what the wood sends
  kind: roll
  dice: 1d6
  outcomes:
  - key: wolf
    target: a1_wolf
    range:
    - 1
    - 2
  - key: quiet
    target: a1_oak
    range:
    - 3
    - 6
layout:
  x: 960.0
  y: 1190.0
prose:
- variant: fe14c43b-b9e0-5b17-93d3-9af77bcaa66c
  text: |-
    North of Marrowmere the road gives up and becomes a track, and the track becomes a gap between trees. The Greywood does not start so much as slowly close over your head. The light turns green, then grey.

    There is no birdsong. Somewhere ahead, off the path, something moves in the undergrowth, and stops when you stop.

    You touch your weapon. The track goes on, straight and wet and patient.
  summary: North of Marrowmere the road gives up and becomes a track, and the track becomes a gap between
    trees.
  inputs_hash: c1a68b3ce3426856a12fb905fe9e28cb16ed24d6b6d3b61ff4693b2812f5a02f
---
A 1d6 roll: a one-in-three chance of a wolf, otherwise a quiet walk to the hanged oak.
