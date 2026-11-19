---
id: a1388c71-0546-549b-a167-2ccd7c764f36
key: a2_wisps
title: Lights in the Reeds
summary: Pale lights drift in the reeds ahead, blue and soft and friendly, bobbing like lanterns carried
  by someone who wants you to follow.
location: the_fen
variants:
- id: d8d5742f-95d0-5799-9f63-0128a7e316e8
  label: Default
- id: 2d8656d9-76db-59f4-b166-948e804f3fa5
  label: You have the map
  condition: has(marsh_map)
  priority: 10
choices:
- id: 305e24b6-e5a2-57dd-a9a0-14cad98ce8c1
  label: Follow the lights
  outcomes:
  - key: default
    target: a2_mire
- id: 86ac3a5e-0078-5b92-bc89-fcc26f9d600d
  label: Ignore them and keep to the causeway
  outcomes:
  - key: default
    target: a2_island
layout:
  x: 3200.0
  y: 170.0
prose:
- variant: d8d5742f-95d0-5799-9f63-0128a7e316e8
  text: |-
    Pale lights drift in the reeds ahead, blue and soft and friendly, bobbing like lanterns carried by someone who wants you to follow. Now and then one dips below the water and rises a little farther along, as if to show the way.

    The marsh map, if you have it, says nothing about lights. The old stories say a great deal.

    The causeway bends east, toward the leaning tower and a low island with a thread of smoke. The lights bend north.
  summary: Pale lights drift in the reeds ahead, blue and soft and friendly, bobbing like lanterns carried
    by someone who wants you to follow.
  inputs_hash: d1398591aab445209c772a193305027c25a77748943e731a3a6d32b6d098801c
- variant: 2d8656d9-76db-59f4-b166-948e804f3fa5
  text: |-
    Pale lights drift in the reeds ahead, blue and soft and friendly. You know them from the beggar's old map, where a small neat hand has written beside the northern reeds: *Wisps. Do not follow.*

    The causeway bends east, toward the leaning tower and a low island with a thread of smoke. The lights bend north, patient, hopeful.
  summary: Pale lights drift in the reeds ahead, blue and soft and friendly.
  inputs_hash: b4bf7a076731c104876b5aca25b6d53d9adb7875d1f7573f5356eaa6fd145235
---
Wisp temptation. If the reader has the map, the text warns them.
