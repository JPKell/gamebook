---
id: 720b009a-4776-5431-b89d-01db0ff041b8
key: a2_seal
title: The Seal of the Order
summary: Alder lifts the seal and lays it in your hand, closing your fingers around it.
location: sunken_abbey
characters:
- brother_alder
on_enter:
- op: give
  item: abbey_seal
  qty: 1
variants:
- id: 9da37fec-c827-5191-b75d-7f5a989fe471
  label: Default
choices:
- id: 92fca465-b59b-5c5d-bd54-84e3ae97f7d4
  label: Return to the cloister
  outcomes:
  - key: default
    target: a2_cloister
layout:
  x: 5120.0
  y: 0.0
prose:
- variant: 9da37fec-c827-5191-b75d-7f5a989fe471
  text: |-
    Alder lifts the seal and lays it in your hand, closing your fingers around it. "The guardians of this place obey it," he says. "So, I am told, do the guardians of the keep. They were made by the same hands."

    He looks very tired. "I crowned him, you know. Oswin. I put it on his head myself. I told him it would protect his people."

    He takes your hand in both of his. "Don't let him keep it."
  summary: Alder lifts the seal and lays it in your hand, closing your fingers around it.
  inputs_hash: 34108cedee881ed728d600adf5915857952934eb9c87e7a9ffe70fe5254f436c
---
The abbey seal. Opens doors in both the abbey and the keep.
