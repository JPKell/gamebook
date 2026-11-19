---
id: 2a56c44d-4db0-56b1-9ae5-a96a2e3dc590
key: a2_mire
title: The Mire
summary: The lights lead you off the stones and into the reeds, and the reeds into the mud, and the mud
  into something thicker.
location: the_fen
variants:
- id: af4aa034-a210-5a12-b5b9-8dff91145d32
  label: Default
choices:
- id: 0a7e5abf-c8b0-5104-b62f-4a75fd718b74
  label: Throw the rope to a root and haul yourself out
  condition: has(rope)
  effects:
  - op: modify
    stat: STAMINA
    amount: '-1'
  outcomes:
  - key: default
    target: a2_island
- id: 3f2e6db6-6139-58bd-8049-d6594d512b87
  label: Thrash free and trust your luck
  kind: test
  test: luck
  outcomes:
  - key: success
    target: a2_island
  - key: failure
    target: a2_death_mire
layout:
  x: 3520.0
  y: 0.0
prose:
- variant: af4aa034-a210-5a12-b5b9-8dff91145d32
  text: |-
    The lights lead you off the stones and into the reeds, and the reeds into the mud, and the mud into something thicker. Your boots go in to the ankle, to the knee, to the thigh. The lights hover, delighted.

    You are sinking, steadily and silently. Reeds hang just out of reach. If you had something to throw, something strong, something to hold...
  summary: The lights lead you off the stones and into the reeds, and the reeds into the mud, and the
    mud into something thicker.
  inputs_hash: 7099e8b30238faba4a1b2a1897889d145b189f3740820d74a23a938d1977b8ac
---
A rope makes this safe. Otherwise it's a Luck test with death on the other side.
