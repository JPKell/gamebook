---
id: b754cceb-7412-5062-a1b3-8f0b6c432a8b
key: a2_hag_riddle
title: Riddles
summary: '"A game!" the hag cries, and claps her hands.'
location: the_fen
characters:
- mother_grey
variants:
- id: 28028bc2-7138-520d-8a86-834e286c100e
  label: Default
choices:
- id: 9781ac4b-e14c-5069-a016-a465318d6c9c
  label: 'Answer: "A kingdom"'
  kind: test
  test: skill
  outcomes:
  - key: success
    target: a2_hag_prize
  - key: failure
    target: a2_hag_deal
layout:
  x: 4160.0
  y: 170.0
prose:
- variant: 28028bc2-7138-520d-8a86-834e286c100e
  text: |-
    "A game!" the hag cries, and claps her hands. "I love a game! One riddle for you, one for me, and the loser pays."

    She asks you: *What is it that drowns without water, fills without pouring, and has a throne?* Her blind eye gleams.

    You think of the fen, the crown, the king.
  summary: '"A game!" the hag cries, and claps her hands.'
  inputs_hash: 787d66e0e44266c5268f9ae5dcb05f2ba3e7132997cc518820a7582fb23986fd
---
Riddle contest. A skill test, with the Marking as the penalty for failure.
