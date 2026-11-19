---
id: 1bf4d10f-50c2-5b35-815a-19ab96e4566e
key: a1_guard
title: A Word with the Guard
summary: The guard's name is Tomas and he is happy to talk, since no one else will.
location: marrowmere
on_enter:
- op: set_flag
  flag: RUMOUR
variants:
- id: ca6594f6-d76f-5deb-ac38-f1e187f31226
  label: Default
choices:
- id: 689a5a9e-898e-5003-96b0-6797646017a0
  label: Thank him and enter the square
  outcomes:
  - key: default
    target: a1_square
layout:
  x: 640.0
  y: 340.0
prose:
- variant: ca6594f6-d76f-5deb-ac38-f1e187f31226
  text: |-
    The guard's name is Tomas and he is happy to talk, since no one else will. In the space of a few breaths you learn that the reeve is desperate, that the inn is the only warm place in town, that the smith overcharges and that old Wick the ferryman "isn't right in the head, but he's never lost a passenger."

    "And if you're going out to the fen," Tomas adds, lowering his voice, "see the brothers at the chapel first. The last two who went didn't."

    He will not say more. He is watching the water in the ditch, which has begun, very slightly, to rise.
  summary: The guard's name is Tomas and he is happy to talk, since no one else will.
  inputs_hash: 47125363141b84d026a0a87cdaa83295e18bd37895df0062ac4387e1724fb6bd
---
Rumour beat. Sets the RUMOUR codeword so the reeve can be haggled with more shrewdly.
