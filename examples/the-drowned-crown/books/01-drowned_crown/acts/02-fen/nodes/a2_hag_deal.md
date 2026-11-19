---
id: 9943ad35-3f74-5d8a-80c9-ca3cccac117c
key: a2_hag_deal
title: A Hag's Bargain
summary: '"One small thing," Mother Grey says, "and I''ll pay you handsomely.'
location: the_fen
characters:
- mother_grey
on_enter:
- op: set_flag
  flag: MARKED
- op: give
  item: healing_draught
  qty: 2
- op: modify
  stat: LUCK
  amount: '1'
  once: true
variants:
- id: 1a5ce877-ccb6-5433-8f77-725d165a7a28
  label: Default
choices:
- id: 90eb11fa-cfa5-5497-94e3-6772b98b6953
  label: Return to the island
  outcomes:
  - key: default
    target: a2_island
layout:
  x: 4160.0
  y: 0.0
prose:
- variant: 1a5ce877-ccb6-5433-8f77-725d165a7a28
  text: |-
    "One small thing," Mother Grey says, "and I'll pay you handsomely. A mark on your wrist, the shape of a little bell. You won't feel it. The fen will know you, that's all, and be gentler."

    Her fingertip touches your wrist. It is cold as a fish, and when it lifts there is a black bell on your skin, tiny and perfect.

    She gives you two healing draughts and a pinch of something that glows. Then she pats your hand and sends you out into the rain.

    "A mark is a door, sweet thing. It opens both ways."
  summary: '"One small thing," Mother Grey says, "and I''ll pay you handsomely.'
  inputs_hash: 1a0993dc95e41fb54d37443511809f32a5cc96e5b0693f68dcb4469de29ec867
---
The Marking is a bargain with a price. It opens one ending, and shuts another.
