---
id: 091ddcd5-df47-5fa6-aef9-7d3911884db8
key: a1_inn_room
title: A Dry Bed
summary: The room is a closet under the eaves, with a bed, a candle stub and a window that looks onto
  the rain.
location: marrowmere
on_enter:
- op: modify
  stat: GOLD
  amount: '-3'
  once: true
- op: modify
  stat: STAMINA
  amount: '4'
  once: true
- op: give
  item: brass_key
  qty: 1
variants:
- id: 0b4ab220-ac89-5287-a29a-b3383fcbf3d2
  label: Default
choices:
- id: 002b73df-1778-5aa4-8e04-1975d78a3034
  label: Go down to the square
  outcomes:
  - key: default
    target: a1_square
layout:
  x: 1280.0
  y: 0.0
prose:
- variant: 0b4ab220-ac89-5287-a29a-b3383fcbf3d2
  text: |-
    The room is a closet under the eaves, with a bed, a candle stub and a window that looks onto the rain. You do not care. You wash, eat what Mara sends up, and fall asleep to the sound of the town being very quietly afraid.

    In the night something taps at the shutter, once, twice, patient as a heartbeat. In the morning there is nothing on the sill except a wet footprint the size of a child's, and you decide not to think about it.

    Mara has left a small brass key beside your boots. "My husband's," she says when you ask. "Never found the lock. You look like you might."
  summary: The room is a closet under the eaves, with a bed, a candle stub and a window that looks onto
    the rain.
  inputs_hash: e1ff2f1090b7983d12577fe77267748411041b63249ca059afdd907939e42988
---
One night's rest: +4 STAMINA, brass key from Mara.
