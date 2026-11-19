---
id: 5429d7aa-7990-5a5b-81ce-7a69752a34bc
key: a3_throne
title: The Hollow King
summary: The throne room is vast, white and entirely empty, save for the throne and the man who sits on
  it.
location: hollow_keep
characters:
- king_oswin
variants:
- id: 9eda8548-fb54-5a12-a0de-a1cced981257
  label: Default
- id: 74fa2848-aa85-5a86-bd4a-b07f37c8bf55
  label: You are marked
  condition: flag(MARKED)
  priority: 10
encounters:
- id: c8e2eeb8-4c85-51c8-b0e5-e5c8ec390eaa
  label: The Hollow King
  enemies:
  - enemy: hollow_king
    level: 1
    count: 1
choices:
- id: f87fdfb8-71e5-54b2-8bc0-e3c089cbb48b
  label: Speak with him
  outcomes:
  - key: default
    target: a3_parley
- id: a3aa64ff-5e5a-52b9-b212-7d67188195b1
  label: Attack the king
  kind: combat
  encounter: c8e2eeb8-4c85-51c8-b0e5-e5c8ec390eaa
  outcomes:
  - key: win
    target: a3_king_fallen
  - key: lose
    target: a3_death_king
- id: 0e3b683d-119d-53ab-a83f-d7c1e62f0a93
  label: Retreat down the stair
  outcomes:
  - key: default
    target: a3_throne_stair
layout:
  x: 8320.0
  y: 340.0
prose:
- variant: 9eda8548-fb54-5a12-a0de-a1cced981257
  text: |-
    The throne room is vast, white and entirely empty, save for the throne and the man who sits on it. King Oswin is tall, fair, handsome and quite perfect, with a smooth, kind face that has not aged by a day. On his brow rests a circlet of black iron, with three jagged gaps.

    He rises when you enter and smiles, and for a moment you almost believe it.

    "Welcome," he says. "Welcome, welcome. You are the first living guest I have had in a hundred years. Have you come to be crowned?"
  summary: The throne room is vast, white and entirely empty, save for the throne and the man who sits
    on it.
  inputs_hash: ae22f64e89198254d812b04a6f42a3ddd02a2020b27cb1ab8ea35419a3a20ccb
- variant: 74fa2848-aa85-5a86-bd4a-b07f37c8bf55
  text: |-
    The throne room is vast, white and entirely empty, save for the throne and the man who sits on it. King Oswin is tall, fair and perfect, with a smooth, kind face that has not aged by a day. On his brow rests a circlet of black iron, with three jagged gaps.

    His gaze falls on your wrist, on the small black bell, and his smile deepens with something like delight.

    "One of mine," he says softly. "The fen's friend. Come closer, child. You have come home."
  summary: The throne room is vast, white and entirely empty, save for the throne and the man who sits
    on it.
  inputs_hash: d12e2194dd63eafdcbc1d5ecae266254eb296caa918f942e855cf1cf819e04bb
---
The final confrontation. A fight, or a long conversation. The Marking changes the king's greeting.
