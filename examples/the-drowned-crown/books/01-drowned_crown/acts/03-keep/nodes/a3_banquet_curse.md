---
id: b235b21f-60ea-5d8a-b7ff-b4ee9d58fe20
key: a3_banquet_curse
title: Poisoned Wine
summary: The wine goes down like honey and settles like lead.
location: hollow_keep
variants:
- id: 47d83944-27c5-5966-aba4-52b8eb371f9a
  label: Default
choices:
- id: 004a7383-8e5d-5b2b-9bb1-e0561820ad40
  label: Stagger on to the gallery
  effects:
  - op: modify
    stat: STAMINA
    amount: '-4'
  outcomes:
  - key: default
    target: a3_gallery
layout:
  x: 8000.0
  y: 0.0
prose:
- variant: 47d83944-27c5-5966-aba4-52b8eb371f9a
  text: |-
    The wine goes down like honey and settles like lead. Your hands go numb, then your lips, and the guests on either side turn their heads, slowly, in unison, and smile at you, with perfect warm friendly teeth.

    You gag, and bring up most of what you drank, and stumble away from the table with the whole hall tilting. They do not follow. They only watch you go, politely, as guests do.
  summary: The wine goes down like honey and settles like lead.
  inputs_hash: a76383f5c7be2c23194c8c8bbcf2ac2c09539ddbddd99de4bd83a4adb858c34a
---
Penalty: 4 STAMINA, applied on the choice that leads out.
