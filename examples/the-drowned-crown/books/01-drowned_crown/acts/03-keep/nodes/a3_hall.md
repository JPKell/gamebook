---
id: a461e815-69b5-520c-9b71-9d5530b14010
key: a3_hall
title: The Great Hall
summary: The great hall is a hundred feet long and lit by a hundred chandeliers.
location: hollow_keep
characters:
- sir_aldous
variants:
- id: 89871791-ce51-5bd8-b6f4-79ee251e4e38
  label: Default
- id: 83588220-0796-5f4a-8302-b67fea8c305e
  label: You freed the prisoner
  condition: flag(PRISONER_FREED)
  priority: 10
encounters:
- id: 8320e38d-ba53-5eed-b5e0-3831510e5241
  label: Sir Aldous
  enemies:
  - enemy: sir_aldous
    level: 1
    count: 1
choices:
- id: bdb9a0ae-0c49-55e1-9560-a9f952390596
  label: Show him the Seal of the Abbey
  condition: has(abbey_seal)
  outcomes:
  - key: default
    target: a3_aldous_down
- id: 054f7bfd-da90-51a7-833d-0c9046bd1feb
  label: Fight Sir Aldous
  kind: combat
  encounter: 8320e38d-ba53-5eed-b5e0-3831510e5241
  outcomes:
  - key: win
    target: a3_aldous_down
  - key: lose
    target: a3_death_knight
- id: 888b0553-7c1d-5ab7-81a3-d3da6f04dfdc
  label: Withdraw to the courtyard
  outcomes:
  - key: default
    target: a3_courtyard
layout:
  x: 7040.0
  y: 680.0
prose:
- variant: 89871791-ce51-5bd8-b6f4-79ee251e4e38
  text: |-
    The great hall is a hundred feet long and lit by a hundred chandeliers. A long table runs down the middle, set for a banquet. At its end a stair rises to a pair of tall gilded doors.

    Between you and the stair stands a knight in black plate, perfectly still, with a great sword held point-down before him. His visor is open, and there is no one inside. He is Sir Aldous, captain of the guard. He has stood here for a hundred years.

    "Halt," he says, in a voice like iron on iron. "None may approach the king unannounced."
  summary: The great hall is a hundred feet long and lit by a hundred chandeliers.
  inputs_hash: 6d33029c771a6e9346ff718d21c83b8b7e00a2ff01967f15886a87d06cff7471
- variant: 83588220-0796-5f4a-8302-b67fea8c305e
  text: |-
    The great hall is a hundred feet long and lit by a hundred chandeliers. A long table runs down the middle, set for a banquet. At its end a stair rises to a pair of tall gilded doors.

    Between you and the stair stands a knight in black plate with a great sword held point-down before him. His visor is open, and there is no one inside. As you enter, his head turns very slightly, as if he heard a distant voice.

    "Pell," he says, with a rasp. "You freed Pell." For a moment, the iron voice almost sounds like a man's. "Halt," he says. "Please."
  summary: The great hall is a hundred feet long and lit by a hundred chandeliers.
  inputs_hash: d69d63c1a3cf1eb31ff186b48c85a3279293236a1d60c49d74520b24e040c419
---
The seal opens this door. Otherwise a long, hard fight. If the prisoner is free, Sir Aldous remembers him.
