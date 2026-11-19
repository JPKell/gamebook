---
id: 16ee335e-0bdd-5367-a544-335c7c277d39
key: a3_banquet
title: The Banquet
summary: The table is a quarter-mile of white linen and gold plate.
location: hollow_keep
variants:
- id: cd1d65a0-495f-5739-b417-796dff34e56f
  label: Default
choices:
- id: 7a1a3564-c189-5047-b00a-f3a033ad34d2
  label: Eat and drink
  kind: test
  test: luck
  outcomes:
  - key: success
    target: a3_gallery
  - key: failure
    target: a3_banquet_curse
- id: 99ee4b60-791e-5555-9569-231de4dd65f8
  label: Refuse the feast and go on to the gallery
  outcomes:
  - key: default
    target: a3_gallery
layout:
  x: 7680.0
  y: 0.0
prose:
- variant: cd1d65a0-495f-5739-b417-796dff34e56f
  text: |-
    The table is a quarter-mile of white linen and gold plate. Every place is set. At every place sits a guest in court dress, perfectly still, a goblet halfway to their lips. A century of waiting has left them well preserved and entirely absent.

    At the head, in a high-backed chair, waits an empty place laid for you. The food in front of it steams. The wine is dark and sweet and smells of summer.

    Hunger gnaws at you. This is how it began for the rest, you suspect.
  summary: The table is a quarter-mile of white linen and gold plate.
  inputs_hash: cdac277c238a27feca097c3972ac8a52ab8a64f6fc258291f7b72717930b58f2
---
A temptation. A lucky reader eats well. Otherwise the feast bites back.
