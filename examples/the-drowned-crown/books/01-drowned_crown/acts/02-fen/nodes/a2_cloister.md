---
id: d880e612-a62f-5be8-b87f-2f77c430a77f
key: a2_cloister
title: The Cloister
summary: The cloister is a square of roofless arches around a flooded garden.
location: sunken_abbey
variants:
- id: a93c98c4-343e-54fd-8a43-e24a38a27b86
  label: Default
choices:
- id: 694da18c-7e83-5a2a-bdab-695ea3dc1b97
  label: Enter the library (it is too dark to read without a light)
  condition: has(lantern)
  print_text: If you have a Lantern, you may enter the library.
  outcomes:
  - key: default
    target: a2_library
- id: 5c50b735-a2af-548a-9a46-459588636d5f
  label: Search the kitchen
  outcomes:
  - key: default
    target: a2_kitchen
- id: 8f60c725-b011-5559-9f96-c74bef056e6f
  label: Knock at the lit cell
  outcomes:
  - key: default
    target: a2_alder
- id: 1371db88-5f99-5b9a-8ea2-a50b26565cdc
  label: Climb to the bell tower
  outcomes:
  - key: default
    target: a2_belltower
- id: 9dc77557-c0f1-59fc-a202-29e555bdf2c7
  label: Try the crypt door
  outcomes:
  - key: default
    target: a2_crypt_door
layout:
  x: 4480.0
  y: 0.0
prose:
- variant: a93c98c4-343e-54fd-8a43-e24a38a27b86
  text: |-
    The cloister is a square of roofless arches around a flooded garden. In the middle of it, a stone fountain still works, a thin silver thread of water falling into a basin of clear green light.

    Doors lead off in all directions: a vaulted library, a scullery, a small cell with a lit candle, a tall stair up into the bell tower and a low door sunk in the floor, fastened with an iron lock.

    The humming comes from everywhere at once.
  summary: The cloister is a square of roofless arches around a flooded garden.
  inputs_hash: bb3a314c623680c59eb219fc1a2e00de82e1b56fed56aa8068bd315e3000c0a3
---
Hub of the abbey. Library (lore), kitchen (supplies), Alder's cell (the seal), the bell, the crypt.
