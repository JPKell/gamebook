---
id: a416481d-4980-514b-a7d2-5b0757d59acd
key: a1_shrine_blessed
title: A Warmth in the Stone
summary: The coin does not clink.
location: marrowmere
on_enter:
- op: modify
  stat: LUCK
  amount: '1'
  once: true
variants:
- id: cbd97b73-038f-5c9d-a629-f180672abe1f
  label: Default
choices:
- id: 18143235-1def-58f1-8997-d4df7d657808
  label: Walk on to the gate
  outcomes:
  - key: default
    target: a1_gate
layout:
  x: 640.0
  y: 0.0
prose:
- variant: cbd97b73-038f-5c9d-a629-f180672abe1f
  text: |-
    The coin does not clink. It slides into the hollow and is gone, as if the stone had swallowed it. A warmth runs up your arm, faint and brief, like a hand briefly resting on yours.

    You will tell yourself it was the cold playing tricks. But you walk toward the town with your shoulders a little lighter, and the rain seems to ease around you.
  summary: The coin does not clink.
  inputs_hash: 967e39887d90582b292e97e9b6167b3e5a689aa66a9d74f5581949000c32ecfc
---
Reward for a lucky offering: +1 LUCK.
