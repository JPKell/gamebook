---
id: df3e024a-4e52-522d-b352-726a6c4fcc86
key: a3_parley
title: The King Speaks
summary: Oswin takes your arm and walks you slowly around the room, talking all the while.
location: hollow_keep
characters:
- king_oswin
variants:
- id: a7557244-b1a4-526c-bcb2-48ce286c2327
  label: Default
encounters:
- id: 3664754d-4bf9-5165-9f84-88564ca9d111
  label: The Hollow King
  enemies:
  - enemy: hollow_king
    level: 1
    count: 1
choices:
- id: 94f9a272-d616-55b7-823a-719d3436459e
  label: Offer him the three shards
  condition: count(crown_shard) >= 3 and flag(LORE_KNOWN)
  outcomes:
  - key: default
    target: a3_final
- id: 7d9350d1-8415-5871-8f43-7f06b60f3cec
  label: Accept his offer of the crown
  condition: flag(MARKED)
  outcomes:
  - key: default
    target: a3_end_hollow
- id: f3df7449-3cc4-5400-b58b-c6c947af223d
  label: Draw your weapon
  kind: combat
  encounter: 3664754d-4bf9-5165-9f84-88564ca9d111
  outcomes:
  - key: win
    target: a3_king_fallen
  - key: lose
    target: a3_death_king
- id: ca34eac0-e236-5c73-8ddb-fa34a69a79fd
  label: Step back
  outcomes:
  - key: default
    target: a3_throne
layout:
  x: 8640.0
  y: 0.0
prose:
- variant: a7557244-b1a4-526c-bcb2-48ce286c2327
  text: |-
    Oswin takes your arm and walks you slowly around the room, talking all the while. He talks about the harvest, about taxes, about the weather, as if a century had not passed. He talks about his queen, and a shadow crosses his face.

    "I wore it for them," he says. "Do you see? So that no one need ever die. And it worked. It *worked.* Why does everyone look at me as if it had not?"

    He stops. His fingers rise to the crown and tremble against it, and he lowers them again. "It will not come off," he says, very quietly. "I have tried."
  summary: Oswin takes your arm and walks you slowly around the room, talking all the while.
  inputs_hash: d6a054f2d4f1573982c5a70e08f069d9bf55119e0adafe263a69d73005cf51b9
---
Talking is the better way. With all three shards and the abbey's lore, the king will let you try to mend it. The Marking offers a darker path.
