---
id: d3acddd5-9060-58af-a647-3d378b6fc7df
key: a1_gate
title: Marrowmere's Gate
summary: Marrowmere crouches behind a wall of grey fieldstone that has been patched with timber, tarred
  sailcloth and what look like old boat hulls.
location: marrowmere
characters:
- reeve_hale
variants:
- id: 8eded442-d383-5a21-8abe-273f878e3c87
  label: Default
- id: 28d64c4c-3dfa-5578-a9c2-1fb7928b961e
  label: Reeve's hireling
  condition: flag(HIRED)
  priority: 10
choices:
- id: a7b6c627-e878-57d6-88e9-03d7e4e8fbf5
  label: Speak to the guard
  outcomes:
  - key: default
    target: a1_guard
- id: ec65b3e9-13bf-55ce-bfe6-68f066579a2e
  label: Walk straight through into the square
  outcomes:
  - key: default
    target: a1_square
layout:
  x: 320.0
  y: 170.0
prose:
- variant: 8eded442-d383-5a21-8abe-273f878e3c87
  text: |-
    Marrowmere crouches behind a wall of grey fieldstone that has been patched with timber, tarred sailcloth and what look like old boat hulls. Water stands in the ditch beneath it. A line of children's boots has been nailed along the gatepost, as a charm against drowning.

    A guard in a leaking helmet leans on his spear in the gate's mouth and watches you the way people watch weather.
  summary: Marrowmere crouches behind a wall of grey fieldstone that has been patched with timber, tarred
    sailcloth and what look like old boat hulls.
  inputs_hash: fcec3c902d6d3f5489e2627a42278f67aa08aceeb0effb2b77d52a7c275513da
- variant: 28d64c4c-3dfa-5578-a9c2-1fb7928b961e
  text: |-
    The guard straightens when he sees you coming back. News travels fast in a small town, and the reeve's coin is no secret. He gives you a nod that is almost a salute.

    "Mind the fen," he says. "It doesn't care who's paying."
  summary: The guard straightens when he sees you coming back.
  inputs_hash: ae597392860922c896f9f3dcd9d36df20ba9cbcd6cb4eb8c81a03a8e13ee0d52
---
Gate. Two variants: default, and the returning hireling.
