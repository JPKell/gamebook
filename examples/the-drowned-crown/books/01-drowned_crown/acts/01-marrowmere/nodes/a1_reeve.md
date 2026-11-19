---
id: 0c28e592-f895-5042-9479-77cec5072b45
key: a1_reeve
title: The Reeve's Hall
summary: Reeve Hale receives you in a room that smells of damp paper.
location: marrowmere
characters:
- reeve_hale
variants:
- id: f050e005-f8da-528c-9e0c-c9157f426014
  label: Default
choices:
- id: d851bd62-6615-534c-8a26-18b9a02821a2
  label: Accept the 15 Gold
  effects:
  - op: modify
    stat: GOLD
    amount: '15'
  - op: set_flag
    flag: HIRED
  outcomes:
  - key: default
    target: a1_reeve_hired
- id: da53b908-8f49-5748-be26-d9bc60ecb1a3
  label: Haggle for more
  kind: test
  effects:
  - op: set_flag
    flag: HIRED
  test: skill
  outcomes:
  - key: success
    target: a1_reeve_rich
  - key: failure
    target: a1_reeve_hired
- id: 4a2a37c8-b7df-5da7-a725-23ca88b0cbd3
  label: Refuse the job
  outcomes:
  - key: default
    target: a1_reeve_refuse
layout:
  x: 960.0
  y: 1020.0
prose:
- variant: f050e005-f8da-528c-9e0c-c9157f426014
  text: |-
    Reeve Hale receives you in a room that smells of damp paper. Ledgers are stacked along the walls, each with a year inked on the spine, each with a column of lost property and a column of lost lives.

    "Here's the situation," he says, without greeting. "The fen rises faster every year. The old stories say there is a crown at the bottom of it, and the crown is the reason. Bring it back, break it, bury it, I don't care. Stop the water."

    He pushes a purse across the table. "Fifteen now. A great deal more if you come back."

    Behind him, in the ledger for last year, two names have been crossed out.
  summary: Reeve Hale receives you in a room that smells of damp paper.
  inputs_hash: 03c47be73bd8647854f8ef57ead3c3b306657cd78795a699f67d73289a97e2fe
---
The hiring scene. Haggling is a Skill test: a success earns 25 gold, a failure the standard 15.
