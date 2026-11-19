---
id: fdb8d975-566f-5a72-bdb2-d12d5716b7c5
key: a3_kitchens
title: The Royal Kitchens
summary: Fires roar in half a dozen hearths.
location: hollow_keep
on_enter:
- op: modify
  stat: STAMINA
  amount: '4'
  once: true
variants:
- id: 76299899-a9a7-59da-aaad-2eb990be1b12
  label: Default
choices:
- id: 79e48750-b605-5ba4-92d5-976415242728
  label: Go up to the courtyard
  outcomes:
  - key: default
    target: a3_courtyard
layout:
  x: 6720.0
  y: 170.0
prose:
- variant: 76299899-a9a7-59da-aaad-2eb990be1b12
  text: |-
    Fires roar in half a dozen hearths. Cooks and scullions turn spits, stir pots and knead dough, all in perfect silence, all with the same glazed look. A haunch of beef turns over the main fire, hissing, glistening, and the smell of it makes your head swim.

    A scullery maid presses a wooden bowl into your hands. The stew is hot and rich and tastes of nothing at all. It fills your belly and warms your hands, and when you set the bowl down she takes it, curtsies and returns to her work.
  summary: Fires roar in half a dozen hearths.
  inputs_hash: f0cf7d4f9339da4fc03e19187eae420449bcdc97c9f3ec8251e4dc54012dd709
---
A free meal. The food is real enough to heal, and wrong enough to disturb.
