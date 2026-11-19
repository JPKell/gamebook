---
id: fd15049d-bce5-53c6-9e91-dbce5e6dbc0a
key: a1_bandit_camp
title: Captain Brandt's Camp
summary: Six or seven outlaws sit around a smokeless fire, eating rabbit.
location: greywood
characters:
- captain_brandt
variants:
- id: b34361fe-5011-5681-b209-c86dd1b33286
  label: Default
encounters:
- id: 2809e4f3-0bec-54c9-9b83-2f0aa0c3996f
  label: Brandt and his men
  enemies:
  - enemy: brandt
    level: 1
    count: 1
  - enemy: bandit
    level: 1
    count: 1
choices:
- id: b8e47047-d6ab-5c64-8407-e00cfce23cd0
  label: Pay the toll (10 Gold)
  condition: GOLD >= 10
  effects:
  - op: modify
    stat: GOLD
    amount: '-10'
  outcomes:
  - key: default
    target: a1_bandit_pay
- id: 665fe57d-f0fe-5aa1-bac1-61414c0c4a9e
  label: 'Parley: argue the reeve will pay him for safe passage'
  kind: test
  test: skill
  outcomes:
  - key: success
    target: a1_bandit_deal
  - key: failure
    target: a1_bandit_pay
- id: b6018b90-3766-5317-8d0a-cfdca2d30f24
  label: Draw your weapon
  kind: combat
  encounter: 2809e4f3-0bec-54c9-9b83-2f0aa0c3996f
  outcomes:
  - key: win
    target: a1_bandit_loot
  - key: lose
    target: a1_death_bandit
- id: 92d7b5ae-799f-5840-baf0-12960c118686
  label: Slip past in the smoke
  condition: skill(STEALTH)
  min_tier: advanced
  outcomes:
  - key: default
    target: a1_woods_exit
layout:
  x: 1600.0
  y: 170.0
prose:
- variant: b34361fe-5011-5681-b209-c86dd1b33286
  text: |-
    Six or seven outlaws sit around a smokeless fire, eating rabbit. A lean man in a ragged cavalry cloak rises to meet you. He is sunburnt and polite, and he rests one hand on a sabre with the ease of long habit.

    "Captain Brandt," he says. "Formerly of the Marrowmere watch. Ten gold buys you the road. You'll find my terms are fair, and my patience is not."

    His men do not move, but they have all stopped chewing.
  summary: Six or seven outlaws sit around a smokeless fire, eating rabbit.
  inputs_hash: 8ad891fbc397419fe7519706aceaf4748a560cfcb9cd27b88c4aa74cf1349559
---
Four ways through: pay, talk, fight, or sneak (advanced tier, STEALTH). A failed parley means you pay anyway.
