---
id: 0836dc66-12b9-581e-a579-6fcdfcd241ad
key: a2_hut
title: Mother Grey's Hut
summary: The hut is built on stilts out of the wreck of a boat, and festooned with fishbones, glass floats
  and dried herbs.
location: the_fen
characters:
- mother_grey
variants:
- id: 446a042f-87c1-5ab8-9811-3c8baef95adf
  label: Default
- id: 56309ee2-d835-5c94-b5e7-63e0cd19f240
  label: Already marked
  condition: flag(MARKED)
  priority: 10
encounters:
- id: a5caafc4-e8e6-5497-b171-9eca284ad888
  label: Mother Grey
  enemies:
  - enemy: mother_grey
    level: 1
    count: 1
choices:
- id: 766a9189-2a1f-524a-8b10-c72c63f4c50c
  label: Strike a bargain with her
  condition: not flag(MARKED)
  outcomes:
  - key: default
    target: a2_hag_deal
- id: 26df6db7-8a95-5946-8ec9-3a419b126407
  label: Challenge her to a riddle contest
  outcomes:
  - key: default
    target: a2_hag_riddle
- id: 52270b27-6fab-5916-833a-5c6f5bfd9657
  label: Attack her before she poisons you
  kind: combat
  encounter: a5caafc4-e8e6-5497-b171-9eca284ad888
  outcomes:
  - key: win
    target: a2_hag_prize
  - key: lose
    target: a2_death_hag
- id: f04863e7-f120-5e39-9e09-0794ed391f6b
  label: Leave quietly
  outcomes:
  - key: default
    target: a2_island
layout:
  x: 3840.0
  y: 170.0
prose:
- variant: 446a042f-87c1-5ab8-9811-3c8baef95adf
  text: |-
    The hut is built on stilts out of the wreck of a boat, and festooned with fishbones, glass floats and dried herbs. A thin woman is stirring a pot with a spoon that is as sharp as a knife. One of her eyes is blind and white. The other follows you.

    "A visitor," she sings. "Sit, sit. I never get visitors who are still warm. What do you want, sweet thing? Names? Luck? A song to keep the water out?"

    The pot smells of something wonderful. You are not hungry. You are suddenly, tremendously hungry.
  summary: The hut is built on stilts out of the wreck of a boat, and festooned with fishbones, glass
    floats and dried herbs.
  inputs_hash: 219f3670957862c0338920b9f1122ba17cc14218c3271bef5074dfe7605976cd
- variant: 56309ee2-d835-5c94-b5e7-63e0cd19f240
  text: |-
    Mother Grey does not look up when you duck under the lintel. "Ah," she sings, to the pot. "Back so soon? The mark itches, doesn't it? It does that."

    She dips a ladle and sniffs it, and her blind eye turns slowly toward you. "There's nothing more I can sell you, sweet thing. Except a better ending. For a price."
  summary: Mother Grey does not look up when you duck under the lintel.
  inputs_hash: 8526dc9a20590b826c1cf088d19177be7386bae02e2c98c332d303e89bf6a3a8
---
The hag's hut. Three ways in: deal (take the Marking), riddle, or fight. A reader who is already marked gets a different greeting.
