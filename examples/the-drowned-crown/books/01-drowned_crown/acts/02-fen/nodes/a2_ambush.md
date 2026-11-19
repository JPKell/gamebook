---
id: 594004da-ca66-5377-bd73-2fd0220e819e
key: a2_ambush
title: Cultists in the Cloister
summary: They come up the stair in single file, robed in sodden black, carrying hooked knives and chanting
  a litany you half recognise.
location: sunken_abbey
variants:
- id: 012b8edc-a112-58b9-9082-18d966a11bcc
  label: Default
encounters:
- id: affe85cc-e741-5c49-b7a6-761c54920b16
  label: The cultists
  enemies:
  - enemy: cultist
    level: 1
    count: 2
choices:
- id: d5872d71-a1af-510b-a3b0-312ce3f7a169
  label: Fight your way down
  kind: combat
  encounter: affe85cc-e741-5c49-b7a6-761c54920b16
  outcomes:
  - key: win
    target: a2_cloister
  - key: lose
    target: a2_death_crypts
layout:
  x: 5440.0
  y: 0.0
prose:
- variant: 012b8edc-a112-58b9-9082-18d966a11bcc
  text: |-
    They come up the stair in single file, robed in sodden black, carrying hooked knives and chanting a litany you half recognise. The Brotherhood of the Crown. They have waited a hundred years for someone to ring the bell and wake the king, and you, fool, have rung it.

    The first one smiles at you the way a priest smiles at a sacrifice.
  summary: They come up the stair in single file, robed in sodden black, carrying hooked knives and chanting
    a litany you half recognise.
  inputs_hash: 16b0b863234f9789a9e11780e22ff25944fb61a9f458b0d1e50af91c8b946f35
---
Fight on the stair. A sequential fight against two cultists.
