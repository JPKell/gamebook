---
id: a29fc891-48c5-58d0-ba2f-7dbf5221e121
key: a3_riddle_door
title: The Door of Three Rings
summary: The three rings are bronze, and they turn.
location: hollow_keep
variants:
- id: 6766cd1c-da82-5f9d-b2b5-dda7c75956a7
  label: Default
choices:
- id: 8d7ef898-31d9-59e4-b83a-18d2c518a242
  label: Spell out PROMISE
  condition: flag(LORE_KNOWN)
  outcomes:
  - key: default
    target: a3_vault
- id: 344752f3-30f6-5e4f-9dec-e2d204840246
  label: Guess at the answer
  kind: test
  test: skill
  outcomes:
  - key: success
    target: a3_vault
  - key: failure
    target: a3_trap
- id: 1cb4defb-4baf-5498-bb6b-c803a7bd8be3
  label: Step back
  outcomes:
  - key: default
    target: a3_gallery
layout:
  x: 8000.0
  y: 170.0
prose:
- variant: 6766cd1c-da82-5f9d-b2b5-dda7c75956a7
  text: |-
    The three rings are bronze, and they turn. Each is carved with a ring of letters, and by turning them you may spell out an answer.

    *What is the crown's true name?* The door is old. The riddle is older.

    Somewhere inside you, if you have read the abbey's book or listened to the dead, you know it: the crown was never a crown. It was a *promise.*
  summary: The three rings are bronze, and they turn.
  inputs_hash: 16cb0d74ded9ae1ee7749d199d07a447c3b7f2edb97a27f2b7241a638bf5c30e
---
Readers who learned the crown's history in the library know the answer. Others guess, and risk a trap.
