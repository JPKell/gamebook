---
id: 6d66c418-f787-590e-b759-51538c3df259
key: a3_courtyard
title: Courtyard of the Dead
summary: The courtyard is the busiest place you have seen in a hundred years of fen.
location: hollow_keep
variants:
- id: 291e43bb-a252-56df-aca6-d7354643ca7e
  label: Default
choices:
- id: 6afcd9e9-92ba-586d-a2e9-f9d13d1d8ae0
  label: Visit the armoury
  outcomes:
  - key: default
    target: a3_armoury
- id: 0d57e1a0-0ca2-521b-821c-333712e78ef9
  label: Visit the kitchens
  outcomes:
  - key: default
    target: a3_kitchens
- id: 91a14de3-342a-51f0-87c6-1d0d63c89abe
  label: Visit the chapel
  outcomes:
  - key: default
    target: a3_chapel_keep
- id: 872f0781-782e-53aa-b426-3e854afba873
  label: Go down the gaol stair
  outcomes:
  - key: default
    target: a3_dungeon
- id: 45ce9fda-3383-5083-a0a8-d6900358027b
  label: Climb the steps to the great hall
  outcomes:
  - key: default
    target: a3_hall
- id: 42a9a0ae-ca64-5008-91f4-db71c88bb1ed
  label: Turn back. This is no place for the living
  outcomes:
  - key: default
    target: a3_end_flee
layout:
  x: 6720.0
  y: 0.0
prose:
- variant: 291e43bb-a252-56df-aca6-d7354643ca7e
  text: |-
    The courtyard is the busiest place you have seen in a hundred years of fen. A hundred servants cross it in every direction: grooms, scullions, pages, washerwomen, carrying baskets, calling orders, hanging linens in the still, warm air. Not one of them makes a sound.

    They do not look at you. They go on as they have gone on for a century, perfect, tireless and empty. A boy with a bucket passes within a hand's breadth of your face, and his eyes are the milky green of a fish's.

    A broad flight of steps rises to the great hall. Doors lead off to the armoury, the kitchens and a small chapel. A low iron-bound door beneath the stair is marked simply: GAOL.
  summary: The courtyard is the busiest place you have seen in a hundred years of fen.
  inputs_hash: 47fd036962a87de793fe8e13430dfb09e695408effba3c85de74225d9caaad43
---
Hub of the keep. Servants are harmless unless provoked. The only danger lies up the steps.
