---
id: fc213143-27df-5949-adb1-06d4579457d5
key: a2_crypt_door
title: The Crypt Door
summary: The door is an iron hatch set in the cloister floor, its lock green with age.
location: sunken_abbey
variants:
- id: f1dabf9d-327a-5f44-b906-8ebd018c160f
  label: Default
choices:
- id: 6f9340f8-3651-56d0-9ed0-676b93ef4030
  label: Unlock it with the brass key
  condition: has(brass_key)
  outcomes:
  - key: default
    target: a2_catacombs
- id: 035dad12-c1bb-54b8-bff2-f5b153f57256
  label: Open it with the abbey seal
  condition: has(abbey_seal)
  outcomes:
  - key: default
    target: a2_catacombs
- id: 6d1df1e7-087b-523c-b04e-5e11a0681613
  label: Force the lock
  kind: test
  effects:
  - op: modify
    stat: STAMINA
    amount: '-1'
  test: skill
  outcomes:
  - key: success
    target: a2_catacombs
  - key: failure
    target: a2_cloister
- id: 21c32438-4d2e-580b-840a-7bf0b297e598
  label: Back to the cloister
  outcomes:
  - key: default
    target: a2_cloister
layout:
  x: 4800.0
  y: 680.0
prose:
- variant: f1dabf9d-327a-5f44-b906-8ebd018c160f
  text: |-
    The door is an iron hatch set in the cloister floor, its lock green with age. The stairs beneath it go down into a dark so complete the water seems to stop at its edge.

    The lock bears a small bell, stamped into the metal.
  summary: The door is an iron hatch set in the cloister floor, its lock green with age.
  inputs_hash: 14cb0d1960c0bc9385d13743ff7c68239e74f3c7cb1de2d4ff2875d982d88119
---
Three ways down: the key from Mara, the seal from Alder, or brute force.
