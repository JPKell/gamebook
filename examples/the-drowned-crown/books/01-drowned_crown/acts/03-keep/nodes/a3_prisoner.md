---
id: d2f11c19-7488-5025-b667-7a4ec3def05c
key: a3_prisoner
title: The Prisoner
summary: In the last cell, curled in the corner, sits an old man in a soldier's coat, chained by the wrist
  to the wall.
location: hollow_keep
variants:
- id: 5f2fb626-f6ba-5a50-9eb4-8715ef282455
  label: Default
choices:
- id: ffab1928-41aa-5530-8eba-45297c134296
  label: Free him and give him a draught
  condition: has(healing_draught)
  effects:
  - op: take
    item: healing_draught
    qty: 1
  - op: set_flag
    flag: PRISONER_FREED
  - op: modify
    stat: LUCK
    amount: '1'
  outcomes:
  - key: default
    target: a3_courtyard
- id: 1bf8cfd8-4bf7-5fc2-b832-c93ae7849553
  label: Free him
  condition: not has(healing_draught)
  effects:
  - op: set_flag
    flag: PRISONER_FREED
  outcomes:
  - key: default
    target: a3_courtyard
- id: c1c9d6d0-f918-5b34-924d-3359d6ee6326
  label: Leave him
  outcomes:
  - key: default
    target: a3_courtyard
layout:
  x: 7040.0
  y: 510.0
prose:
- variant: 5f2fb626-f6ba-5a50-9eb4-8715ef282455
  text: |-
    In the last cell, curled in the corner, sits an old man in a soldier's coat, chained by the wrist to the wall. He is thin, grey-bearded, and quite sane. He has been here forty years.

    "Sergeant Pell," he says, in a cracked voice. "Of the king's guard. I refused to wear the crown's collar, when the king took the oath. They threw me down here and forgot me."

    He grips your arm. "Listen. The king is not cruel. He is *trapped*. If you can get all three pieces of the crown, you can free him. I... I don't know how. But I know the knight in the hall will let you pass if you wear the abbey seal."
  summary: In the last cell, curled in the corner, sits an old man in a soldier's coat, chained by the
    wrist to the wall.
  inputs_hash: 98bde26f663a0ee406f318fcf9b763d42cb7bb6fad2138e9572f1cc57c4711af
---
The prisoner tells the reader about the seal. Freeing him earns a Luck boost.
