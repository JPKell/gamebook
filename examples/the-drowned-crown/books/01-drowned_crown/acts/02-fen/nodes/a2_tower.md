---
id: b205bff9-41c2-5ef4-baaa-ce3b3ab430c5
key: a2_tower
title: The Signal Tower
summary: The tower leans at an angle that should have brought it down a century ago.
location: the_fen
variants:
- id: 464346cf-c91a-5070-b162-00b86df5c656
  label: Default
choices:
- id: c0684a24-ee10-5091-8261-0bef2cee066e
  label: Search the satchel
  condition: not has(luck_charm)
  print_text: Search the satchel. Inside is a Fisherman's Charm. Take it, then return here.
  effects:
  - op: give
    item: luck_charm
    qty: 1
  outcomes:
  - key: default
    target: a2_tower
- id: be14a41e-1cb3-59a8-9010-d9578363b5f2
  label: Climb back down to the island
  outcomes:
  - key: default
    target: a2_island
layout:
  x: 3840.0
  y: 340.0
prose:
- variant: 464346cf-c91a-5070-b162-00b86df5c656
  text: |-
    The tower leans at an angle that should have brought it down a century ago. Inside, a spiral stair has been half eaten by damp and half propped up with hope. You climb carefully, counting steps, and at the top you find a brazier cold as a grave and a view that makes you forget to breathe.

    The whole fen lies spread below. To the north, on a cliff of black rock, rises a castle: dry, whole, lit. Its windows glow like a dozen yellow eyes. Between you and it lie the Sunken Abbey and a long flooded road.

    On the parapet someone has left a leather satchel. A dead signalman's, still strapped to the stonework by his own cold fingers.
  summary: The tower leans at an angle that should have brought it down a century ago.
  inputs_hash: 7fcae5ae7cbda6e96b25d9ec643f484a552d9e06695fa3aeb8d753909e4872ce
---
A view of the Hollow Keep, foreshadowing act 3. The satchel hides a luck charm.
