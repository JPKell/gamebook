---
id: fc3043a7-f13d-5840-807f-6837af644bf7
key: a1_square
title: Market Square
summary: The square is a bowl of wet cobbles ringed by narrow houses leaning together like drunks.
location: marrowmere
variants:
- id: 58e07884-2063-5264-a8f4-fbc09a021902
  label: Default
choices:
- id: 217601a4-6cf6-578a-99e1-99502306ee0b
  label: Enter the Salted Eel inn
  outcomes:
  - key: default
    target: a1_inn
- id: a459c1e3-c0c4-5e51-b34a-678fc746c3a5
  label: Visit Hobb's forge
  outcomes:
  - key: default
    target: a1_smith
- id: c565da7d-af7b-5b13-9ac5-b0e7e61c59e8
  label: Browse the chandler's shop
  outcomes:
  - key: default
    target: a1_chandler
- id: dab7fc36-8d9a-5a0d-bf1e-6de43ca29747
  label: Speak to the beggar by the well
  outcomes:
  - key: default
    target: a1_beggar
- id: 9f1a0fb8-b34a-5083-8d4e-2a1efa2be492
  label: Take the shortcut through Fishgut Alley
  outcomes:
  - key: default
    target: a1_alley
- id: 9228e583-30d8-5298-bd8d-72376b18e72f
  label: Visit the chapel of the bell
  outcomes:
  - key: default
    target: a1_chapel
- id: 2a7e29bc-f4db-5c28-b3c0-cd056f0a84d2
  label: Go to the reeve's hall
  condition: not flag(HIRED)
  outcomes:
  - key: default
    target: a1_reeve
- id: 0bbcdcc6-8f5b-5782-bcf0-fc7e7fc3b907
  label: Leave by the north road toward the Greywood
  condition: flag(HIRED)
  outcomes:
  - key: default
    target: a1_wood_edge
- id: f0670c5b-3668-5b22-9b85-1f423f5a5425
  label: Walk down to Old Wick's ferry landing
  condition: flag(HIRED)
  outcomes:
  - key: default
    target: a1_ferry
layout:
  x: 640.0
  y: 510.0
prose:
- variant: 58e07884-2063-5264-a8f4-fbc09a021902
  text: |-
    The square is a bowl of wet cobbles ringed by narrow houses leaning together like drunks. Fishwives pack their stalls away as the light fails, and a boy sweeps water from one end of the square to the other, where it immediately runs back.

    Every door has a sandbag across it. The doorways have waterlines scored into the frames, a different year beside each, higher every time.

    A lit sign swings above the inn. The smithy's forge glows orange, and the chandler's shutters are still open. An old woman begs by the well. A narrow alley leads off into shadow, and the squat chapel of the bell stands at the far end beside the reeve's hall.
  summary: The square is a bowl of wet cobbles ringed by narrow houses leaning together like drunks.
  inputs_hash: 27f0f6976420b838ed17bcd08422f23c0b8b258857da1f0b8f716634704408e6
---
Hub. The reader can shop, rest, gossip and then must be hired before leaving. Two routes out: the Greywood road or the ferry.
