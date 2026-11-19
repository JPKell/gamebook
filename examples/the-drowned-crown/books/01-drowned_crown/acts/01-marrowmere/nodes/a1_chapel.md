---
id: 39f1e7cc-d242-583d-b88c-c17f6325bbb7
key: a1_chapel
title: The Chapel of the Bell
summary: The chapel is small, bare and cold.
location: marrowmere
characters:
- brother_alder
variants:
- id: 48af3b76-1ae6-5589-9f6d-a198809346ed
  label: Default
choices:
- id: fd6fddd7-594a-5cd3-b463-b6bc9b8261e2
  label: Ask about the crown
  condition: not flag(ALDER_TRUST)
  print_text: Ask about the crown. Brother Alder will tell you what he knows. Note the codeword ALDER_TRUST,
    then return here.
  effects:
  - op: set_flag
    flag: ALDER_TRUST
  outcomes:
  - key: default
    target: a1_chapel
- id: d5d05d5f-64ce-5608-8f52-d61597ad87ca
  label: Leave an offering (2 Gold)
  condition: GOLD >= 2 and not has(holy_water)
  print_text: Leave 2 Gold. Alder gives you a Vial of Holy Water. Then return here.
  effects:
  - op: modify
    stat: GOLD
    amount: '-2'
  - op: give
    item: holy_water
    qty: 1
  outcomes:
  - key: default
    target: a1_chapel
- id: e9cabf50-8670-5488-ab1c-7787037b56c1
  label: Back to the square
  outcomes:
  - key: default
    target: a1_square
layout:
  x: 960.0
  y: 850.0
prose:
- variant: 48af3b76-1ae6-5589-9f6d-a198809346ed
  text: |-
    The chapel is small, bare and cold. A great bronze bell hangs in a timber frame above the altar, its rope tied up out of reach. The bell is cracked from lip to shoulder.

    A barefoot man in a rolled-up monk's habit is mopping the flagstones. He straightens as you come in. He is thin as a rake, with pewter-coloured eyes.

    "Brother Alder," he says. "I was abbot of the Sunken Abbey once, before the water. I keep the bell now, though it does not ring. Have you come to pray, or to ask about the crown?"
  summary: The chapel is small, bare and cold.
  inputs_hash: d44a621bf586ce0d6c1e0303a527bf9eec9de7504932abadf9eda45fd33dbfe8
---
Alder explains the three shards of the crown. Talking to him earns ALDER_TRUST, which pays off at the abbey.
