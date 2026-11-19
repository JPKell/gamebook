---
id: 3f97680c-1b7e-508d-a1cf-39c2f876ee21
key: a1_reeve_rich
title: Hard Bargain
summary: You lean on the table and name your price, and then a second, higher price, and you do not blink.
location: marrowmere
characters:
- reeve_hale
on_enter:
- op: modify
  stat: GOLD
  amount: '25'
  once: true
variants:
- id: 921ff62a-955a-50ec-a7d4-55f6837077ea
  label: Default
choices:
- id: 149abf03-e4c0-5c0a-bebe-92fd6afb1418
  label: Go back out to the square
  outcomes:
  - key: default
    target: a1_square
layout:
  x: 1280.0
  y: 850.0
prose:
- variant: 921ff62a-955a-50ec-a7d4-55f6837077ea
  text: |-
    You lean on the table and name your price, and then a second, higher price, and you do not blink. Hale looks at you for a long moment. Then something in his face cracks, just slightly, with relief.

    "Twenty-five," he says. "And if you tell anyone I paid that much, I'll deny it."

    He signs a chit and slides a heavy purse across the ledger. You have a feeling you were not the first to ask, and you are the first he has been glad to pay.
  summary: You lean on the table and name your price, and then a second, higher price, and you do not
    blink.
  inputs_hash: 5dd63b76b00034ccb1931e2821dddfcb90249b4d22a74893070f81fc7e2c8925
---
Bonus: 25 Gold on a successful haggle. HIRED is set by the choice that leads here.
