---
id: 79115281-73fc-59f2-b6f5-e214034ab49c
key: a1_beggar
title: The Beggar by the Well
summary: She sits with her back to the well and a cracked bowl in her lap, a tiny woman wrapped in so
  many sacks that she looks like a pile of them.
location: marrowmere
variants:
- id: b0c48e51-5ba2-50a5-9d1f-1ec38632e798
  label: Default
choices:
- id: 109264f8-eddf-53cc-ba45-e4e2c3ca8751
  label: Give her a coin (1 Gold)
  condition: GOLD >= 1
  effects:
  - op: modify
    stat: GOLD
    amount: '-1'
  outcomes:
  - key: default
    target: a1_beggar_gift
- id: 481bcd94-4cce-542e-a17f-44d79eb18ba9
  label: Quietly take what's in the sack
  kind: test
  test: luck
  outcomes:
  - key: success
    target: a1_beggar_whistle
  - key: failure
    target: a1_square
- id: 41b5d1aa-5ef3-5169-8993-9caacb4612ef
  label: Walk away
  outcomes:
  - key: default
    target: a1_square
layout:
  x: 960.0
  y: 510.0
prose:
- variant: b0c48e51-5ba2-50a5-9d1f-1ec38632e798
  text: |-
    She sits with her back to the well and a cracked bowl in her lap, a tiny woman wrapped in so many sacks that she looks like a pile of them. Her eyes, when they find you, are very sharp.

    "A coin for the old girl," she says. "Or take what's in the sack and be a thief. Either way, you'll see the fen."

    Her sack is open on the cobbles beside her. Something bone-white shows in the folds.
  summary: She sits with her back to the well and a cracked bowl in her lap, a tiny woman wrapped in so
    many sacks that she looks like a pile of them.
  inputs_hash: 9bad54de2318868738f2a38b614a7ae07c5ad8d444b82e8d16f614074027738a
---
A small moral choice. Generosity gives a map. Theft is a luck test, and the whistle is the reward.
