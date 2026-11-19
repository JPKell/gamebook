---
id: f4e37eea-dd5f-593b-8d28-cc0add80b490
key: a3_aldous_down
title: Aldous Stands Aside
summary: The knight lowers his sword.
location: hollow_keep
characters:
- sir_aldous
variants:
- id: c7cd93a4-5098-57aa-9b79-f28d6741dd82
  label: Default
choices:
- id: 63417dcd-1fd6-56c5-9886-00a45633f87a
  label: Sit at the banquet table
  outcomes:
  - key: default
    target: a3_banquet
- id: 0a138b56-a78a-5ddf-9fc7-d640a5e2f293
  label: Go through to the gallery
  outcomes:
  - key: default
    target: a3_gallery
- id: da77a20d-1347-574e-8c12-9ecf0fd0819e
  label: Withdraw to the courtyard
  outcomes:
  - key: default
    target: a3_courtyard
layout:
  x: 7360.0
  y: 170.0
prose:
- variant: c7cd93a4-5098-57aa-9b79-f28d6741dd82
  text: |-
    The knight lowers his sword. The great black helm turns toward the seal, and for a long moment the hall seems to hold its breath.

    "The Order," Sir Aldous says. "Then the Order has come at last." He steps aside, and bows, the creak of his plate echoing through the empty hall.

    Beyond him the table is laid for a banquet. A passage leads off into a gallery of portraits. At the far end of the hall the stair climbs toward the throne room.
  summary: The knight lowers his sword.
  inputs_hash: 7efa480d124ec051ab49551813512976e1cd5b56374abb9387b1fe8f78009b7c
---
The knight yields. Beyond him: the banquet, the gallery, and the way up.
