---
id: 4da7e8fc-6954-5cf4-af54-d248916c3fa4
key: a2_belltower
title: The Bell Tower
summary: The stair is a spiral of wet stone.
location: sunken_abbey
variants:
- id: 8a0986bd-6310-5e50-a866-3ec44f333aa8
  label: Default
choices:
- id: b782c28f-0826-5747-87aa-5f8ee4ae284c
  label: Ring the bell
  condition: not flag(BELL_RUNG)
  effects:
  - op: set_flag
    flag: BELL_RUNG
  outcomes:
  - key: default
    target: a2_bell_rung
- id: 50a623af-1c4c-5897-b8a3-3ee509b3aa36
  label: Climb back down
  outcomes:
  - key: default
    target: a2_cloister
layout:
  x: 4800.0
  y: 510.0
prose:
- variant: 8a0986bd-6310-5e50-a866-3ec44f333aa8
  text: |-
    The stair is a spiral of wet stone. At the top, in a high airy room full of pigeons' feathers, the great bell hangs from a beam as thick as a mast: a mass of green-black bronze taller than a man, with a crack down its side like a lightning scar.

    Its rope hangs in a loop beside you. The bell hums to itself, softly, constantly, a low note that runs through your teeth.

    The abbey, you realise, is waiting for someone to ring it.
  summary: The stair is a spiral of wet stone.
  inputs_hash: ce74c299564548f41fd667489ca4279c3b37cc9039de2f5d37475f59e193e482
---
Optional: ringing the bell brings the dead to the abbey. Both friends and enemies answer.
