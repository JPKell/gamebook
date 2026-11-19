---
id: 4d44ac34-46cb-52ca-a7cf-42ca71de89eb
key: a1_start
title: The Road to Marrowmere
summary: You arrive at Marrowmere in the rain, knowing the reeve is hiring.
location: marrowmere
variants:
- id: 2fc2cbb2-1b5d-5a43-9658-08d914c36c8b
  label: Default
choices:
- id: 6d8636a7-c91c-5bd3-8f87-24f275204ca1
  label: Stop at the shrine
  outcomes:
  - key: default
    target: a1_shrine
- id: 5b35dce4-0e3c-5cbd-857a-901bec3a0c14
  label: Walk on to the town gate
  outcomes:
  - key: default
    target: a1_gate
layout:
  x: 0.0
  y: 0.0
prose:
- variant: 2fc2cbb2-1b5d-5a43-9658-08d914c36c8b
  text: |-
    Rain has followed you for three days, and now the road ends at a crooked signpost: MARROWMERE, 2 MILES. Below it someone has scratched a smaller line with a knife: TURN BACK.

    You have heard what people say about the town. The fen beyond it swallowed a whole kingdom a hundred years ago, and every spring it rises again to take a little more. The reeve is paying adventurers to do something about it. Two have already gone out into the water and not returned.

    Your pack is light and your purse is lighter. A small roadside shrine stands in the hedge, hung with fishermen's charms, and past it the lamps of the town are coming on.
  summary: You arrive at Marrowmere in the rain, knowing the reeve is hiring.
  inputs_hash: aa731a3cf0947f265edb3e655845c831a9a86bda4d4f231fbfe63204b654458a
---
Opening. Set mood: rain, dread, a town that wants a hero and doesn't expect one. Establish the reeve's offer and the missing hirelings.
