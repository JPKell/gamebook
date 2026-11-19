---
id: b93b96ed-df58-5a2b-b8ae-72cccc51d6ef
key: a2_island
title: Fisherman's Island
summary: A low, humped island with a half-collapsed boathouse and a ring of blackened stones.
location: the_fen
items:
- item: ration
  qty: 1
variants:
- id: 54cae442-35e1-5555-b553-8cc689621248
  label: Default
choices:
- id: 11f4e93e-6944-5288-a2d7-337f3df7994d
  label: Visit the smoking hut to the east
  outcomes:
  - key: default
    target: a2_hut
- id: 5c873a8b-9936-569b-963c-1a5013014cf8
  label: Climb the signal tower
  outcomes:
  - key: default
    target: a2_tower
- id: 7612a204-862b-5654-bf7f-a3025304fd91
  label: Take the flooded road to the abbey
  outcomes:
  - key: default
    target: a2_abbey_gate
layout:
  x: 3520.0
  y: 170.0
prose:
- variant: 54cae442-35e1-5555-b553-8cc689621248
  text: |-
    A low, humped island with a half-collapsed boathouse and a ring of blackened stones. Someone camped here not long ago. There are fish bones in the ashes and a scatter of broken floats.

    From here the whole fen is spread before you. The leaning tower rises to the north, topped with a cracked iron brazier. A column of grey smoke twists from a hut on a second island to the east. And straight ahead, at the end of a long flooded road, the roof of the Sunken Abbey breaks the surface like the back of a whale.

    You could rest for an hour. The fen does not seem to mind.
  summary: A low, humped island with a half-collapsed boathouse and a ring of blackened stones.
  inputs_hash: b81c05f04822c9edca64d14ca6f011c0e09feb6bd8d9540bd2a35c2c4d4c4bf5
---
Hub of the fen. Three ways on: the hag's hut, the tower (a view and a clue), or straight to the abbey.
