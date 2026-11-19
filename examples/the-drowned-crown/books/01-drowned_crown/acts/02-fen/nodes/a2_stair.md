---
id: 40414787-b39a-566b-8623-07edf388f083
key: a2_stair
title: The Stair Below
summary: The stair is dry, and dusty, and very steep.
act_exit: true
location: sunken_abbey
variants:
- id: ca68ae41-0f2f-5010-88a4-68b7f4ce1c0a
  label: Default
choices:
- id: 07154a0b-52da-58d7-bd42-93a3dfcd635b
  label: Open the wooden door
  outcomes:
  - key: default
    target: a3_keepgate
- id: 80566215-0317-55ba-82de-818007184904
  label: Crawl through the water gate
  condition: has(rope) or has(lantern)
  print_text: If you have a rope or a lantern, you may crawl through the water gate.
  outcomes:
  - key: default
    target: a3_watergate
layout:
  x: 5760.0
  y: 170.0
prose:
- variant: ca68ae41-0f2f-5010-88a4-68b7f4ce1c0a
  text: |-
    The stair is dry, and dusty, and very steep. It descends through living rock for a long time, and somewhere along the way the damp air turns warm, and then dry, and then perfumed, faintly, with old candle smoke and lavender.

    At the bottom is a landing with two doors. One is a plain wooden door, and under it you see a bar of golden light. The other is a low iron grate through which comes the soft sound of running water. It leads, you guess, to a drowned passage along the keep's foundations.

    From above, very faintly, you hear the abbey bell ring a single note, as if in warning.
  summary: The stair is dry, and dusty, and very steep.
  inputs_hash: 7017c347290b92ca3d50191376c7012e737faab6740f68ce21392e76900b752b
---
Act exit. The front door is easy; the water gate needs a light or a rope.
