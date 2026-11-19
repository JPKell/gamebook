---
id: 5608733e-d928-5277-b0fe-a28a965b9050
key: a3_chapel_keep
title: The Royal Chapel
summary: The chapel is small, bright and silent, with a painted ceiling of gold stars on blue.
location: hollow_keep
variants:
- id: 2a016c95-9a50-550a-8513-7f9a0d312c18
  label: Default
choices:
- id: 72a592b6-144f-5553-975e-6856c4d58b74
  label: Pour the holy water over the Marking
  condition: has(holy_water) and flag(MARKED)
  print_text: Pour a vial of holy water over your wrist. Cross out the codeword MARKED. Then return here.
  effects:
  - op: take
    item: holy_water
    qty: 1
  - op: clear_flag
    flag: MARKED
  outcomes:
  - key: default
    target: a3_chapel_keep
- id: b9c36b07-a181-57d2-b00c-103dd67c4ef3
  label: Rest and pray a while
  effects:
  - op: modify
    stat: STAMINA
    amount: '2'
  outcomes:
  - key: default
    target: a3_courtyard
- id: 8e5c8031-ab87-56c5-a724-74126276129c
  label: Leave the chapel
  outcomes:
  - key: default
    target: a3_courtyard
layout:
  x: 7040.0
  y: 170.0
prose:
- variant: 2a016c95-9a50-550a-8513-7f9a0d312c18
  text: |-
    The chapel is small, bright and silent, with a painted ceiling of gold stars on blue. A carved bell stands in an alcove, its tongue wrapped in cloth, and beneath it a basin of water that has gone stagnant. The candles burn, and the shadows do not move.

    You kneel, as one does. The mark on your wrist, if you bear one, gives a small cold pulse. If you have holy water, it begins very faintly to glow.
  summary: The chapel is small, bright and silent, with a painted ceiling of gold stars on blue.
  inputs_hash: 33d4eab3b6e5c418797774934c284ac83ce2ddf3f283351d6d2b06dbca98f44e
---
The chapel can lift the hag's Marking, closing the hollow ending for good.
